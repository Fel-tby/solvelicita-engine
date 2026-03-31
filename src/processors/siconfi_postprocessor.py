"""
siconfi_postprocessor.py — Bloco 7
Lê int_eorcam + int_lliq_base do BigQuery.
Replica exatamente a lógica do lliq_scorer.py + eorcam_scorer.py.
Atualiza mart.mart_indicadores_municipios via MERGE.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import pandas as pd
from datetime import date
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()
if key := os.getenv("GCP_SA_KEY_PATH"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key

from scorers.config import (
    PESOS_ANO,
    LIMIAR_LLIQ_SUSPEITO,
    JANELA_RGF_BIMESTRAL,
    JANELA_RGF_SEMESTRAL,
    FIM_PERIODO_MES,
)

PROJECT      = "solvelicita"
DATASET_I    = "intermediate"
DATASET_M    = "mart"
TABLE_TARGET = f"{PROJECT}.{DATASET_I}.int_siconfi_postprocessed"
HOJE         = date.today()


def _bq(client: bigquery.Client, table: str) -> pd.DataFrame:
    return client.query(
        f"SELECT * FROM `{PROJECT}.{DATASET_I}.{table}`"
    ).to_dataframe()


def _bq_mart_pop(client: bigquery.Client) -> pd.DataFrame:
    """Busca populacao do mart para usar no decay."""
    return client.query(
        f"SELECT cod_ibge, populacao FROM `{PROJECT}.{DATASET_M}.mart_indicadores_municipios`"
    ).to_dataframe()


# ── eorcam ────────────────────────────────────────────────────────────────────

def _eorcam_ponderado(df: pd.DataFrame) -> pd.DataFrame:
    """Média ponderada por PESOS_ANO. Grain: cod_ibge."""
    df = df[df["entregou_rreo"] == True].copy()
    df["peso"] = df["ano"].map(PESOS_ANO).fillna(0)
    df = df[df["peso"] > 0]
    agg = (
        df.groupby("cod_ibge")
        .apply(
            lambda g: (g["eorcam_raw"] * g["peso"]).sum() / g["peso"].sum(),
            include_groups=False
        )
        .reset_index()
        .rename(columns={0: "eorcam_raw"})
    )
    agg["eorcam_raw"] = agg["eorcam_raw"].round(6)
    return agg


# ── lliq ──────────────────────────────────────────────────────────────────────

def _dias_atraso(ano: int, periodo: int, periodicidade: str) -> int:
    """
    Replica _dias_atraso do lliq_scorer.py.
    Adiciona 2 meses de prazo de publicação ao fim do período RGF.
    """
    if pd.isna(periodo) or pd.isna(periodicidade):
        return 999
    key = (str(periodicidade), int(periodo))
    if key not in FIM_PERIODO_MES:
        return 999
    mes_pub  = FIM_PERIODO_MES[key] + 2
    ano_pub  = int(ano) + (1 if mes_pub > 12 else 0)
    mes_pub  = mes_pub - 12 if mes_pub > 12 else mes_pub
    try:
        return max(0, (HOJE - date(ano_pub, mes_pub, 1)).days)
    except Exception:
        return 999


def _decay(dias: int, populacao: int) -> float:
    """Replica _decay do lliq_scorer.py."""
    janela = JANELA_RGF_BIMESTRAL if int(populacao) > 50_000 else JANELA_RGF_SEMESTRAL
    if dias <= janela:
        return 1.0
    return round(max(0.0, 1.0 - (dias - janela) / 365.0), 4)


def _lliq(df: pd.DataFrame, df_pop: pd.DataFrame) -> pd.DataFrame:
    """
    Seleciona o RGF mais recente por município. Grain de saída: cod_ibge.
    Prioridade: Q > S no mesmo ano (igual ao lliq_scorer).
    """
    df = df.copy()
    df["_prior_per"] = (df["periodicidade_rgf"] == "Q").astype(int)
    df = df.sort_values(
        ["cod_ibge", "ano", "periodo_rgf", "_prior_per"],
        ascending=[True, False, False, False]
    )

    df = df.merge(df_pop[["cod_ibge", "populacao"]], on="cod_ibge", how="left")

    records = []
    for cod_ibge, grp in df.groupby("cod_ibge"):
        pop = int(grp["populacao"].iloc[0]) if grp["populacao"].notna().any() else 0
        found = False

        for _, row in grp.iterrows():
            rec = row["receita_realizada"]
            if pd.isna(rec) or rec <= 0:
                continue

            if pd.notnull(row["dcl_apos_rp_total"]):
                rpps     = row["dcl_apos_rp_rpps"] if pd.notnull(row["dcl_apos_rp_rpps"]) else 0.0
                lliq_raw = round((row["dcl_apos_rp_total"] - rpps) / rec, 6)
                parcial  = False
            elif pd.notnull(row["dcl_pre_rp_total"]):
                rpps     = row["dcl_pre_rp_rpps"] if pd.notnull(row["dcl_pre_rp_rpps"]) else 0.0
                lliq_raw = round((row["dcl_pre_rp_total"] - rpps) / rec, 6)
                parcial  = True
            else:
                continue

            dias     = _dias_atraso(int(row["ano"]), int(row["periodo_rgf"]), str(row["periodicidade_rgf"]))
            decay    = _decay(dias, pop)
            janela   = JANELA_RGF_BIMESTRAL if pop > 50_000 else JANELA_RGF_SEMESTRAL

            records.append({
                "cod_ibge":           cod_ibge,
                "lliq_raw":           lliq_raw,
                "lliq_parcial":       parcial,
                "dias_atraso":        dias,
                "decay_fator":        decay,
                "dado_suspeito_lliq": bool(lliq_raw < LIMIAR_LLIQ_SUSPEITO),
                "dado_defasado":      bool(dias > janela),
            })
            found = True
            break

        if not found:
            records.append({
                "cod_ibge":           cod_ibge,
                "lliq_raw":           None,
                "lliq_parcial":       False,
                "dias_atraso":        None,
                "decay_fator":        None,
                "dado_suspeito_lliq": False,
                "dado_defasado":      False,
            })

    return pd.DataFrame(records)


# ── BQ MERGE ──────────────────────────────────────────────────────────────────

def _merge_bq(client: bigquery.Client, df: pd.DataFrame, uf: str) -> None:
    # Garante que a tabela existe antes do MERGE
    schema = [
        bigquery.SchemaField("cod_ibge", "INT64"),
        bigquery.SchemaField("uf", "STRING"),
        bigquery.SchemaField("eorcam_raw", "FLOAT64"),
        bigquery.SchemaField("lliq_raw", "FLOAT64"),
        bigquery.SchemaField("lliq_parcial", "BOOL"),
        bigquery.SchemaField("dias_atraso", "INT64"),
        bigquery.SchemaField("decay_fator", "FLOAT64"),
        bigquery.SchemaField("dado_suspeito_lliq", "BOOL"),
        bigquery.SchemaField("dado_defasado", "BOOL"),
        bigquery.SchemaField("updated_at", "TIMESTAMP"),
    ]
    table = bigquery.Table(TABLE_TARGET, schema=schema)
    client.create_table(table, exists_ok=True)

    df["uf"] = uf
    tmp = f"{PROJECT}.{DATASET_M}._tmp_siconfi_post"

    job = client.load_table_from_dataframe(
        df, tmp,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    )
    job.result()

    client.query(f"""
    MERGE `{TABLE_TARGET}` T
    USING `{tmp}` S ON T.cod_ibge = S.cod_ibge
    WHEN MATCHED THEN UPDATE SET
        T.uf                  = S.uf,
        T.eorcam_raw          = S.eorcam_raw,
        T.lliq_raw            = S.lliq_raw,
        T.lliq_parcial        = S.lliq_parcial,
        T.dias_atraso         = CAST(S.dias_atraso AS INT64),
        T.decay_fator         = S.decay_fator,
        T.dado_suspeito_lliq  = S.dado_suspeito_lliq,
        T.dado_defasado       = S.dado_defasado,
        T.updated_at          = CURRENT_TIMESTAMP()
    WHEN NOT MATCHED THEN INSERT (
        cod_ibge, uf, eorcam_raw, lliq_raw, lliq_parcial, dias_atraso,
        decay_fator, dado_suspeito_lliq, dado_defasado, updated_at
    ) VALUES (
        S.cod_ibge, S.uf, S.eorcam_raw, S.lliq_raw, S.lliq_parcial, CAST(S.dias_atraso AS INT64),
        S.decay_fator, S.dado_suspeito_lliq, S.dado_defasado, CURRENT_TIMESTAMP()
    )
    """).result()

    client.delete_table(tmp, not_found_ok=True)
    print(f"  ✅ MERGE concluído — {len(df)} linhas em int_siconfi_postprocessed")


# ── entry point ───────────────────────────────────────────────────────────────

def run(uf: str = "PB") -> None:
    print("=" * 60)
    print(" siconfi_postprocessor — Bloco 7")
    print(f" UF: {uf}")
    print("=" * 60)

    client = bigquery.Client(project=PROJECT)

    print("\n── Lendo int_eorcam...")
    df_eorcam = _bq(client, "int_eorcam")
    df_eorcam["cod_ibge"] = df_eorcam["cod_ibge"].astype("Int64")
    df_eorcam_m = _eorcam_ponderado(df_eorcam)
    print(f"   {len(df_eorcam_m)} municípios com eorcam_raw")

    print("\n── Lendo int_lliq_base...")
    df_lliq = _bq(client, "int_lliq_base")
    df_lliq["cod_ibge"]   = df_lliq["cod_ibge"].astype("Int64")

    print("\n── Buscando populacao do mart...")
    df_pop = _bq_mart_pop(client)
    df_pop["cod_ibge"]    = df_pop["cod_ibge"].astype("Int64")

    df_lliq_m = _lliq(df_lliq, df_pop)
    print(f"   {df_lliq_m['lliq_raw'].notna().sum()} municípios com lliq_raw")
    print(f"   {df_lliq_m['lliq_parcial'].sum()} com lliq_parcial (pré-RPNP)")
    print(f"   {df_lliq_m['dado_defasado'].sum()} com dado_defasado")

    print("\n── Fazendo MERGE em int_siconfi_postprocessed...")
    merged = df_eorcam_m.merge(df_lliq_m, on="cod_ibge", how="outer")
    _merge_bq(client, merged, uf=uf)

    print("\n✅ siconfi_postprocessor concluído.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="PB")
    args = parser.parse_args()
    run(uf=args.uf)

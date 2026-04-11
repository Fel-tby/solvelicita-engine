"""
siconfi_postprocessor.py - Bloco 7
Le int_eorcam + int_lliq_base do BigQuery.
Replica exatamente a logica do lliq_scorer.py + eorcam_scorer.py.
Atualiza intermediate.int_siconfi_postprocessed via BigQuery MERGE.
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scorers.config import (
    FIM_PERIODO_MES,
    JANELA_RGF_BIMESTRAL,
    JANELA_RGF_SEMESTRAL,
    LIMIAR_LLIQ_SUSPEITO,
    PESOS_ANO,
)
from utils.bigquery_loader import (
    get_bigquery_project,
    merge_dataframe_to_table,
    query_to_dataframe,
)
from utils.paths import get_paths


DATASET_I = "intermediate"
DATASET_M = "mart"
HOJE = date.today()


def _project() -> str:
    return get_bigquery_project()


def _bq(table: str, uf: str) -> pd.DataFrame:
    project = _project()
    query = f"""
        SELECT t.*
        FROM `{project}.{DATASET_I}.{table}` t
        JOIN `{project}.staging.stg_municipios` m
          ON t.cod_ibge = m.cod_ibge
        WHERE m.uf = '{uf}'
    """
    return query_to_dataframe(query, strict=True)


def _bq_anuais(uf: str) -> pd.DataFrame:
    project = _project()
    query = f"""
        SELECT *
        FROM `{project}.{DATASET_I}.int_siconfi_indicadores_anuais`
        WHERE uf = '{uf}'
        ORDER BY instituicao, ano
    """
    return query_to_dataframe(query, strict=True)


def _bq_mart_pop() -> pd.DataFrame:
    """Busca populacao do mart para usar no decay."""
    project = _project()
    query = f"SELECT cod_ibge, populacao FROM `{project}.{DATASET_M}.mart_indicadores_municipios`"
    return query_to_dataframe(query, strict=True)


def _eorcam_ponderado(df: pd.DataFrame) -> pd.DataFrame:
    """Media ponderada por PESOS_ANO. Grain: cod_ibge."""
    df = df[df["entregou_rreo"] == True].copy()
    df["peso"] = df["ano"].map(PESOS_ANO).fillna(0)
    df = df[df["peso"] > 0]
    agg = (
        df.groupby("cod_ibge")
        .apply(
            lambda g: (g["eorcam_raw"] * g["peso"]).sum() / g["peso"].sum(),
            include_groups=False,
        )
        .reset_index()
        .rename(columns={0: "eorcam_raw"})
    )
    agg["eorcam_raw"] = agg["eorcam_raw"].round(6)
    return agg


def _dias_atraso(ano: int, periodo: int, periodicidade: str) -> int:
    """
    Replica _dias_atraso do lliq_scorer.py.
    Adiciona 2 meses de prazo de publicacao ao fim do periodo RGF.
    """
    if pd.isna(periodo) or pd.isna(periodicidade):
        return 999
    key = (str(periodicidade), int(periodo))
    if key not in FIM_PERIODO_MES:
        return 999
    mes_pub = FIM_PERIODO_MES[key] + 2
    ano_pub = int(ano) + (1 if mes_pub > 12 else 0)
    mes_pub = mes_pub - 12 if mes_pub > 12 else mes_pub
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
    Seleciona o RGF mais recente por municipio. Grain de saida: cod_ibge.
    Prioridade: Q > S no mesmo ano (igual ao lliq_scorer).
    """
    df = df.copy()
    df["_prior_per"] = (df["periodicidade_rgf"] == "Q").astype(int)
    df = df.sort_values(
        ["cod_ibge", "ano", "periodo_rgf", "_prior_per"],
        ascending=[True, False, False, False],
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
                rpps = row["dcl_apos_rp_rpps"] if pd.notnull(row["dcl_apos_rp_rpps"]) else 0.0
                lliq_raw = round((row["dcl_apos_rp_total"] - rpps) / rec, 6)
                parcial = False
            elif pd.notnull(row["dcl_pre_rp_total"]):
                rpps = row["dcl_pre_rp_rpps"] if pd.notnull(row["dcl_pre_rp_rpps"]) else 0.0
                lliq_raw = round((row["dcl_pre_rp_total"] - rpps) / rec, 6)
                parcial = True
            else:
                continue

            dias = _dias_atraso(int(row["ano"]), int(row["periodo_rgf"]), str(row["periodicidade_rgf"]))
            decay = _decay(dias, pop)
            janela = JANELA_RGF_BIMESTRAL if pop > 50_000 else JANELA_RGF_SEMESTRAL

            records.append(
                {
                    "cod_ibge": cod_ibge,
                    "lliq_raw": lliq_raw,
                    "lliq_parcial": parcial,
                    "dias_atraso": dias,
                    "decay_fator": decay,
                    "dado_suspeito_lliq": bool(lliq_raw < LIMIAR_LLIQ_SUSPEITO),
                    "dado_defasado": bool(dias > janela),
                }
            )
            found = True
            break

        if not found:
            records.append(
                {
                    "cod_ibge": cod_ibge,
                    "lliq_raw": None,
                    "lliq_parcial": False,
                    "dias_atraso": None,
                    "decay_fator": None,
                    "dado_suspeito_lliq": False,
                    "dado_defasado": False,
                }
            )

    return pd.DataFrame(records)


def _merge_bq(df: pd.DataFrame, uf: str) -> None:
    project = _project()
    table_ref = f"{project}.{DATASET_I}.int_siconfi_postprocessed"
    temp_ref = f"{project}.{DATASET_M}._tmp_siconfi_post"
    schema_spec = [
        ("cod_ibge", "INT64"),
        ("uf", "STRING"),
        ("eorcam_raw", "FLOAT64"),
        ("lliq_raw", "FLOAT64"),
        ("lliq_parcial", "BOOL"),
        ("dias_atraso", "INT64"),
        ("decay_fator", "FLOAT64"),
        ("dado_suspeito_lliq", "BOOL"),
        ("dado_defasado", "BOOL"),
        ("updated_at", "TIMESTAMP"),
    ]

    df_upload = df.copy()
    df_upload["uf"] = uf

    merge_dataframe_to_table(
        df_upload,
        table_ref=table_ref,
        schema_spec=schema_spec,
        key_cols=["cod_ibge"],
        temp_table_ref=temp_ref,
        extra_update_assignments={"updated_at": "CURRENT_TIMESTAMP()"},
        extra_insert_values={"updated_at": "CURRENT_TIMESTAMP()"},
    )
    print(f"  OK MERGE concluido - {len(df_upload)} linhas em int_siconfi_postprocessed")


def run(uf: str = "PB") -> None:
    print("=" * 60)
    print(" siconfi_postprocessor - Bloco 7")
    print(f" UF: {uf}")
    print("=" * 60)

    print("\n-- Lendo int_eorcam...")
    df_eorcam = _bq("int_eorcam", uf=uf)
    df_eorcam["cod_ibge"] = df_eorcam["cod_ibge"].astype("Int64")
    df_eorcam_m = _eorcam_ponderado(df_eorcam)
    print(f"   {len(df_eorcam_m)} municipios com eorcam_raw")

    print("\n-- Lendo int_lliq_base...")
    df_lliq = _bq("int_lliq_base", uf=uf)
    df_lliq["cod_ibge"] = df_lliq["cod_ibge"].astype("Int64")

    print("\n-- Buscando populacao do mart...")
    df_pop = _bq_mart_pop()
    df_pop["cod_ibge"] = df_pop["cod_ibge"].astype("Int64")

    df_lliq_m = _lliq(df_lliq, df_pop)
    print(f"   {df_lliq_m['lliq_raw'].notna().sum()} municipios com lliq_raw")
    print(f"   {df_lliq_m['lliq_parcial'].sum()} com lliq_parcial (pre-RPNP)")
    print(f"   {df_lliq_m['dado_defasado'].sum()} com dado_defasado")

    print("\n-- Fazendo MERGE em int_siconfi_postprocessed...")
    merged = df_eorcam_m.merge(df_lliq_m, on="cod_ibge", how="outer")
    _merge_bq(merged, uf=uf)

    paths = get_paths(uf)
    csv_anuais = paths["processed"] / f"siconfi_indicadores_{uf.lower()}.csv"
    df_anuais = _bq_anuais(uf=uf)
    df_anuais.to_csv(csv_anuais, index=False)
    print(f"  Exportado local: {csv_anuais.name}")

    csv_resumo = paths["processed"] / f"siconfi_postprocessed_{uf.lower()}.csv"
    merged.to_csv(csv_resumo, index=False)
    print(f"  Exportado local: {csv_resumo.name}")

    print("\nOK siconfi_postprocessor concluido.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="PB")
    args = parser.parse_args()
    run(uf=args.uf)

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

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.scorers.config import (
    FIM_PERIODO_MES,
    ICF_FATOR_SEM_REGISTRO,
    JANELA_RGF_BIMESTRAL,
    JANELA_RGF_SEMESTRAL,
    LIMIAR_LLIQ_SUSPEITO,
    PESOS_EORCAM_ANO,
)
from src.utils.bigquery_loader import (
    get_bigquery_project,
    merge_dataframe_to_table,
    query_to_dataframe,
)
from src.utils.paths import get_artifact_path


DATASET_I = "intermediate"
DATASET_M = "mart"
HOJE = date.today()
ICF_PREFIX_FIELDS = (
    "icf_fator",
    "icf_exercicio",
    "icf_status",
    "icf_conceito",
    "icf_previo",
    "icf_defasado",
    "icf_sem_registro",
)


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


def _bq_icf(uf: str) -> pd.DataFrame:
    return _bq("int_siconfi_icf_resolved", uf=uf)


def _bq_mart_pop() -> pd.DataFrame:
    """Busca populacao do mart para usar no decay."""
    project = _project()
    query = f"SELECT cod_ibge, populacao FROM `{project}.{DATASET_M}.mart_indicadores_municipios`"
    return query_to_dataframe(query, strict=True)


def _preparar_icf(df_icf: pd.DataFrame) -> dict[tuple[int, int], dict]:
    if df_icf.empty:
        return {}

    df = df_icf.copy()
    df["cod_ibge"] = pd.to_numeric(df["cod_ibge"], errors="coerce").astype("Int64")
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")
    df["fator_icf"] = pd.to_numeric(df.get("fator_icf"), errors="coerce").fillna(
        ICF_FATOR_SEM_REGISTRO
    )
    for col in ("icf_previo", "icf_defasado", "icf_sem_registro"):
        if col not in df.columns:
            df[col] = False
        df[col] = df[col].fillna(False).astype(bool)

    lookup = {}
    for row in df.dropna(subset=["cod_ibge", "ano"]).to_dict("records"):
        lookup[(int(row["cod_ibge"]), int(row["ano"]))] = row
    return lookup


def _icf_record(
    lookup: dict[tuple[int, int], dict],
    cod_ibge,
    ano,
    *,
    prefix: str,
) -> dict:
    base = {
        f"{prefix}_icf_fator": ICF_FATOR_SEM_REGISTRO,
        f"{prefix}_icf_exercicio": None,
        f"{prefix}_icf_status": "SEM_ICF",
        f"{prefix}_icf_conceito": "SEM_ICF",
        f"{prefix}_icf_previo": False,
        f"{prefix}_icf_defasado": False,
        f"{prefix}_icf_sem_registro": True,
    }
    if pd.isna(cod_ibge) or pd.isna(ano):
        return base

    row = lookup.get((int(cod_ibge), int(ano)))
    if not row:
        return base

    base.update(
        {
            f"{prefix}_icf_fator": float(row.get("fator_icf") or ICF_FATOR_SEM_REGISTRO),
            f"{prefix}_icf_exercicio": (
                int(row["icf_exercicio"]) if pd.notna(row.get("icf_exercicio")) else None
            ),
            f"{prefix}_icf_status": row.get("status_icf") or "SEM_ICF",
            f"{prefix}_icf_conceito": row.get("conceito_icf") or "SEM_ICF",
            f"{prefix}_icf_previo": bool(row.get("icf_previo", False)),
            f"{prefix}_icf_defasado": bool(row.get("icf_defasado", False)),
            f"{prefix}_icf_sem_registro": bool(row.get("icf_sem_registro", False)),
        }
    )
    return base


def _eorcam_ponderado(df: pd.DataFrame, icf_lookup: dict[tuple[int, int], dict]) -> pd.DataFrame:
    """Media ponderada por exercicios fechados. Grain: cod_ibge."""
    df = df[df["entregou_rreo"] == True].copy()
    df["peso"] = df["ano"].map(PESOS_EORCAM_ANO).fillna(0)
    df = df[df["peso"] > 0]

    if df.empty:
        return pd.DataFrame(
            columns=[
                "cod_ibge",
                "eorcam_raw",
                "eorcam_icf_fator",
                "eorcam_icf_previo",
                "eorcam_icf_defasado",
                "eorcam_icf_sem_registro",
            ]
        )

    icf_rows = [
        _icf_record(icf_lookup, row["cod_ibge"], row["ano"], prefix="eorcam")
        for _, row in df.iterrows()
    ]
    df = pd.concat([df.reset_index(drop=True), pd.DataFrame(icf_rows)], axis=1)

    def _agregar(g: pd.DataFrame) -> pd.Series:
        peso = g["peso"]
        peso_total = peso.sum()
        return pd.Series(
            {
                "eorcam_raw": (g["eorcam_raw"] * peso).sum() / peso_total,
                "eorcam_icf_fator": (g["eorcam_icf_fator"] * peso).sum() / peso_total,
                "eorcam_icf_previo": bool(g["eorcam_icf_previo"].any()),
                "eorcam_icf_defasado": bool(g["eorcam_icf_defasado"].any()),
                "eorcam_icf_sem_registro": bool(g["eorcam_icf_sem_registro"].any()),
            }
        )

    agg = df.groupby("cod_ibge").apply(_agregar, include_groups=False).reset_index()
    agg["eorcam_raw"] = agg["eorcam_raw"].round(6)
    agg["eorcam_icf_fator"] = agg["eorcam_icf_fator"].round(6)
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


def _lliq(
    df: pd.DataFrame,
    df_pop: pd.DataFrame,
    icf_lookup: dict[tuple[int, int], dict],
) -> pd.DataFrame:
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
                    "lliq_ano": int(row["ano"]),
                    "lliq_raw": lliq_raw,
                    "lliq_parcial": parcial,
                    "dias_atraso": dias,
                    "decay_fator": decay,
                    "dado_suspeito_lliq": bool(lliq_raw < LIMIAR_LLIQ_SUSPEITO),
                    "dado_defasado": bool(dias > janela),
                    **_icf_record(icf_lookup, cod_ibge, int(row["ano"]), prefix="lliq"),
                }
            )
            found = True
            break

        if not found:
            records.append(
                {
                    "cod_ibge": cod_ibge,
                    "lliq_ano": None,
                    "lliq_raw": None,
                    "lliq_parcial": False,
                    "dias_atraso": None,
                    "decay_fator": None,
                    "dado_suspeito_lliq": False,
                    "dado_defasado": False,
                    **_icf_record(icf_lookup, cod_ibge, None, prefix="lliq"),
                }
            )

    return pd.DataFrame(records)


def _lliq_vazio(codigos, icf_lookup: dict[tuple[int, int], dict] | None = None) -> pd.DataFrame:
    icf_lookup = icf_lookup or {}
    codigos_unicos = pd.Series(codigos, dtype="Int64").dropna().drop_duplicates().tolist()
    return pd.DataFrame(
        [
            {
                "cod_ibge": cod_ibge,
                "lliq_ano": None,
                "lliq_raw": None,
                "lliq_parcial": False,
                "dias_atraso": None,
                "decay_fator": None,
                "dado_suspeito_lliq": False,
                "dado_defasado": False,
                **_icf_record(icf_lookup, cod_ibge, None, prefix="lliq"),
            }
            for cod_ibge in codigos_unicos
        ]
    )


def _rproc_icf(df_anuais: pd.DataFrame, icf_lookup: dict[tuple[int, int], dict]) -> pd.DataFrame:
    if df_anuais.empty or "rproc_pct" not in df_anuais.columns:
        return pd.DataFrame(
            columns=[
                "cod_ibge",
                "rproc_icf_fator",
                "rproc_icf_previo",
                "rproc_icf_defasado",
                "rproc_icf_sem_registro",
            ]
        )

    df = df_anuais[
        (df_anuais["entregou_rreo"] == True) & df_anuais["rproc_pct"].notna()
    ].copy()
    if df.empty:
        codigos = df_anuais["cod_ibge"].dropna().drop_duplicates()
        return pd.DataFrame(
            {
                "cod_ibge": codigos,
                "rproc_icf_fator": ICF_FATOR_SEM_REGISTRO,
                "rproc_icf_previo": False,
                "rproc_icf_defasado": False,
                "rproc_icf_sem_registro": True,
            }
        )

    icf_rows = [
        _icf_record(icf_lookup, row["cod_ibge"], row["ano"], prefix="rproc")
        for _, row in df.iterrows()
    ]
    df = pd.concat([df.reset_index(drop=True), pd.DataFrame(icf_rows)], axis=1)
    return (
        df.groupby("cod_ibge")
        .agg(
            rproc_icf_fator=("rproc_icf_fator", "mean"),
            rproc_icf_previo=("rproc_icf_previo", "max"),
            rproc_icf_defasado=("rproc_icf_defasado", "max"),
            rproc_icf_sem_registro=("rproc_icf_sem_registro", "max"),
        )
        .reset_index()
    )


def _merge_bq(df: pd.DataFrame, uf: str) -> None:
    project = _project()
    table_ref = f"{project}.{DATASET_I}.int_siconfi_postprocessed"
    temp_ref = f"{project}.{DATASET_M}._tmp_siconfi_post"
    schema_spec = [
        ("cod_ibge", "INT64"),
        ("uf", "STRING"),
        ("eorcam_raw", "FLOAT64"),
        ("eorcam_icf_fator", "FLOAT64"),
        ("eorcam_icf_previo", "BOOL"),
        ("eorcam_icf_defasado", "BOOL"),
        ("eorcam_icf_sem_registro", "BOOL"),
        ("lliq_ano", "INT64"),
        ("lliq_raw", "FLOAT64"),
        ("lliq_parcial", "BOOL"),
        ("dias_atraso", "INT64"),
        ("decay_fator", "FLOAT64"),
        ("dado_suspeito_lliq", "BOOL"),
        ("dado_defasado", "BOOL"),
        ("lliq_icf_fator", "FLOAT64"),
        ("lliq_icf_exercicio", "INT64"),
        ("lliq_icf_status", "STRING"),
        ("lliq_icf_conceito", "STRING"),
        ("lliq_icf_previo", "BOOL"),
        ("lliq_icf_defasado", "BOOL"),
        ("lliq_icf_sem_registro", "BOOL"),
        ("rproc_icf_fator", "FLOAT64"),
        ("rproc_icf_previo", "BOOL"),
        ("rproc_icf_defasado", "BOOL"),
        ("rproc_icf_sem_registro", "BOOL"),
        ("updated_at", "TIMESTAMP"),
    ]

    df_upload = df.copy()
    df_upload["uf"] = uf
    for col, default in {
        "eorcam_icf_fator": ICF_FATOR_SEM_REGISTRO,
        "lliq_icf_fator": ICF_FATOR_SEM_REGISTRO,
        "rproc_icf_fator": ICF_FATOR_SEM_REGISTRO,
        "eorcam_icf_previo": False,
        "eorcam_icf_defasado": False,
        "eorcam_icf_sem_registro": True,
        "lliq_icf_previo": False,
        "lliq_icf_defasado": False,
        "lliq_icf_sem_registro": True,
        "rproc_icf_previo": False,
        "rproc_icf_defasado": False,
        "rproc_icf_sem_registro": True,
    }.items():
        if col not in df_upload.columns:
            df_upload[col] = default

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

    print("\n-- Lendo int_siconfi_icf_resolved...")
    df_icf = _bq_icf(uf=uf)
    icf_lookup = _preparar_icf(df_icf)

    df_eorcam_m = _eorcam_ponderado(df_eorcam, icf_lookup)
    print(f"   {len(df_eorcam_m)} municipios com eorcam_raw")

    print("\n-- Lendo int_lliq_base...")
    df_lliq = _bq("int_lliq_base", uf=uf)

    print("\n-- Buscando populacao do mart...")
    df_pop = _bq_mart_pop()
    df_pop["cod_ibge"] = df_pop["cod_ibge"].astype("Int64")

    if df_lliq.empty or "cod_ibge" not in df_lliq.columns:
        df_lliq_m = _lliq_vazio(
            df_eorcam_m["cod_ibge"] if "cod_ibge" in df_eorcam_m.columns else [],
            icf_lookup,
        )
    else:
        df_lliq["cod_ibge"] = df_lliq["cod_ibge"].astype("Int64")
        df_lliq_m = _lliq(df_lliq, df_pop, icf_lookup)
        if df_lliq_m.empty or "lliq_raw" not in df_lliq_m.columns:
            df_lliq_m = _lliq_vazio(
                df_eorcam_m["cod_ibge"] if "cod_ibge" in df_eorcam_m.columns else [],
                icf_lookup,
            )

    print(f"   {df_lliq_m['lliq_raw'].notna().sum()} municipios com lliq_raw")
    print(f"   {df_lliq_m['lliq_parcial'].sum()} com lliq_parcial (pre-RPNP)")
    print(f"   {df_lliq_m['dado_defasado'].sum()} com dado_defasado")

    print("\n-- Fazendo MERGE em int_siconfi_postprocessed...")
    df_anuais = _bq_anuais(uf=uf)
    df_rproc_icf = _rproc_icf(df_anuais, icf_lookup)
    merged = (
        df_eorcam_m
        .merge(df_lliq_m, on="cod_ibge", how="outer")
        .merge(df_rproc_icf, on="cod_ibge", how="outer")
    )
    _merge_bq(merged, uf=uf)

    csv_anuais = get_artifact_path(uf, "siconfi_indicadores")
    df_anuais.to_csv(csv_anuais, index=False)
    print(f"  Exportado local: {csv_anuais.name}")

    csv_resumo = get_artifact_path(uf, "siconfi_postprocessed")
    merged.to_csv(csv_resumo, index=False)
    print(f"  Exportado local: {csv_resumo.name}")

    print("\nOK siconfi_postprocessor concluido.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="PB")
    args = parser.parse_args()
    run(uf=args.uf)

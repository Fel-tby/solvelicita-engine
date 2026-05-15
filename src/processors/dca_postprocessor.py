"""
dca_postprocessor.py
Le int_autonomia_base do BigQuery.
Calcula:
  - autonomia_media   : media 2020-2024 por municipio
  - autonomia_critica : True se autonomia_media < limiar regional da UF
Atualiza intermediate.int_dca_postprocessed via BigQuery MERGE.
"""

import sys
from pathlib import Path

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.scorers.config import ICF_FATOR_SEM_REGISTRO, get_limiar_autonomia_crit
from src.utils.bigquery_loader import (
    get_bigquery_project,
    merge_dataframe_to_table,
    query_to_dataframe,
)
from src.utils.paths import get_artifact_path


DATASET_I = "intermediate"
DATASET_M = "mart"


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


def _preparar_icf(df_icf: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "cod_ibge",
        "ano",
        "fator_icf",
        "icf_previo",
        "icf_defasado",
        "icf_sem_registro",
    ]
    if df_icf.empty or not {"cod_ibge", "ano"}.issubset(df_icf.columns):
        return pd.DataFrame(columns=cols)

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
    return df[cols].dropna(subset=["cod_ibge", "ano"])


def _calcular_autonomia(df: pd.DataFrame, uf: str, df_icf: pd.DataFrame) -> pd.DataFrame:
    """Grain de saida: cod_ibge."""
    limiar_critico = get_limiar_autonomia_crit(uf)
    df = df.copy()
    df_icf = _preparar_icf(df_icf)
    df = df.merge(df_icf, on=["cod_ibge", "ano"], how="left")
    df["fator_icf"] = pd.to_numeric(df["fator_icf"], errors="coerce").fillna(
        ICF_FATOR_SEM_REGISTRO
    )
    for col, default in {
        "icf_previo": False,
        "icf_defasado": False,
        "icf_sem_registro": True,
    }.items():
        df[col] = df[col].where(df[col].notna(), default).map(bool)

    agg = df.groupby("cod_ibge").agg(
        autonomia_media=("autonomia_raw", "mean"),
        autonomia_icf_fator=("fator_icf", "mean"),
        autonomia_icf_previo=("icf_previo", "max"),
        autonomia_icf_defasado=("icf_defasado", "max"),
        autonomia_icf_sem_registro=("icf_sem_registro", "max"),
    ).reset_index()
    agg["autonomia_icf_fator"] = (
        pd.to_numeric(agg["autonomia_icf_fator"], errors="coerce")
        .fillna(ICF_FATOR_SEM_REGISTRO)
        .round(6)
    )
    agg["autonomia_critica"] = (
        agg["autonomia_media"].notna() &
        (agg["autonomia_media"] < limiar_critico)
    )
    return agg


def _merge_bq(df: pd.DataFrame, uf: str) -> None:
    project = _project()
    table_ref = f"{project}.{DATASET_I}.int_dca_postprocessed"
    temp_ref = f"{project}.{DATASET_M}._tmp_dca_post"
    schema_spec = [
        ("cod_ibge", "INT64"),
        ("uf", "STRING"),
        ("autonomia_media", "FLOAT64"),
        ("autonomia_critica", "BOOL"),
        ("autonomia_icf_fator", "FLOAT64"),
        ("autonomia_icf_previo", "BOOL"),
        ("autonomia_icf_defasado", "BOOL"),
        ("autonomia_icf_sem_registro", "BOOL"),
        ("updated_at", "TIMESTAMP"),
    ]

    df_upload = df.copy()
    df_upload["uf"] = uf
    for col, default in {
        "autonomia_icf_fator": ICF_FATOR_SEM_REGISTRO,
        "autonomia_icf_previo": False,
        "autonomia_icf_defasado": False,
        "autonomia_icf_sem_registro": True,
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
    print(f"  OK MERGE concluido - {len(df_upload)} municipios em int_dca_postprocessed")


def run(uf: str = "PB") -> None:
    print("=" * 60)
    print(" dca_postprocessor - Bloco 7")
    print(f" UF: {uf}")
    print("=" * 60)

    print("\n-- Lendo int_autonomia_base...")
    df = _bq("int_autonomia_base", uf=uf)
    df["cod_ibge"] = df["cod_ibge"].astype("Int64")

    print("\n-- Lendo int_siconfi_icf_resolved...")
    df_icf = _bq("int_siconfi_icf_resolved", uf=uf)
    if "cod_ibge" in df_icf.columns:
        df_icf["cod_ibge"] = df_icf["cod_ibge"].astype("Int64")

    df_m = _calcular_autonomia(df, uf=uf, df_icf=df_icf)
    print(f"   {df_m['autonomia_media'].notna().sum()} municipios com autonomia_media")
    print(f"   {df_m['autonomia_critica'].sum()} com autonomia_critica")

    print("\n-- Fazendo MERGE em int_dca_postprocessed...")
    _merge_bq(df_m, uf=uf)

    csv_path = get_artifact_path(uf, "dca_indicadores")
    df_m.to_csv(csv_path, index=False)
    print(f"  Exportado local: {csv_path.name}")

    print("\nOK dca_postprocessor concluido.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="PB")
    args = parser.parse_args()
    run(uf=args.uf)

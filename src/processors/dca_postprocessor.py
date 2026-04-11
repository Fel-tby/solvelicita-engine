"""
dca_postprocessor.py
Le int_autonomia_base do BigQuery.
Calcula:
  - autonomia_media   : media 2020-2024 por municipio
  - autonomia_critica : True se autonomia_media < 0.08
Atualiza intermediate.int_dca_postprocessed via BigQuery MERGE.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scorers.config import LIMIAR_AUTONOMIA_CRIT
from utils.bigquery_loader import (
    get_bigquery_project,
    merge_dataframe_to_table,
    query_to_dataframe,
)
from utils.paths import get_paths


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


def _calcular_autonomia(df: pd.DataFrame) -> pd.DataFrame:
    """Grain de saida: cod_ibge."""
    agg = (
        df.groupby("cod_ibge")
        .agg(autonomia_media=("autonomia_raw", "mean"))
        .reset_index()
    )
    agg["autonomia_critica"] = (
        agg["autonomia_media"].notna() &
        (agg["autonomia_media"] < LIMIAR_AUTONOMIA_CRIT)
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
    print(f"  OK MERGE concluido - {len(df_upload)} municipios em int_dca_postprocessed")


def run(uf: str = "PB") -> None:
    print("=" * 60)
    print(" dca_postprocessor - Bloco 7")
    print(f" UF: {uf}")
    print("=" * 60)

    print("\n-- Lendo int_autonomia_base...")
    df = _bq("int_autonomia_base", uf=uf)
    df["cod_ibge"] = df["cod_ibge"].astype("Int64")

    df_m = _calcular_autonomia(df)
    print(f"   {df_m['autonomia_media'].notna().sum()} municipios com autonomia_media")
    print(f"   {df_m['autonomia_critica'].sum()} com autonomia_critica")

    print("\n-- Fazendo MERGE em int_dca_postprocessed...")
    _merge_bq(df_m, uf=uf)

    paths = get_paths(uf)
    csv_path = paths["processed"] / f"dca_indicadores_{uf.lower()}.csv"
    df_m.to_csv(csv_path, index=False)
    print(f"  Exportado local: {csv_path.name}")

    print("\nOK dca_postprocessor concluido.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="PB")
    args = parser.parse_args()
    run(uf=args.uf)

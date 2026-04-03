"""
dca_postprocessor.py
Lê int_autonomia_base do BigQuery.
Calcula:
  - autonomia_media   : média 2020–2024 por município
  - autonomia_critica : True se autonomia_media < 0.08
Atualiza mart.mart_indicadores_municipios via BigQuery MERGE.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery
from utils.paths import get_paths
from scorers.config import LIMIAR_AUTONOMIA_CRIT

load_dotenv()
if key := os.getenv("GCP_SA_KEY_PATH"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key

PROJECT      = "solvelicita"
DATASET_I    = "intermediate"
DATASET_M    = "mart"
TABLE_TARGET = f"{PROJECT}.{DATASET_I}.int_dca_postprocessed"

def _bq(client: bigquery.Client, table: str, uf: str) -> pd.DataFrame:
    query = f"""
        SELECT t.* 
        FROM `{PROJECT}.{DATASET_I}.{table}` t
        JOIN `{PROJECT}.staging.stg_municipios` m 
          ON t.cod_ibge = m.cod_ibge
        WHERE m.uf = '{uf}'
    """
    return client.query(query).to_dataframe()


def _calcular_autonomia(df: pd.DataFrame) -> pd.DataFrame:
    """Grain de saída: cod_ibge."""
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


def _merge_bq(client: bigquery.Client, df: pd.DataFrame, uf: str) -> None:
    # Schema da tabela destino
    schema_target = [
        bigquery.SchemaField("cod_ibge", "INT64"),
        bigquery.SchemaField("uf", "STRING"),
        bigquery.SchemaField("autonomia_media", "FLOAT64"),
        bigquery.SchemaField("autonomia_critica", "BOOL"),
        bigquery.SchemaField("updated_at", "TIMESTAMP"),
    ]
    table = bigquery.Table(TABLE_TARGET, schema=schema_target)
    client.create_table(table, exists_ok=True)

    # Schema da tabela temporária (sem updated_at)
    schema_tmp = [f for f in schema_target if f.name != "updated_at"]

    df["uf"] = uf
    tmp = f"{PROJECT}.{DATASET_M}._tmp_dca_post"

    job = client.load_table_from_dataframe(
        df, tmp,
        job_config=bigquery.LoadJobConfig(
            write_disposition="WRITE_TRUNCATE",
            schema=schema_tmp
        )
    )
    job.result()

    merge_sql = f"""
    MERGE `{TABLE_TARGET}` T
    USING `{tmp}` S ON T.cod_ibge = S.cod_ibge
    WHEN MATCHED THEN UPDATE SET
        T.uf                 = S.uf,
        T.autonomia_media    = S.autonomia_media,
        T.autonomia_critica  = S.autonomia_critica,
        T.updated_at         = CURRENT_TIMESTAMP()
    WHEN NOT MATCHED THEN INSERT (
        cod_ibge, uf, autonomia_media, autonomia_critica, updated_at
    ) VALUES (
        S.cod_ibge, S.uf, S.autonomia_media, S.autonomia_critica, CURRENT_TIMESTAMP()
    )
    """
    client.query(merge_sql).result()
    client.delete_table(tmp, not_found_ok=True)
    print(f"  ✅ MERGE concluído — {len(df)} municípios em int_dca_postprocessed")


def run(uf: str = "PB") -> None:
    print("=" * 60)
    print(" dca_postprocessor — Bloco 7")
    print(f" UF: {uf}")
    print("=" * 60)

    client = bigquery.Client(project=PROJECT)

    print("\n── Lendo int_autonomia_base...")
    df = _bq(client, "int_autonomia_base", uf=uf)
    df["cod_ibge"] = df["cod_ibge"].astype("Int64")

    df_m = _calcular_autonomia(df)
    print(f"   {df_m['autonomia_media'].notna().sum()} municípios com autonomia_media")
    print(f"   {df_m['autonomia_critica'].sum()} com autonomia_critica")

    print("\n── Fazendo MERGE em int_dca_postprocessed...")
    _merge_bq(client, df_m, uf=uf)

    # Exportação Local (Audit)
    paths = get_paths(uf)
    csv_path = paths["processed"] / f"dca_indicadores_{uf.lower()}.csv"
    df_m.to_csv(csv_path, index=False)
    print(f"  💾 Exportado local: {csv_path.name}")

    print("\n✅ dca_postprocessor concluído.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="PB")
    args = parser.parse_args()
    run(uf=args.uf)

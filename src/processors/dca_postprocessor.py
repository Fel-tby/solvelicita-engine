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
from scorers.config import LIMIAR_AUTONOMIA_CRIT

load_dotenv()
if key := os.getenv("GCP_SA_KEY_PATH"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key

PROJECT    = "solvelicita"
DATASET_I  = "intermediate"
DATASET_M  = "mart"
TABLE_MART = f"{PROJECT}.{DATASET_M}.mart_indicadores_municipios"

def _bq(client: bigquery.Client, table: str) -> pd.DataFrame:
    return client.query(
        f"SELECT * FROM `{PROJECT}.{DATASET_I}.{table}`"
    ).to_dataframe()


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


def _merge_bq(client: bigquery.Client, df: pd.DataFrame) -> None:
    tmp = f"{PROJECT}.{DATASET_M}._tmp_dca_post"

    job = client.load_table_from_dataframe(
        df, tmp,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    )
    job.result()

    merge_sql = f"""
    MERGE `{TABLE_MART}` T
    USING `{tmp}` S ON T.cod_ibge = S.cod_ibge
    WHEN MATCHED THEN UPDATE SET
        T.autonomia_media    = S.autonomia_media,
        T.autonomia_critica  = S.autonomia_critica,
        T.updated_at         = CURRENT_TIMESTAMP()
    """
    client.query(merge_sql).result()
    client.delete_table(tmp, not_found_ok=True)
    print(f"  ✅ MERGE concluído — {len(df)} municípios")


def run() -> None:
    print("=" * 60)
    print(" dca_postprocessor — Bloco 7")
    print("=" * 60)

    client = bigquery.Client(project=PROJECT)

    print("\n── Lendo int_autonomia_base...")
    df = _bq(client, "int_autonomia_base")
    df["cod_ibge"] = df["cod_ibge"].astype("Int64")

    df_m = _calcular_autonomia(df)
    print(f"   {df_m['autonomia_media'].notna().sum()} municípios com autonomia_media")
    print(f"   {df_m['autonomia_critica'].sum()} com autonomia_critica")

    print("\n── Fazendo merge no mart...")
    _merge_bq(client, df_m)

    print("\n✅ dca_postprocessor concluído.")


if __name__ == "__main__":
    run()
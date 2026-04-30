"""
Executa uma query minima no BigQuery para verificar se o custo e abatido dos
creditos da billing account ativa do projeto.

Uso:
    python scripts/bq_credit_probe.py

Configuracoes opcionais:
    BQ_PROBE_PROJECT=solvelicita
    BQ_PROBE_LOCATION=southamerica-east1
    BQ_PROBE_MAX_BYTES=10485760
"""

from __future__ import annotations

import os
from pathlib import Path

from google.cloud import bigquery
from google.oauth2 import service_account


PROJECT_ID = os.getenv("BQ_PROBE_PROJECT", "solvelicita")
LOCATION = os.getenv("BQ_PROBE_LOCATION", "southamerica-east1")
MAX_BYTES = int(os.getenv("BQ_PROBE_MAX_BYTES", str(10 * 1024 * 1024)))
ROOT_DIR = Path(__file__).resolve().parents[1]


def _credentials():
    candidates = [
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        os.getenv("GCP_SA_KEY_PATH"),
        str(ROOT_DIR / "gcp-credentials.json"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            creds = service_account.Credentials.from_service_account_file(path)
            return creds, str(path)
    return None, "Application Default Credentials"


def main() -> None:
    credentials, credentials_source = _credentials()
    client = bigquery.Client(
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials,
    )
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES,
        use_legacy_sql=False,
    )
    sql = """
    SELECT COUNT(*) AS n_jobs
    FROM `region-southamerica-east1`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
    """

    job = client.query(sql, job_config=job_config)
    rows = list(job.result())
    billed = job.total_bytes_billed or 0

    print(f"project_id: {PROJECT_ID}")
    print(f"location: {LOCATION}")
    print(f"credentials: {credentials_source}")
    print(f"n_jobs: {rows[0]['n_jobs']}")
    print(f"job_id: {job.job_id}")
    print(f"bytes_billed: {billed}")
    print(f"gib_billed: {billed / 1024**3:.9f}")
    print()
    print("Confira no Console: Billing > Reports > Today > Service = BigQuery.")
    print("O esperado e ver custo bruto pequeno com credito aplicado e valor a pagar zero.")


if __name__ == "__main__":
    main()

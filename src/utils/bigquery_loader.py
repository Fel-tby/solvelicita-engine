"""
bigquery_loader.py - Interface unica de leitura/escrita no BigQuery.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from uuid import uuid4

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent

_CSV_FALLBACK: dict[str, str] = {
    "mart_indicadores_municipios": "data/processed/PB/mart_indicadores_pb.csv",
    "mart_pncp_municipios": "data/outputs/PB/score_municipios_pb_pncp.csv",
    "score_municipios": "data/outputs/PB/score_municipios_pb.csv",
}

_client = None
_BQ_AVAILABLE = None


def _check_bq_available() -> bool:
    global _BQ_AVAILABLE
    if _BQ_AVAILABLE is not None:
        return _BQ_AVAILABLE
    try:
        import google.cloud.bigquery  # noqa: F401
        _BQ_AVAILABLE = True
    except ImportError:
        _BQ_AVAILABLE = False
    return _BQ_AVAILABLE


def _cfg() -> dict:
    return {
        "project": os.getenv("GCP_PROJECT_ID", "solvelicita"),
        "sa_path": os.getenv("GCP_SA_KEY_PATH", ""),
        "dataset": os.getenv("BQ_DATASET", "raw"),
        "enabled": os.getenv("BQ_ENABLED", "false").lower() == "true",
    }


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not _check_bq_available():
        raise RuntimeError(
            "google-cloud-bigquery nao instalado. "
            "Execute: pip install google-cloud-bigquery"
        )
    from google.cloud import bigquery
    from google.oauth2 import service_account

    cfg = _cfg()
    sa_path = cfg["sa_path"]
    if sa_path and Path(sa_path).exists():
        creds = service_account.Credentials.from_service_account_file(sa_path)
        _client = bigquery.Client(project=cfg["project"], credentials=creds)
    else:
        _client = bigquery.Client(project=cfg["project"])
    return _client


def is_bigquery_enabled() -> bool:
    cfg = _cfg()
    return bool(cfg["enabled"] and _check_bq_available() and cfg["sa_path"])


def get_bigquery_client():
    if not is_bigquery_enabled():
        raise RuntimeError(
            "BigQuery nao esta habilitado ou configurado no ambiente atual."
        )
    return _get_client()


def get_bigquery_project() -> str:
    return _cfg()["project"]


def _sanitize_column_name(name: str, index: int) -> str:
    value = re.sub(r"[^a-zA-Z0-9_]", "_", str(name)).lower()
    if value and value[0].isdigit():
        value = "c_" + value
    value = re.sub(r"^_+", "", value) or f"col_{index}"
    return value


def _sanitize(df: pd.DataFrame, uf: str) -> pd.DataFrame:
    """
    Prepara o DataFrame para upload no BigQuery:
    - Remove colunas duplicadas
    - Sanitiza nomes de colunas
    - Garante coluna uf consistente
    - Serializa dict/list para JSON
    - Converte tudo para STRING
    """
    df = df.loc[:, ~df.columns.duplicated()].copy()

    new_cols = []
    seen = {}
    for i, col in enumerate(df.columns):
        name = _sanitize_column_name(str(col), i)
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        new_cols.append(name)
    df.columns = new_cols

    if "uf" not in df.columns:
        df["uf"] = uf.upper()
    else:
        df["uf"] = df["uf"].fillna(uf.upper()).astype(str).str.upper()

    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: json.dumps(x, ensure_ascii=False)
            if isinstance(x, (dict, list))
            else x
        )

    df = df.astype(str)
    df = df.replace({"nan": None, "None": None, "NaT": None, "<NA>": None})
    return df


def _normalize_key_columns(key_cols: list[str]) -> list[str]:
    return [_sanitize_column_name(col, i) for i, col in enumerate(key_cols)]


def _validate_keys(df: pd.DataFrame, key_cols: list[str], uf: str) -> None:
    missing = [col for col in key_cols if col not in df.columns]
    if missing:
        raise ValueError(
            f"Chaves de merge ausentes apos sanitizacao: {', '.join(missing)}"
        )

    for col in key_cols:
        invalid = df[col].isna() | (df[col].astype(str).str.strip() == "")
        if invalid.any():
            raise ValueError(
                f"Coluna-chave '{col}' contem valores nulos/vazios em {int(invalid.sum())} linhas."
            )

    uf_values = sorted(set(df["uf"].dropna().astype(str).str.upper()))
    if uf_values != [uf.upper()]:
        raise ValueError(
            f"UF inconsistente na carga: esperado '{uf.upper()}', encontrado {uf_values}"
        )


def _dedupe_by_keys(df: pd.DataFrame, key_cols: list[str], table: str, uf: str) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="last").reset_index(drop=True)
    removed = before - len(df)
    if removed:
        logger.info(
            "[BQ] dedupe antes do merge: %s.%s uf=%s duplicatas_removidas=%d",
            _cfg()["dataset"], table, uf.upper(), removed,
        )
        print(f"  [BQ] dedupe: {removed:,} duplicatas removidas antes do merge")
    return df


def _build_merge_sql(target_ref: str, temp_ref: str, cols: list[str], key_cols: list[str]) -> str:
    on_clause = " AND ".join([f"T.`{col}` = S.`{col}`" for col in key_cols])
    update_cols = [col for col in cols if col not in []]
    update_clause = ", ".join([f"`{col}` = S.`{col}`" for col in update_cols])
    insert_cols = ", ".join([f"`{col}`" for col in cols])
    insert_vals = ", ".join([f"S.`{col}`" for col in cols])
    return f"""
MERGE `{target_ref}` T
USING `{temp_ref}` S
ON {on_clause}
WHEN MATCHED THEN
  UPDATE SET {update_clause}
WHEN NOT MATCHED THEN
  INSERT ({insert_cols})
  VALUES ({insert_vals})
""".strip()


def _ensure_target_table(client, target_ref: str, cols: list[str]) -> None:
    from google.cloud import bigquery
    from google.api_core.exceptions import NotFound

    try:
        table = client.get_table(target_ref)
        existing = {field.name for field in table.schema}
    except NotFound:
        schema = [bigquery.SchemaField(col, "STRING") for col in cols]
        client.create_table(bigquery.Table(target_ref, schema=schema))
        existing = set(cols)

    missing = [col for col in cols if col not in existing]
    for col in missing:
        sql = f"ALTER TABLE `{target_ref}` ADD COLUMN IF NOT EXISTS `{col}` STRING"
        client.query(sql).result()


def upload_raw(
    df: pd.DataFrame,
    table: str,
    uf: str,
    write_mode: str = "append",
) -> None:
    """
    Faz upload simples de um DataFrame para a camada raw do BigQuery.
    Mantido para casos que ainda nao migraram para staging + MERGE.
    """
    cfg = _cfg()

    if not cfg["enabled"] or not _check_bq_available() or not cfg["sa_path"]:
        logger.info(
            "[BQ stub] upload_raw ignorado: table=%s.%s uf=%s linhas=%d",
            cfg["dataset"], table, uf.upper(), len(df),
        )
        return

    from google.cloud import bigquery

    client = _get_client()
    table_ref = f"{cfg['project']}.{cfg['dataset']}.{table}"
    bq_mode = (
        bigquery.WriteDisposition.WRITE_APPEND
        if write_mode == "append"
        else bigquery.WriteDisposition.WRITE_TRUNCATE
    )

    df_upload = _sanitize(df, uf)

    schema = [bigquery.SchemaField(col, "STRING") for col in df_upload.columns]
    job_config = bigquery.LoadJobConfig(
        write_disposition=bq_mode,
        schema=schema,
    )

    job = client.load_table_from_dataframe(df_upload, table_ref, job_config=job_config)
    job.result()
    logger.info("[BQ] upload_raw: %s (%d linhas)", table_ref, len(df_upload))
    print(f"  [BQ] {table_ref}: {len(df_upload):,} linhas enviadas")


def publish_raw_merge(
    df: pd.DataFrame,
    table: str,
    uf: str,
    key_cols: list[str],
) -> None:
    """
    Publicacao segura para raw.* via staging temporaria + MERGE no alvo final.
    - nao faz truncate/delete na tabela final
    - valida UF/chaves antes de publicar
    - deduplica o lote pela chave natural
    """
    cfg = _cfg()

    if df.empty:
        print(f"  [BQ] aviso: lote vazio para raw.{table} ({uf.upper()})")
        return

    if not cfg["enabled"] or not _check_bq_available() or not cfg["sa_path"]:
        logger.info(
            "[BQ stub] publish_raw_merge ignorado: table=%s.%s uf=%s linhas=%d",
            cfg["dataset"], table, uf.upper(), len(df),
        )
        return

    from google.cloud import bigquery

    df_upload = _sanitize(df, uf)
    key_cols_norm = _normalize_key_columns(key_cols)
    _validate_keys(df_upload, key_cols_norm, uf)
    df_upload = _dedupe_by_keys(df_upload, key_cols_norm, table, uf)

    client = _get_client()
    target_ref = f"{cfg['project']}.{cfg['dataset']}.{table}"
    temp_ref = (
        f"{cfg['project']}.{cfg['dataset']}."
        f"__tmp_{table}_{uf.lower()}_{int(time.time())}_{uuid4().hex[:8]}"
    )

    schema = [bigquery.SchemaField(col, "STRING") for col in df_upload.columns]
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=schema,
    )

    try:
        load_job = client.load_table_from_dataframe(df_upload, temp_ref, job_config=job_config)
        load_job.result()

        _ensure_target_table(client, target_ref, list(df_upload.columns))

        merge_sql = _build_merge_sql(
            target_ref=target_ref,
            temp_ref=temp_ref,
            cols=list(df_upload.columns),
            key_cols=key_cols_norm,
        )
        client.query(merge_sql).result()
        logger.info(
            "[BQ] publish_raw_merge: %s uf=%s linhas=%d",
            target_ref, uf.upper(), len(df_upload),
        )
        print(
            f"  [BQ] merge seguro concluido: {target_ref} | "
            f"uf={uf.upper()} | linhas={len(df_upload):,}"
        )
    finally:
        client.delete_table(temp_ref, not_found_ok=True)


def read_mart(table: str, uf: str | None = None) -> pd.DataFrame:
    """
    Le uma tabela do mart do BigQuery.
    Fallback para CSV local quando BigQuery nao esta disponivel.
    """
    cfg = _cfg()

    if not cfg["enabled"] or not _check_bq_available() or not cfg["sa_path"]:
        return _read_mart_csv_fallback(table, uf)

    client = _get_client()
    table_ref = f"{cfg['project']}.mart.{table}"
    uf_filter = f"WHERE uf = '{uf.upper()}'" if uf else ""
    query = f"SELECT * FROM `{table_ref}` {uf_filter}"

    logger.info("[BQ] read_mart: %s uf=%s", table_ref, uf or "nacional")
    return client.query(query).to_dataframe()


def read_intermediate(table: str, uf: str | None = None) -> pd.DataFrame:
    """
    Le uma tabela da camada intermediate do BigQuery.
    Retorna DataFrame vazio quando BigQuery nao esta disponivel.
    """
    cfg = _cfg()

    if not cfg["enabled"] or not _check_bq_available() or not cfg["sa_path"]:
        logger.warning(
            "[BQ stub] read_intermediate ignorado - sem fallback CSV para '%s'. "
            "Retornando DataFrame vazio.",
            table,
        )
        return pd.DataFrame()

    client = _get_client()
    table_ref = f"{cfg['project']}.intermediate.{table}"
    uf_filter = f"WHERE uf = '{uf.upper()}'" if uf else ""
    query = f"SELECT * FROM `{table_ref}` {uf_filter}"

    logger.info("[BQ] read_intermediate: %s uf=%s", table_ref, uf or "nacional")
    return client.query(query).to_dataframe()


def _read_mart_csv_fallback(table: str, uf: str | None) -> pd.DataFrame:
    rel_path = _CSV_FALLBACK.get(table)
    if not rel_path:
        logger.warning(
            "[BQ stub] Sem fallback CSV para tabela '%s'. Retornando DataFrame vazio.",
            table,
        )
        return pd.DataFrame()

    if uf and uf.upper() != "PB":
        rel_path = rel_path.replace("/PB/", f"/{uf.upper()}/")

    full_path = _ROOT / rel_path
    if not full_path.exists():
        logger.warning(
            "[BQ stub] Fallback CSV nao encontrado: %s. Retornando DataFrame vazio.",
            full_path,
        )
        return pd.DataFrame()

    logger.info("[BQ stub] read_mart via CSV local: %s", full_path.name)
    return pd.read_csv(full_path, dtype={"cod_ibge": str})

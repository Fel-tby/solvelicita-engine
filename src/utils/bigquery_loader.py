"""
bigquery_loader.py - Interface unica de leitura/escrita no BigQuery.
"""

import json
import logging
import os
import re
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4

import pandas as pd

from src.config.settings import get_bigquery_settings
from src.utils.paths import get_bigquery_csv_fallback_paths

logger = logging.getLogger(__name__)

_client = None
_BQ_AVAILABLE = None

BYTES_PER_GIB = 1024 ** 3
DEFAULT_MERGE_MAX_GIB_BY_TABLE = {
    "cauc": 0.5,
    "dim_municipios": 0.5,
    "dca": 2.0,
    "pncp": 5.0,
    "siconfi_rgf": 2.0,
    "siconfi_rreo": 10.0,
}
DEFAULT_REPLACE_SLICE_MAX_GIB_BY_TABLE = {
    "siconfi_icf": 0.5,
    "siconfi_rgf": 1.0,
    "siconfi_rreo": 2.0,
}
RAW_MERGE_BLOCKLIST = {"siconfi_icf", "siconfi_rgf", "siconfi_rreo"}
SICONFI_TYPED_FIELDS = {
    "dim_i": "NUMERIC",
    "dim_ii": "NUMERIC",
    "dim_iii": "NUMERIC",
    "dim_iv": "NUMERIC",
    "edicao_ranking": "INT64",
    "exercicio": "INT64",
    "fator_icf": "NUMERIC",
    "periodo": "INT64",
    "percentual_acertos": "NUMERIC",
    "populacao": "INT64",
    "posicao_ranking": "INT64",
    "total_pontos": "NUMERIC",
    "valor": "NUMERIC",
}
BQ_NUMERIC_SCALE = Decimal("0.000000001")


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
    cfg = get_bigquery_settings()
    return {
        "project": cfg.project_id,
        "sa_path": cfg.resolved_sa_key_path_str,
        "dataset": cfg.dataset,
        "enabled": cfg.enabled,
    }


def _env_float(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Variavel de ambiente {name} deve ser numerica: {raw!r}") from exc


def _merge_max_gib_for_table(table: str) -> float | None:
    specific = _env_float(f"BQ_MERGE_MAX_GIB_{table.upper()}")
    if specific is not None:
        return specific

    default = _env_float("BQ_MERGE_MAX_GIB_DEFAULT")
    if default is not None:
        return default

    return DEFAULT_MERGE_MAX_GIB_BY_TABLE.get(table)


def _is_raw_merge_blocked(table: str) -> bool:
    return table in RAW_MERGE_BLOCKLIST or any(
        table.startswith(f"{blocked}_") for blocked in RAW_MERGE_BLOCKLIST
    )


def _is_siconfi_table(table: str) -> bool:
    return table.startswith("siconfi_")


def _ensure_raw_merge_allowed(table: str) -> None:
    if not _is_raw_merge_blocked(table):
        return

    raise RuntimeError(
        f"MERGE bloqueado para raw.{table}. Use replace-slice por uf/exercicio "
        "para SICONFI; MERGE nessa raw pode varrer a tabela nacional inteira."
    )


def _replace_slice_max_gib_for_table(table: str) -> float | None:
    specific = _env_float(f"BQ_REPLACE_SLICE_MAX_GIB_{table.upper()}")
    if specific is not None:
        return specific

    default = _env_float("BQ_REPLACE_SLICE_MAX_GIB_DEFAULT")
    if default is not None:
        return default

    return DEFAULT_REPLACE_SLICE_MAX_GIB_BY_TABLE.get(table)


def _build_query_job_config_for_merge(table: str):
    max_gib = _merge_max_gib_for_table(table)
    if max_gib is None or max_gib <= 0:
        return None

    bigquery = _import_bigquery()
    return bigquery.QueryJobConfig(
        maximum_bytes_billed=int(max_gib * BYTES_PER_GIB)
    )


def _build_query_job_config_for_replace_slice(table: str, query_parameters: list | None = None):
    max_gib = _replace_slice_max_gib_for_table(table)
    if (max_gib is None or max_gib <= 0) and not query_parameters:
        return None

    bigquery = _import_bigquery()
    kwargs = {}
    if max_gib is not None and max_gib > 0:
        kwargs["maximum_bytes_billed"] = int(max_gib * BYTES_PER_GIB)
    if query_parameters:
        kwargs["query_parameters"] = query_parameters
    return bigquery.QueryJobConfig(**kwargs)


def _job_billed_gib(job) -> float | None:
    billed = getattr(job, "total_bytes_billed", None)
    if billed is None:
        return None
    return billed / BYTES_PER_GIB


def _print_merge_cost(*, target_ref: str, uf: str, rows: int, job) -> None:
    billed_gib = _job_billed_gib(job)
    job_id = getattr(job, "job_id", "")
    if billed_gib is None:
        print(
            f"  [BQ] merge seguro concluido: {target_ref} | "
            f"uf={uf.upper()} | linhas={rows:,} | job={job_id}"
        )
        return

    print(
        f"  [BQ] merge seguro concluido: {target_ref} | "
        f"uf={uf.upper()} | linhas={rows:,} | billed={billed_gib:.3f} GiB | job={job_id}"
    )


def _print_replace_slice_cost(*, target_ref: str, uf: str, rows: int, slice_summary: str, job) -> None:
    billed_gib = _job_billed_gib(job)
    job_id = getattr(job, "job_id", "")
    if billed_gib is None:
        print(
            f"  [BQ] replace-slice concluido: {target_ref} | "
            f"uf={uf.upper()} | {slice_summary} | linhas={rows:,} | job={job_id}"
        )
        return

    print(
        f"  [BQ] replace-slice concluido: {target_ref} | "
        f"uf={uf.upper()} | {slice_summary} | linhas={rows:,} | "
        f"billed={billed_gib:.3f} GiB | job={job_id}"
    )


def _print_append_slice_cost(*, target_ref: str, uf: str, rows: int, slice_summary: str, job) -> None:
    job_id = getattr(job, "job_id", "")
    print(
        f"  [BQ] append-slice concluido: {target_ref} | "
        f"uf={uf.upper()} | {slice_summary} | linhas={rows:,} | job={job_id}"
    )


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


def _import_bigquery():
    if not _check_bq_available():
        raise RuntimeError(
            "google-cloud-bigquery nao instalado. "
            "Execute: pip install google-cloud-bigquery"
        )
    from google.cloud import bigquery

    return bigquery


def _ensure_bigquery_readable(layer: str, table: str, uf: str | None = None) -> None:
    if is_bigquery_enabled():
        return

    target = f"{layer}.{table}"
    scope = f" uf={uf.upper()}" if uf else ""
    raise RuntimeError(
        "Leitura canonica via BigQuery indisponivel para "
        f"{target}{scope}. Verifique BQ_ENABLED, GCP_SA_KEY_PATH e as credenciais."
    )


def _sanitize_column_name(name: str, index: int) -> str:
    value = re.sub(r"[^a-zA-Z0-9_]", "_", str(name)).lower()
    if value and value[0].isdigit():
        value = "c_" + value
    value = re.sub(r"^_+", "", value) or f"col_{index}"
    return value


def query_to_dataframe(query: str, *, strict: bool = True) -> pd.DataFrame:
    """
    Executa uma consulta SQL no BigQuery e retorna DataFrame.
    Em modo estrito, falha cedo se o BigQuery nao estiver disponivel.
    """
    if not is_bigquery_enabled():
        if strict:
            raise RuntimeError(
                "BigQuery nao esta habilitado ou configurado para executar consultas."
            )
        logger.warning("[BQ stub] query_to_dataframe ignorado; retornando DataFrame vazio.")
        return pd.DataFrame()

    client = _get_client()
    try:
        return client.query(query).to_dataframe()
    except Exception as exc:
        if strict:
            raise RuntimeError("Falha ao executar consulta no BigQuery.") from exc
        raise


def _schema_fields_from_spec(schema_spec: list[tuple[str, str]]):
    bigquery = _import_bigquery()
    return [bigquery.SchemaField(name, field_type) for name, field_type in schema_spec]


def ensure_typed_table(table_ref: str, schema_spec: list[tuple[str, str]]) -> None:
    """
    Garante a existencia da tabela com schema tipado, adicionando colunas faltantes.
    """
    if not is_bigquery_enabled():
        raise RuntimeError(
            f"BigQuery nao esta habilitado para garantir schema da tabela {table_ref}."
        )

    client = _get_client()
    bigquery = _import_bigquery()

    from google.api_core.exceptions import NotFound

    spec_map = {name: field_type for name, field_type in schema_spec}

    try:
        table = client.get_table(table_ref)
        existing = {field.name: field.field_type for field in table.schema}
    except NotFound:
        schema = _schema_fields_from_spec(schema_spec)
        client.create_table(bigquery.Table(table_ref, schema=schema))
        existing = spec_map

    missing = [name for name in spec_map if name not in existing]
    for name in missing:
        sql = (
            f"ALTER TABLE `{table_ref}` "
            f"ADD COLUMN IF NOT EXISTS `{name}` {spec_map[name]}"
        )
        client.query(sql).result()


def merge_dataframe_to_table(
    df: pd.DataFrame,
    *,
    table_ref: str,
    schema_spec: list[tuple[str, str]],
    key_cols: list[str],
    temp_table_ref: str | None = None,
    extra_update_assignments: dict[str, str] | None = None,
    extra_insert_values: dict[str, str] | None = None,
) -> None:
    """
    Faz MERGE tipado de um DataFrame em uma tabela BigQuery via staging temporaria.
    """
    if not is_bigquery_enabled():
        raise RuntimeError(
            f"BigQuery nao esta habilitado para MERGE na tabela {table_ref}."
        )
    if df.empty:
        logger.warning("[BQ] merge_dataframe_to_table recebeu DataFrame vazio para %s", table_ref)
        return

    for col in key_cols:
        if col not in df.columns:
            raise ValueError(f"Coluna-chave ausente para MERGE tipado: {col}")

    client = _get_client()
    bigquery = _import_bigquery()
    ensure_typed_table(table_ref, schema_spec)

    if temp_table_ref is None:
        temp_table_ref = (
            f"{table_ref.rsplit('.', 1)[0]}."
            f"__tmp_merge_{int(time.time())}_{uuid4().hex[:8]}"
        )

    schema_map = {name: field_type for name, field_type in schema_spec}
    temp_spec = [(name, schema_map[name]) for name in df.columns if name in schema_map]
    temp_schema = [bigquery.SchemaField(name, field_type) for name, field_type in temp_spec]

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=temp_schema,
    )

    extra_update_assignments = extra_update_assignments or {}
    extra_insert_values = extra_insert_values or {}

    update_cols = [col for col in df.columns if col not in key_cols]
    update_parts = [f"T.`{col}` = S.`{col}`" for col in update_cols]
    update_parts.extend(
        [f"T.`{col}` = {expression}" for col, expression in extra_update_assignments.items()]
    )

    insert_cols = list(df.columns) + list(extra_insert_values.keys())
    insert_vals = [f"S.`{col}`" for col in df.columns]
    insert_vals.extend(extra_insert_values.values())

    on_clause = " AND ".join([f"T.`{col}` = S.`{col}`" for col in key_cols])
    merge_sql = f"""
MERGE `{table_ref}` T
USING `{temp_table_ref}` S
ON {on_clause}
WHEN MATCHED THEN
  UPDATE SET {", ".join(update_parts)}
WHEN NOT MATCHED THEN
  INSERT ({", ".join([f"`{col}`" for col in insert_cols])})
  VALUES ({", ".join(insert_vals)})
""".strip()

    try:
        client.load_table_from_dataframe(df.copy(), temp_table_ref, job_config=job_config).result()
        table_name = table_ref.rsplit(".", 1)[-1]
        query_job = client.query(
            merge_sql,
            job_config=_build_query_job_config_for_merge(table_name),
        )
        query_job.result()
        _print_merge_cost(
            target_ref=table_ref,
            uf="",
            rows=len(df),
            job=query_job,
        )
    finally:
        client.delete_table(temp_table_ref, not_found_ok=True)


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


def _to_decimal_or_none(value) -> Decimal | None:
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()
    if text == "":
        return None

    try:
        numeric = Decimal(text.replace(",", "."))
        return numeric.quantize(BQ_NUMERIC_SCALE, rounding=ROUND_HALF_UP).normalize()
    except InvalidOperation as exc:
        raise ValueError(f"Valor NUMERIC invalido para BigQuery: {value!r}") from exc


def _coerce_raw_upload_types(df: pd.DataFrame, table: str) -> tuple[pd.DataFrame, dict[str, str]]:
    if not _is_siconfi_table(table):
        return df, {}

    df = df.copy()
    schema_types = {
        col: field_type
        for col, field_type in SICONFI_TYPED_FIELDS.items()
        if col in df.columns
    }

    for col, field_type in schema_types.items():
        if field_type == "INT64":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        elif field_type == "NUMERIC":
            df[col] = df[col].apply(_to_decimal_or_none)

    return df, schema_types


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


def _build_replace_slice_sql(
    target_ref: str,
    temp_ref: str,
    cols: list[str],
    slice_cols: list[str],
) -> str:
    predicates = ["`uf` = @uf"]
    for col in slice_cols:
        predicates.append(f"`{col}` IN UNNEST(@slice_{col})")

    insert_cols = ", ".join([f"`{col}`" for col in cols])
    select_cols = ", ".join([f"`{col}`" for col in cols])
    delete_where = " AND ".join(predicates)
    return f"""
BEGIN TRANSACTION;

DELETE FROM `{target_ref}`
WHERE {delete_where};

INSERT INTO `{target_ref}` ({insert_cols})
SELECT {select_cols}
FROM `{temp_ref}`;

COMMIT TRANSACTION;
""".strip()


def _ensure_target_table(
    client,
    target_ref: str,
    cols: list[str],
    schema_types: dict[str, str] | None = None,
) -> None:
    from google.cloud import bigquery
    from google.api_core.exceptions import NotFound

    schema_types = schema_types or {}

    try:
        table = client.get_table(target_ref)
        existing = {field.name for field in table.schema}
    except NotFound:
        schema = [bigquery.SchemaField(col, schema_types.get(col, "STRING")) for col in cols]
        client.create_table(bigquery.Table(target_ref, schema=schema))
        existing = set(cols)

    missing = [col for col in cols if col not in existing]
    for col in missing:
        sql = (
            f"ALTER TABLE `{target_ref}` "
            f"ADD COLUMN IF NOT EXISTS `{col}` {schema_types.get(col, 'STRING')}"
        )
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
    _ensure_raw_merge_allowed(table)
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
        query_job = client.query(
            merge_sql,
            job_config=_build_query_job_config_for_merge(table),
        )
        query_job.result()
        logger.info(
            "[BQ] publish_raw_merge: %s uf=%s linhas=%d billed_gib=%s",
            target_ref, uf.upper(), len(df_upload), _job_billed_gib(query_job),
        )
        _print_merge_cost(
            target_ref=target_ref,
            uf=uf,
            rows=len(df_upload),
            job=query_job,
        )
    finally:
        client.delete_table(temp_ref, not_found_ok=True)


def publish_raw_replace_slice(
    df: pd.DataFrame,
    table: str,
    uf: str,
    key_cols: list[str],
    slice_cols: list[str],
    *,
    ensure_target: bool = True,
) -> None:
    """
    Publica uma fatia raw.* por substituicao transacional.

    Este caminho existe para coletores em que o lote representa a fotografia
    completa de uma UF em certos periodos (ex.: SICONFI por uf + exercicio).
    Ele evita o MERGE linha-a-linha, que no BigQuery pode varrer a tabela alvo
    inteira a cada UF. O fluxo e:
    - carrega o lote em uma tabela temporaria;
    - dentro de uma transacao, remove apenas uf + slice_cols presentes no lote;
    - insere a temporaria no alvo final.

    Nao usar para lotes parciais dentro da mesma fatia, pois isso substituiria
    dados que nao vieram no lote atual.
    """
    cfg = _cfg()

    if df.empty:
        print(f"  [BQ] aviso: lote vazio para raw.{table} ({uf.upper()})")
        return

    if not cfg["enabled"] or not _check_bq_available() or not cfg["sa_path"]:
        logger.info(
            "[BQ stub] publish_raw_replace_slice ignorado: table=%s.%s uf=%s linhas=%d",
            cfg["dataset"], table, uf.upper(), len(df),
        )
        return

    from google.cloud import bigquery

    df_upload = _sanitize(df, uf)
    key_cols_norm = _normalize_key_columns(key_cols)
    slice_cols_norm = _normalize_key_columns(slice_cols)
    _validate_keys(df_upload, key_cols_norm, uf)

    missing_slices = [col for col in slice_cols_norm if col not in df_upload.columns]
    if missing_slices:
        raise ValueError(
            "Colunas de fatia ausentes para replace-slice: "
            + ", ".join(missing_slices)
        )

    for col in slice_cols_norm:
        invalid = df_upload[col].isna() | (df_upload[col].astype(str).str.strip() == "")
        if invalid.any():
            raise ValueError(
                f"Coluna de fatia '{col}' contem valores nulos/vazios em "
                f"{int(invalid.sum())} linhas."
            )

    df_upload = _dedupe_by_keys(df_upload, key_cols_norm, table, uf)
    df_upload, schema_types = _coerce_raw_upload_types(df_upload, table)

    client = _get_client()
    target_ref = f"{cfg['project']}.{cfg['dataset']}.{table}"
    temp_ref = (
        f"{cfg['project']}.{cfg['dataset']}."
        f"__tmp_replace_{table}_{uf.lower()}_{int(time.time())}_{uuid4().hex[:8]}"
    )

    schema = [
        bigquery.SchemaField(col, schema_types.get(col, "STRING"))
        for col in df_upload.columns
    ]
    load_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=schema,
    )

    query_parameters = [
        bigquery.ScalarQueryParameter("uf", "STRING", uf.upper()),
    ]
    slice_summary_parts = []
    for col in slice_cols_norm:
        if schema_types.get(col) == "INT64":
            values = sorted({int(value) for value in df_upload[col].dropna().tolist()})
            parameter_type = "INT64"
        else:
            values = sorted(set(df_upload[col].dropna().astype(str).str.strip()))
            parameter_type = "STRING"
        if not values:
            raise ValueError(f"Coluna de fatia '{col}' nao tem valores validos.")
        query_parameters.append(
            bigquery.ArrayQueryParameter(f"slice_{col}", parameter_type, values)
        )
        slice_summary_parts.append(f"{col}={','.join(str(value) for value in values)}")

    replace_sql = _build_replace_slice_sql(
        target_ref=target_ref,
        temp_ref=temp_ref,
        cols=list(df_upload.columns),
        slice_cols=slice_cols_norm,
    )

    try:
        client.load_table_from_dataframe(df_upload, temp_ref, job_config=load_config).result()
        if ensure_target:
            _ensure_target_table(
                client,
                target_ref,
                list(df_upload.columns),
                schema_types=schema_types,
            )

        query_job = client.query(
            replace_sql,
            job_config=_build_query_job_config_for_replace_slice(
                table,
                query_parameters=query_parameters,
            ),
        )
        query_job.result()
        logger.info(
            "[BQ] publish_raw_replace_slice: %s uf=%s slices=%s linhas=%d billed_gib=%s",
            target_ref,
            uf.upper(),
            ";".join(slice_summary_parts),
            len(df_upload),
            _job_billed_gib(query_job),
        )
        _print_replace_slice_cost(
            target_ref=target_ref,
            uf=uf,
            rows=len(df_upload),
            slice_summary="; ".join(slice_summary_parts),
            job=query_job,
        )
    finally:
        client.delete_table(temp_ref, not_found_ok=True)


def publish_raw_append_slice(
    df: pd.DataFrame,
    table: str,
    uf: str,
    key_cols: list[str],
    slice_cols: list[str],
) -> None:
    """
    Publica uma fatia raw.* por append, sem DELETE.

    Este caminho e para backfill inicial em tabela vazia/controlada. Nao use para
    manutencao recorrente de uma fatia ja existente, pois append repetido duplica.
    """
    cfg = _cfg()

    if df.empty:
        print(f"  [BQ] aviso: lote vazio para raw.{table} ({uf.upper()})")
        return

    if not cfg["enabled"] or not _check_bq_available() or not cfg["sa_path"]:
        logger.info(
            "[BQ stub] publish_raw_append_slice ignorado: table=%s.%s uf=%s linhas=%d",
            cfg["dataset"], table, uf.upper(), len(df),
        )
        return

    from google.cloud import bigquery

    df_upload = _sanitize(df, uf)
    key_cols_norm = _normalize_key_columns(key_cols)
    slice_cols_norm = _normalize_key_columns(slice_cols)
    _validate_keys(df_upload, key_cols_norm, uf)

    missing_slices = [col for col in slice_cols_norm if col not in df_upload.columns]
    if missing_slices:
        raise ValueError(
            "Colunas de fatia ausentes para append-slice: "
            + ", ".join(missing_slices)
        )

    for col in slice_cols_norm:
        invalid = df_upload[col].isna() | (df_upload[col].astype(str).str.strip() == "")
        if invalid.any():
            raise ValueError(
                f"Coluna de fatia '{col}' contem valores nulos/vazios em "
                f"{int(invalid.sum())} linhas."
            )

    df_upload = _dedupe_by_keys(df_upload, key_cols_norm, table, uf)
    df_upload, schema_types = _coerce_raw_upload_types(df_upload, table)

    client = _get_client()
    target_ref = f"{cfg['project']}.{cfg['dataset']}.{table}"
    schema = [
        bigquery.SchemaField(col, schema_types.get(col, "STRING"))
        for col in df_upload.columns
    ]
    load_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema=schema,
    )

    slice_summary_parts = []
    for col in slice_cols_norm:
        values = sorted(set(df_upload[col].dropna().astype(str).str.strip()))
        if not values:
            raise ValueError(f"Coluna de fatia '{col}' nao tem valores validos.")
        slice_summary_parts.append(f"{col}={','.join(values)}")

    job = client.load_table_from_dataframe(df_upload, target_ref, job_config=load_config)
    job.result()
    logger.info(
        "[BQ] publish_raw_append_slice: %s uf=%s slices=%s linhas=%d",
        target_ref,
        uf.upper(),
        ";".join(slice_summary_parts),
        len(df_upload),
    )
    _print_append_slice_cost(
        target_ref=target_ref,
        uf=uf,
        rows=len(df_upload),
        slice_summary="; ".join(slice_summary_parts),
        job=job,
    )


def read_mart(table: str, uf: str | None = None, *, strict: bool = False) -> pd.DataFrame:
    """
    Le uma tabela do mart do BigQuery.
    Fallback para CSV local quando BigQuery nao esta disponivel.
    """
    cfg = _cfg()

    if not cfg["enabled"] or not _check_bq_available() or not cfg["sa_path"]:
        if strict:
            _ensure_bigquery_readable("mart", table, uf)
        return _read_mart_csv_fallback(table, uf)

    client = _get_client()
    table_ref = f"{cfg['project']}.mart.{table}"
    uf_filter = f"WHERE uf = '{uf.upper()}'" if uf else ""
    query = f"SELECT * FROM `{table_ref}` {uf_filter}"

    logger.info("[BQ] read_mart: %s uf=%s", table_ref, uf or "nacional")
    try:
        return client.query(query).to_dataframe()
    except Exception as exc:
        if strict:
            raise RuntimeError(
                f"Falha ao ler mart via BigQuery: {table_ref} uf={uf or 'nacional'}"
            ) from exc
        raise


def read_intermediate(table: str, uf: str | None = None, *, strict: bool = False) -> pd.DataFrame:
    """
    Le uma tabela da camada intermediate do BigQuery.
    Retorna DataFrame vazio quando BigQuery nao esta disponivel.
    """
    cfg = _cfg()

    if not cfg["enabled"] or not _check_bq_available() or not cfg["sa_path"]:
        if strict:
            _ensure_bigquery_readable("intermediate", table, uf)
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
    try:
        return client.query(query).to_dataframe()
    except Exception as exc:
        if strict:
            raise RuntimeError(
                "Falha ao ler intermediate via BigQuery: "
                f"{table_ref} uf={uf or 'nacional'}"
            ) from exc
        raise


def _read_mart_csv_fallback(table: str, uf: str | None) -> pd.DataFrame:
    candidates = get_bigquery_csv_fallback_paths(table, uf=uf)
    if not candidates:
        logger.warning(
            "[BQ stub] Sem fallback CSV para tabela '%s'. Retornando DataFrame vazio.",
            table,
        )
        return pd.DataFrame()

    for full_path in candidates:
        if full_path.exists():
            logger.info("[BQ stub] read_mart via CSV local: %s", full_path.name)
            return pd.read_csv(full_path, dtype={"cod_ibge": str})

    logger.warning(
        "[BQ stub] Fallback CSV nao encontrado para '%s': %s. Retornando DataFrame vazio.",
        table,
        ", ".join(str(path) for path in candidates),
    )
    return pd.DataFrame()

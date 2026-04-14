"""
Publicacao do resultado analitico final em camada historica no BigQuery.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from uuid import uuid4

import pandas as pd
from google.cloud import bigquery

from src.engine.classifier import ORDEM_SORT
from src.utils.bigquery_loader import (
    get_bigquery_client,
    get_bigquery_project,
    is_bigquery_enabled,
)
from src.utils.temporal_infra import ensure_temporal_infra

logger = logging.getLogger(__name__)

CLASSIFICACOES_VALIDAS = set(ORDEM_SORT)
SEM_DADOS_LABEL = next(label for label in ORDEM_SORT if "Sem Dados" in label)

RUN_COLUMNS = [
    "snapshot_run_id",
    "snapshot_date",
    "snapshot_ts",
    "uf",
    "run_type",
    "pipeline_mode",
    "source_mode",
    "methodology_version",
    "pipeline_version",
    "status",
    "rows_written",
    "rows_scored",
    "rows_sem_dados",
    "score_avg",
    "score_median",
    "score_min",
    "score_max",
    "source_siconfi_ref",
    "source_dca_ref",
    "source_cauc_ref",
    "source_pncp_ref",
    "notes",
]

SNAPSHOT_COLUMNS = [
    "snapshot_run_id",
    "snapshot_date",
    "snapshot_ts",
    "uf",
    "cod_ibge",
    "ente",
    "populacao",
    "methodology_version",
    "score",
    "classificacao",
    "score_base",
    "score_bruto",
    "anos_entregues",
    "n_anos_cronicos",
    "rproc_pct_atual",
    "lliq_raw",
    "eorcam_raw",
    "qsiconfi",
    "ccauc",
    "autonomia_media",
    "eorcam_norm",
    "lliq_norm",
    "rproc_norm",
    "autonomia_norm",
    "contrib_eorcam",
    "contrib_lliq",
    "contrib_qsiconfi",
    "contrib_ccauc",
    "contrib_autonomia",
    "contrib_rproc",
    "pen_lliq_parcial",
    "pen_situacional",
    "dias_atraso",
    "decay_fator",
    "dado_suspeito",
    "dado_suspeito_lliq",
    "dado_defasado",
    "lliq_parcial",
    "autonomia_critica",
    "n_graves",
    "n_moderadas",
    "n_leves",
    "pendencias",
    "pendencias_cauc_json",
    "n_licitacoes",
    "valor_homologado_total",
    "n_dispensa",
    "valor_hom_dispensa",
    "pct_dispensa",
    "ano_ultima_licitacao",
    "alerta_dispensa",
]

RUN_SCHEMA_SPEC = [
    ("snapshot_run_id", "STRING", "REQUIRED"),
    ("snapshot_date", "DATE", "REQUIRED"),
    ("snapshot_ts", "TIMESTAMP", "REQUIRED"),
    ("uf", "STRING", "REQUIRED"),
    ("run_type", "STRING", "REQUIRED"),
    ("pipeline_mode", "STRING", "NULLABLE"),
    ("source_mode", "STRING", "NULLABLE"),
    ("methodology_version", "STRING", "REQUIRED"),
    ("pipeline_version", "STRING", "NULLABLE"),
    ("status", "STRING", "REQUIRED"),
    ("rows_written", "INT64", "NULLABLE"),
    ("rows_scored", "INT64", "NULLABLE"),
    ("rows_sem_dados", "INT64", "NULLABLE"),
    ("score_avg", "FLOAT64", "NULLABLE"),
    ("score_median", "FLOAT64", "NULLABLE"),
    ("score_min", "FLOAT64", "NULLABLE"),
    ("score_max", "FLOAT64", "NULLABLE"),
    ("source_siconfi_ref", "STRING", "NULLABLE"),
    ("source_dca_ref", "STRING", "NULLABLE"),
    ("source_cauc_ref", "STRING", "NULLABLE"),
    ("source_pncp_ref", "STRING", "NULLABLE"),
    ("notes", "STRING", "NULLABLE"),
]

SNAPSHOT_SCHEMA_SPEC = [
    ("snapshot_run_id", "STRING", "REQUIRED"),
    ("snapshot_date", "DATE", "REQUIRED"),
    ("snapshot_ts", "TIMESTAMP", "REQUIRED"),
    ("uf", "STRING", "REQUIRED"),
    ("cod_ibge", "STRING", "REQUIRED"),
    ("ente", "STRING", "NULLABLE"),
    ("populacao", "INT64", "NULLABLE"),
    ("methodology_version", "STRING", "REQUIRED"),
    ("score", "FLOAT64", "NULLABLE"),
    ("classificacao", "STRING", "NULLABLE"),
    ("score_base", "FLOAT64", "NULLABLE"),
    ("score_bruto", "FLOAT64", "NULLABLE"),
    ("anos_entregues", "INT64", "NULLABLE"),
    ("n_anos_cronicos", "INT64", "NULLABLE"),
    ("rproc_pct_atual", "FLOAT64", "NULLABLE"),
    ("lliq_raw", "FLOAT64", "NULLABLE"),
    ("eorcam_raw", "FLOAT64", "NULLABLE"),
    ("qsiconfi", "FLOAT64", "NULLABLE"),
    ("ccauc", "FLOAT64", "NULLABLE"),
    ("autonomia_media", "FLOAT64", "NULLABLE"),
    ("eorcam_norm", "FLOAT64", "NULLABLE"),
    ("lliq_norm", "FLOAT64", "NULLABLE"),
    ("rproc_norm", "FLOAT64", "NULLABLE"),
    ("autonomia_norm", "FLOAT64", "NULLABLE"),
    ("contrib_eorcam", "FLOAT64", "NULLABLE"),
    ("contrib_lliq", "FLOAT64", "NULLABLE"),
    ("contrib_qsiconfi", "FLOAT64", "NULLABLE"),
    ("contrib_ccauc", "FLOAT64", "NULLABLE"),
    ("contrib_autonomia", "FLOAT64", "NULLABLE"),
    ("contrib_rproc", "FLOAT64", "NULLABLE"),
    ("pen_lliq_parcial", "FLOAT64", "NULLABLE"),
    ("pen_situacional", "FLOAT64", "NULLABLE"),
    ("dias_atraso", "INT64", "NULLABLE"),
    ("decay_fator", "FLOAT64", "NULLABLE"),
    ("dado_suspeito", "BOOL", "NULLABLE"),
    ("dado_suspeito_lliq", "BOOL", "NULLABLE"),
    ("dado_defasado", "BOOL", "NULLABLE"),
    ("lliq_parcial", "BOOL", "NULLABLE"),
    ("autonomia_critica", "BOOL", "NULLABLE"),
    ("n_graves", "INT64", "NULLABLE"),
    ("n_moderadas", "INT64", "NULLABLE"),
    ("n_leves", "INT64", "NULLABLE"),
    ("pendencias", "STRING", "NULLABLE"),
    ("pendencias_cauc_json", "STRING", "NULLABLE"),
    ("n_licitacoes", "INT64", "NULLABLE"),
    ("valor_homologado_total", "FLOAT64", "NULLABLE"),
    ("n_dispensa", "INT64", "NULLABLE"),
    ("valor_hom_dispensa", "FLOAT64", "NULLABLE"),
    ("pct_dispensa", "FLOAT64", "NULLABLE"),
    ("ano_ultima_licitacao", "INT64", "NULLABLE"),
    ("alerta_dispensa", "BOOL", "NULLABLE"),
]

REQUIRED_COLUMNS = {
    "cod_ibge",
    "ente",
    "score",
    "classificacao",
    "score_base",
    "score_bruto",
    "anos_entregues",
    "n_anos_cronicos",
}

INT_COLUMNS = {
    "populacao",
    "anos_entregues",
    "n_anos_cronicos",
    "dias_atraso",
    "n_graves",
    "n_moderadas",
    "n_leves",
    "n_licitacoes",
    "n_dispensa",
    "ano_ultima_licitacao",
}

FLOAT_COLUMNS = {
    "score",
    "score_base",
    "score_bruto",
    "rproc_pct_atual",
    "lliq_raw",
    "eorcam_raw",
    "qsiconfi",
    "ccauc",
    "autonomia_media",
    "eorcam_norm",
    "lliq_norm",
    "rproc_norm",
    "autonomia_norm",
    "contrib_eorcam",
    "contrib_lliq",
    "contrib_qsiconfi",
    "contrib_ccauc",
    "contrib_autonomia",
    "contrib_rproc",
    "pen_lliq_parcial",
    "pen_situacional",
    "decay_fator",
    "valor_homologado_total",
    "valor_hom_dispensa",
    "pct_dispensa",
}

BOOL_COLUMNS = {
    "dado_suspeito",
    "dado_suspeito_lliq",
    "dado_defasado",
    "lliq_parcial",
    "autonomia_critica",
    "alerta_dispensa",
}

TRUE_STRINGS = {"true", "1", "t", "yes", "y", "sim"}
FALSE_STRINGS = {"false", "0", "f", "no", "n", "nao", "não"}


def _schema_columns(schema_spec: list[tuple[str, ...]]) -> list[str]:
    return [item[0] for item in schema_spec]


def _schema_fields(schema_spec: list[tuple[str, ...]]) -> list[bigquery.SchemaField]:
    fields = []
    for item in schema_spec:
        if len(item) == 2:
            name, field_type = item
            mode = "NULLABLE"
        elif len(item) == 3:
            name, field_type, mode = item
        else:
            raise ValueError(f"Schema spec invalido: {item!r}")
        fields.append(bigquery.SchemaField(name, field_type, mode=mode))
    return fields


def _build_typed_select_list(
    schema_spec: list[tuple[str, ...]],
    *,
    source_alias: str = "S",
) -> str:
    return ",\n        ".join(
        [
            f"CAST({source_alias}.{item[0]} AS {item[1]}) AS {item[0]}"
            for item in schema_spec
        ]
    )


if RUN_COLUMNS != _schema_columns(RUN_SCHEMA_SPEC):
    raise RuntimeError("RUN_COLUMNS e RUN_SCHEMA_SPEC estao fora de sincronia.")

if SNAPSHOT_COLUMNS != _schema_columns(SNAPSHOT_SCHEMA_SPEC):
    raise RuntimeError("SNAPSHOT_COLUMNS e SNAPSHOT_SCHEMA_SPEC estao fora de sincronia.")


def build_snapshot_run_id(uf: str, snapshot_date: date, run_type: str = "pipeline") -> str:
    suffix = uuid4().hex[:8]
    return f"{uf.upper()}_{snapshot_date.strftime('%Y%m%d')}_{run_type}_{suffix}"


def validate_snapshot_dataframe(df: pd.DataFrame, uf: str) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatorias ausentes para snapshot: {sorted(missing)}")

    if df.empty:
        raise ValueError("Snapshot nao pode ser publicado com DataFrame vazio.")

    if df["cod_ibge"].isna().any():
        raise ValueError("Snapshot contem cod_ibge nulo.")

    if df["cod_ibge"].astype(str).duplicated().any():
        dup = df.loc[df["cod_ibge"].astype(str).duplicated(), "cod_ibge"].astype(str).tolist()[:5]
        raise ValueError(f"Snapshot contem municipios duplicados: {dup}")

    invalid = (
        df["classificacao"]
        .dropna()
        .astype(str)
        .loc[lambda s: ~s.isin(CLASSIFICACOES_VALIDAS)]
        .unique()
        .tolist()
    )
    if invalid:
        raise ValueError(f"Snapshot contem classificacoes invalidas: {invalid}")

    valid_scores = pd.to_numeric(df["score"], errors="coerce").dropna()
    if not valid_scores.empty and ((valid_scores < 0) | (valid_scores > 100)).any():
        raise ValueError("Snapshot contem score fora da faixa [0, 100].")

    if not uf or len(uf.strip()) != 2:
        raise ValueError(f"UF invalida para snapshot: {uf!r}")


def _to_optional_bool(value):
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)

    text = str(value).strip().lower()
    if text in TRUE_STRINGS:
        return True
    if text in FALSE_STRINGS:
        return False
    return bool(value)


def _coerce_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in INT_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    for col in FLOAT_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    for col in BOOL_COLUMNS:
        if col in out.columns:
            out[col] = out[col].map(_to_optional_bool)

    for col in ["cod_ibge", "ente", "classificacao", "pendencias", "pendencias_cauc_json"]:
        if col in out.columns:
            out[col] = out[col].where(out[col].notna(), None)

    return out


def _prepare_snapshot_rows(
    df: pd.DataFrame,
    uf: str,
    methodology_version: str,
    snapshot_run_id: str,
    snapshot_date: date,
    snapshot_ts: datetime,
) -> pd.DataFrame:
    out = df.copy()
    out["cod_ibge"] = out["cod_ibge"].astype(str).str.zfill(7)
    out["uf"] = uf.upper()
    out["snapshot_run_id"] = snapshot_run_id
    out["snapshot_date"] = snapshot_date
    out["snapshot_ts"] = snapshot_ts
    out["methodology_version"] = methodology_version

    for col in SNAPSHOT_COLUMNS:
        if col not in out.columns:
            out[col] = None

    out = out[SNAPSHOT_COLUMNS]
    out = _coerce_columns(out)
    return out


def _build_run_record(
    df_snapshot: pd.DataFrame,
    snapshot_run_id: str,
    snapshot_date: date,
    snapshot_ts: datetime,
    uf: str,
    methodology_version: str,
    *,
    run_type: str,
    pipeline_mode: str | None,
    source_mode: str,
    pipeline_version: str | None,
    notes: str | None,
) -> pd.DataFrame:
    scores = pd.to_numeric(df_snapshot["score"], errors="coerce").dropna()
    rows_written = len(df_snapshot)
    rows_scored = int(df_snapshot["score"].notna().sum())
    rows_sem_dados = int(df_snapshot["classificacao"].eq(SEM_DADOS_LABEL).sum())

    record = {
        "snapshot_run_id": snapshot_run_id,
        "snapshot_date": snapshot_date,
        "snapshot_ts": snapshot_ts,
        "uf": uf.upper(),
        "run_type": run_type,
        "pipeline_mode": pipeline_mode,
        "source_mode": source_mode,
        "methodology_version": methodology_version,
        "pipeline_version": pipeline_version,
        "status": "SUCCESS",
        "rows_written": rows_written,
        "rows_scored": rows_scored,
        "rows_sem_dados": rows_sem_dados,
        "score_avg": float(scores.mean()) if not scores.empty else None,
        "score_median": float(scores.median()) if not scores.empty else None,
        "score_min": float(scores.min()) if not scores.empty else None,
        "score_max": float(scores.max()) if not scores.empty else None,
        "source_siconfi_ref": None,
        "source_dca_ref": None,
        "source_cauc_ref": None,
        "source_pncp_ref": None,
        "notes": notes,
    }
    return pd.DataFrame([[record[col] for col in RUN_COLUMNS]], columns=RUN_COLUMNS)


def _append_dataframe(
    client: bigquery.Client,
    table_ref: str,
    df: pd.DataFrame,
    *,
    schema_spec: list[tuple[str, str]] | None = None,
) -> None:
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema=_schema_fields(schema_spec) if schema_spec else None,
    )
    client.load_table_from_dataframe(df, table_ref, job_config=job_config).result()


def _replace_daily_snapshot(
    client: bigquery.Client,
    project: str,
    *,
    uf: str,
    snapshot_date: date,
    df_snapshot: pd.DataFrame,
) -> None:
    temp_table = f"{project}.snapshots._tmp_municipios_risco_snapshot_{uuid4().hex[:8]}"
    target_table = f"{project}.snapshots.municipios_risco_snapshot"
    columns_csv = ", ".join(SNAPSHOT_COLUMNS)
    typed_select_csv = _build_typed_select_list(SNAPSHOT_SCHEMA_SPEC)

    load_job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=_schema_fields(SNAPSHOT_SCHEMA_SPEC),
    )
    client.load_table_from_dataframe(df_snapshot, temp_table, job_config=load_job_config).result()

    try:
        query = f"""
        BEGIN TRANSACTION;
        DELETE FROM `{target_table}`
        WHERE uf = @uf
          AND snapshot_date = @snapshot_date;

        INSERT INTO `{target_table}` ({columns_csv})
        SELECT
        {typed_select_csv}
        FROM `{temp_table}` S;
        COMMIT TRANSACTION;
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("uf", "STRING", uf.upper()),
                bigquery.ScalarQueryParameter("snapshot_date", "DATE", snapshot_date.isoformat()),
            ]
        )
        client.query(query, job_config=job_config).result()
    finally:
        client.delete_table(temp_table, not_found_ok=True)


def publish_snapshot(
    df: pd.DataFrame,
    *,
    uf: str,
    methodology_version: str,
    run_type: str = "pipeline",
    pipeline_mode: str | None = None,
    source_mode: str = "bigquery",
    pipeline_version: str | None = None,
    notes: str | None = None,
) -> bool:
    if not is_bigquery_enabled():
        logger.warning(
            "BigQuery nao esta habilitado; snapshot historico nao foi publicado."
        )
        return False

    validate_snapshot_dataframe(df, uf)
    ensure_temporal_infra()

    snapshot_date = date.today()
    snapshot_ts = datetime.now(timezone.utc)
    snapshot_run_id = build_snapshot_run_id(uf, snapshot_date, run_type=run_type)
    df_snapshot = _prepare_snapshot_rows(
        df,
        uf=uf,
        methodology_version=methodology_version,
        snapshot_run_id=snapshot_run_id,
        snapshot_date=snapshot_date,
        snapshot_ts=snapshot_ts,
    )
    df_run = _build_run_record(
        df_snapshot,
        snapshot_run_id=snapshot_run_id,
        snapshot_date=snapshot_date,
        snapshot_ts=snapshot_ts,
        uf=uf,
        methodology_version=methodology_version,
        run_type=run_type,
        pipeline_mode=pipeline_mode,
        source_mode=source_mode,
        pipeline_version=pipeline_version,
        notes=notes,
    )

    client = get_bigquery_client()
    project = get_bigquery_project()
    _append_dataframe(
        client,
        f"{project}.snapshots.snapshot_runs",
        df_run,
        schema_spec=RUN_SCHEMA_SPEC,
    )
    _replace_daily_snapshot(
        client,
        project,
        uf=uf,
        snapshot_date=snapshot_date,
        df_snapshot=df_snapshot,
    )

    logger.info(
        "Snapshot publicado com sucesso: run_id=%s uf=%s linhas=%d",
        snapshot_run_id,
        uf.upper(),
        len(df_snapshot),
    )
    print(
        f"  [SNAPSHOT] OK run_id={snapshot_run_id} | uf={uf.upper()} | linhas={len(df_snapshot)}"
    )
    return True

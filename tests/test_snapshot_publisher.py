from datetime import datetime, timezone

import pandas as pd
import pytest
from google.cloud import bigquery

from src.utils import snapshot_publisher
from src.utils.snapshot_publisher import (
    CLASSIFICACOES_VALIDAS,
    RUN_COLUMNS,
    RUN_SCHEMA_SPEC,
    SNAPSHOT_COLUMNS,
    SNAPSHOT_SCHEMA_SPEC,
    _append_dataframe,
    _build_run_record,
    _build_typed_select_list,
    _coerce_columns,
    _prepare_snapshot_rows,
    _replace_daily_snapshot,
    build_snapshot_run_id,
    publish_snapshot,
    validate_snapshot_dataframe,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cod_ibge": "2507507",
                "ente": "Joao Pessoa",
                "score": 72.4,
                "classificacao": sorted(CLASSIFICACOES_VALIDAS)[0],
                "score_base": 75.0,
                "score_bruto": 72.4,
                "anos_entregues": 6,
                "n_anos_cronicos": 1,
                "alerta_dispensa": "False",
                "dado_defasado": "true",
            }
        ]
    )


def _sample_snapshot_ts() -> datetime:
    return datetime(2026, 4, 14, 18, 26, 59, tzinfo=timezone.utc)


def test_schema_specs_stay_aligned_with_column_order():
    assert [item[0] for item in RUN_SCHEMA_SPEC] == RUN_COLUMNS
    assert [item[0] for item in SNAPSHOT_SCHEMA_SPEC] == SNAPSHOT_COLUMNS


def test_validate_snapshot_dataframe_accepts_valid_payload():
    df = _sample_df()
    validate_snapshot_dataframe(df, "PB")


def test_validate_snapshot_dataframe_rejects_invalid_classification():
    df = _sample_df()
    df.loc[0, "classificacao"] = "INVALIDA"

    with pytest.raises(ValueError, match="classificacoes invalidas"):
        validate_snapshot_dataframe(df, "PB")


def test_coerce_columns_parses_boolean_strings_without_inversion():
    df = _coerce_columns(_sample_df())

    assert bool(df.loc[0, "alerta_dispensa"]) is False
    assert bool(df.loc[0, "dado_defasado"]) is True


def test_build_snapshot_run_id_is_structured():
    run_id = build_snapshot_run_id("pb", pd.Timestamp("2026-04-08").date(), run_type="pipeline")

    assert run_id.startswith("PB_20260408_pipeline_")
    assert len(run_id.split("_")[-1]) == 8


def test_prepare_snapshot_rows_preserves_temporal_types():
    snapshot_date = pd.Timestamp("2026-04-14").date()
    snapshot_ts = _sample_snapshot_ts()

    df_snapshot = _prepare_snapshot_rows(
        _sample_df(),
        uf="SE",
        methodology_version="v7.0",
        snapshot_run_id="SE_20260414_pipeline_deadbeef",
        snapshot_date=snapshot_date,
        snapshot_ts=snapshot_ts,
    )

    assert df_snapshot.loc[0, "snapshot_date"] == snapshot_date
    assert type(df_snapshot.loc[0, "snapshot_date"]).__name__ == "date"
    assert df_snapshot.loc[0, "snapshot_ts"] == snapshot_ts
    assert df_snapshot.loc[0, "snapshot_ts"].tzinfo == timezone.utc


def test_build_run_record_preserves_temporal_types():
    snapshot_date = pd.Timestamp("2026-04-14").date()
    snapshot_ts = _sample_snapshot_ts()
    df_snapshot = _prepare_snapshot_rows(
        _sample_df(),
        uf="SE",
        methodology_version="v7.0",
        snapshot_run_id="SE_20260414_pipeline_deadbeef",
        snapshot_date=snapshot_date,
        snapshot_ts=snapshot_ts,
    )

    run_df = _build_run_record(
        df_snapshot,
        "SE_20260414_pipeline_deadbeef",
        snapshot_date,
        snapshot_ts,
        "SE",
        "v7.0",
        run_type="pipeline",
        pipeline_mode="incremental",
        source_mode="bigquery",
        pipeline_version="pipeline.py v9.1",
        notes=None,
    )

    assert run_df.loc[0, "snapshot_date"] == snapshot_date
    assert type(run_df.loc[0, "snapshot_date"]).__name__ == "date"
    assert run_df.loc[0, "snapshot_ts"] == snapshot_ts
    assert run_df.loc[0, "snapshot_ts"].tzinfo == timezone.utc


def test_build_typed_select_list_casts_temporal_columns():
    typed_select = _build_typed_select_list(SNAPSHOT_SCHEMA_SPEC)

    assert "CAST(S.snapshot_date AS DATE) AS snapshot_date" in typed_select
    assert "CAST(S.snapshot_ts AS TIMESTAMP) AS snapshot_ts" in typed_select


def test_append_dataframe_uses_explicit_schema_for_temporal_columns():
    captured = {}

    class FakeJob:
        def result(self):
            return None

    class FakeClient:
        def load_table_from_dataframe(self, df, table_ref, job_config=None):
            captured["table_ref"] = table_ref
            captured["write_disposition"] = job_config.write_disposition
            captured["schema"] = [
                (field.name, field.field_type, field.mode) for field in job_config.schema
            ]
            return FakeJob()

    _append_dataframe(
        FakeClient(),
        "solvelicita.snapshots.snapshot_runs",
        pd.DataFrame([{"snapshot_run_id": "x"}]),
        schema_spec=RUN_SCHEMA_SPEC,
    )

    assert captured["table_ref"] == "solvelicita.snapshots.snapshot_runs"
    assert captured["write_disposition"] == bigquery.WriteDisposition.WRITE_APPEND
    assert ("snapshot_run_id", "STRING", "REQUIRED") in captured["schema"]
    assert ("snapshot_date", "DATE", "REQUIRED") in captured["schema"]
    assert ("snapshot_ts", "TIMESTAMP", "REQUIRED") in captured["schema"]


def test_replace_daily_snapshot_uses_typed_temp_load_and_typed_insert():
    captured = {}

    class FakeJob:
        def result(self):
            return None

    class FakeClient:
        def load_table_from_dataframe(self, df, table_ref, job_config=None):
            captured["temp_table_ref"] = table_ref
            captured["load_schema"] = [
                (field.name, field.field_type, field.mode) for field in job_config.schema
            ]
            captured["load_write_disposition"] = job_config.write_disposition
            return FakeJob()

        def query(self, query, job_config=None):
            captured["query"] = query
            captured["query_parameters"] = [
                (param.name, param.type_, param.value) for param in job_config.query_parameters
            ]
            return FakeJob()

        def delete_table(self, table_ref, not_found_ok=False):
            captured["deleted_table_ref"] = table_ref
            captured["deleted_not_found_ok"] = not_found_ok

    _replace_daily_snapshot(
        FakeClient(),
        "solvelicita",
        uf="SE",
        snapshot_date=pd.Timestamp("2026-04-14").date(),
        df_snapshot=_prepare_snapshot_rows(
            _sample_df(),
            uf="SE",
            methodology_version="v7.0",
            snapshot_run_id="SE_20260414_pipeline_deadbeef",
            snapshot_date=pd.Timestamp("2026-04-14").date(),
            snapshot_ts=_sample_snapshot_ts(),
        ),
    )

    assert captured["temp_table_ref"].startswith("solvelicita.snapshots._tmp_municipios_risco_snapshot_")
    assert captured["load_write_disposition"] == bigquery.WriteDisposition.WRITE_TRUNCATE
    assert ("snapshot_run_id", "STRING", "REQUIRED") in captured["load_schema"]
    assert ("snapshot_date", "DATE", "REQUIRED") in captured["load_schema"]
    assert ("snapshot_ts", "TIMESTAMP", "REQUIRED") in captured["load_schema"]
    assert ("cod_ibge", "STRING", "REQUIRED") in captured["load_schema"]
    assert "CAST(S.snapshot_date AS DATE) AS snapshot_date" in captured["query"]
    assert "CAST(S.snapshot_ts AS TIMESTAMP) AS snapshot_ts" in captured["query"]
    assert ("uf", "STRING", "SE") in captured["query_parameters"]
    assert ("snapshot_date", "DATE", pd.Timestamp("2026-04-14").date()) in captured["query_parameters"]
    assert captured["deleted_table_ref"] == captured["temp_table_ref"]
    assert captured["deleted_not_found_ok"] is True


def test_publish_snapshot_appends_run_log_and_replaces_daily_snapshot(monkeypatch):
    calls = []

    monkeypatch.setattr(snapshot_publisher, "is_bigquery_enabled", lambda: True)
    monkeypatch.setattr(snapshot_publisher, "ensure_temporal_infra", lambda: None)
    monkeypatch.setattr(snapshot_publisher, "get_bigquery_client", lambda: object())
    monkeypatch.setattr(snapshot_publisher, "get_bigquery_project", lambda: "solvelicita")
    monkeypatch.setattr(
        snapshot_publisher,
        "_append_dataframe",
        lambda client, table_ref, df, schema_spec=None: calls.append(
            ("append", table_ref, len(df), schema_spec)
        ),
    )
    monkeypatch.setattr(
        snapshot_publisher,
        "_replace_daily_snapshot",
        lambda client, project, uf, snapshot_date, df_snapshot: calls.append(
            ("replace", project, uf, snapshot_date, len(df_snapshot))
        ),
    )
    monkeypatch.setattr(
        snapshot_publisher,
        "datetime",
        type(
            "FakeDateTime",
            (),
            {"now": staticmethod(lambda tz=None: datetime(2026, 4, 14, 18, 42, 12, tzinfo=tz))},
        ),
    )

    ok = publish_snapshot(
        _sample_df(),
        uf="PB",
        methodology_version="v7.0",
        run_type="pipeline",
        pipeline_mode="incremental",
        source_mode="bigquery",
        pipeline_version="pipeline.py v9.1",
    )

    assert ok is True
    assert calls[0][0] == "append"
    assert calls[0][1] == "solvelicita.snapshots.snapshot_runs"
    assert calls[0][2] == 1
    assert calls[0][3] == RUN_SCHEMA_SPEC
    assert calls[1][0] == "replace"
    assert calls[1][1] == "solvelicita"
    assert calls[1][2] == "PB"
    assert str(calls[1][3]) == "2026-04-14"
    assert calls[1][4] == 1

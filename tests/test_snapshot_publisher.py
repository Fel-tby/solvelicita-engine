import pandas as pd
import pytest

from utils import snapshot_publisher
from utils.snapshot_publisher import (
    CLASSIFICACOES_VALIDAS,
    _coerce_columns,
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


def test_publish_snapshot_appends_run_log_and_replaces_daily_snapshot(monkeypatch):
    chamadas = []

    monkeypatch.setattr(snapshot_publisher, "is_bigquery_enabled", lambda: True)
    monkeypatch.setattr(snapshot_publisher, "ensure_temporal_infra", lambda: None)
    monkeypatch.setattr(snapshot_publisher, "get_bigquery_client", lambda: object())
    monkeypatch.setattr(snapshot_publisher, "get_bigquery_project", lambda: "solvelicita")
    monkeypatch.setattr(
        snapshot_publisher,
        "_append_dataframe",
        lambda client, table_ref, df: chamadas.append(("append", table_ref, len(df))),
    )
    monkeypatch.setattr(
        snapshot_publisher,
        "_replace_daily_snapshot",
        lambda client, project, uf, snapshot_date, df_snapshot: chamadas.append(
            ("replace", project, uf, snapshot_date, len(df_snapshot))
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
    assert chamadas[0][0] == "append"
    assert chamadas[0][1] == "solvelicita.snapshots.snapshot_runs"
    assert chamadas[1][0] == "replace"
    assert chamadas[1][1] == "solvelicita"
    assert chamadas[1][2] == "PB"
    assert chamadas[1][4] == 1

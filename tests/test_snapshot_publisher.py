import pandas as pd
import pytest

from utils.snapshot_publisher import (
    CLASSIFICACOES_VALIDAS,
    _coerce_columns,
    build_snapshot_run_id,
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

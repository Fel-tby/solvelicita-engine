import pandas as pd
import pytest

from src.engine import solvency
from src.utils import bigquery_loader


def test_read_mart_strict_raises_when_bigquery_is_unavailable(monkeypatch):
    monkeypatch.setenv("BQ_ENABLED", "false")
    monkeypatch.setenv("GCP_SA_KEY_PATH", "")
    monkeypatch.setattr(bigquery_loader, "_check_bq_available", lambda: False)

    with pytest.raises(RuntimeError, match="Leitura canonica via BigQuery indisponivel"):
        bigquery_loader.read_mart("mart_indicadores_municipios", uf="PB", strict=True)


def test_read_intermediate_strict_raises_when_bigquery_is_unavailable(monkeypatch):
    monkeypatch.setenv("BQ_ENABLED", "false")
    monkeypatch.setenv("GCP_SA_KEY_PATH", "")
    monkeypatch.setattr(bigquery_loader, "_check_bq_available", lambda: False)

    with pytest.raises(RuntimeError, match="Leitura canonica via BigQuery indisponivel"):
        bigquery_loader.read_intermediate("int_siconfi_postprocessed", uf="PB", strict=True)


def test_read_intermediate_non_strict_keeps_legacy_empty_fallback(monkeypatch):
    monkeypatch.setenv("BQ_ENABLED", "false")
    monkeypatch.setenv("GCP_SA_KEY_PATH", "")
    monkeypatch.setattr(bigquery_loader, "_check_bq_available", lambda: False)

    result = bigquery_loader.read_intermediate("int_siconfi_postprocessed", uf="PB", strict=False)

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_carregar_bq_passes_strict_flag_to_loader(monkeypatch):
    calls = []

    def fake_read_mart(table, uf=None, strict=False):
        calls.append(("mart", table, uf, strict))
        if table == "mart_indicadores_municipios":
            return pd.DataFrame(
                [
                    {
                        "cod_ibge": "2800100",
                        "ente": "Amparo de Sao Francisco",
                        "populacao": 1000,
                        "ccauc": 1.0,
                        "anos_entregues": 6,
                        "n_anos_cronicos": 0,
                    }
                ]
            )
        return pd.DataFrame(columns=["cod_ibge"])

    def fake_read_intermediate(table, uf=None, strict=False):
        calls.append(("intermediate", table, uf, strict))
        return pd.DataFrame(columns=["cod_ibge"])

    monkeypatch.setattr("src.utils.bigquery_loader.read_mart", fake_read_mart)
    monkeypatch.setattr("src.utils.bigquery_loader.read_intermediate", fake_read_intermediate)

    written = []
    monkeypatch.setattr(
        pd.DataFrame,
        "to_csv",
        lambda self, *args, **kwargs: written.append(args[0] if args else None),
        raising=False,
    )

    result = solvency._carregar_bq("SE", strict_bigquery=True)

    assert not result.empty
    assert all(call[3] is True for call in calls)
    assert [call[:3] for call in calls] == [
        ("mart", "mart_indicadores_municipios", "SE"),
        ("mart", "mart_pncp_municipios", "SE"),
        ("intermediate", "int_siconfi_postprocessed", "SE"),
        ("intermediate", "int_dca_postprocessed", "SE"),
    ]
    assert written, "Esperava exportacao local de auditoria no caminho bigquery"


def test_run_bigquery_strict_propagates_runtime_error(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("BigQuery indisponivel")

    monkeypatch.setattr(solvency, "_carregar_bq", fail)

    with pytest.raises(RuntimeError, match="BigQuery indisponivel"):
        solvency.run(uf="PB", source="bigquery", strict_bigquery=True)

import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from collectors import municipios


def test_preparar_lote_municipios_deduplica_por_uf_cod_ibge():
    items = [
        {
            "cod_ibge": "2500106",
            "uf": "PB",
            "ente": "Agua Branca",
            "populacao": 1000,
            "cnpj": "1",
        },
        {
            "cod_ibge": "2500106",
            "uf": "PB",
            "ente": "Agua Branca Atualizado",
            "populacao": 1001,
            "cnpj": "2",
        },
        {
            "cod_ibge": "2500205",
            "uf": "PB",
            "ente": "Aguiar",
            "populacao": 2000,
            "cnpj": "3",
        },
    ]

    result = municipios._preparar_lote_municipios(items, "PB")

    assert len(result) == 2
    assert result["cod_ibge"].tolist() == ["2500106", "2500205"]
    assert result.loc[result["cod_ibge"] == "2500106", "ente"].iloc[0] == "Agua Branca Atualizado"


def test_preparar_lote_municipios_rejeita_uf_divergente():
    items = [
        {
            "cod_ibge": "2300101",
            "uf": "CE",
            "ente": "Abaiara",
            "populacao": 1000,
        }
    ]

    with pytest.raises(ValueError, match="UFs divergentes"):
        municipios._preparar_lote_municipios(items, "PB")


def test_run_publica_com_merge_seguro(monkeypatch):
    published = {}
    temp_root = Path.cwd() / ".pytest_artifacts" / f"municipios_{uuid4().hex[:8]}"
    temp_root.mkdir(parents=True, exist_ok=True)

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "items": [
                    {
                        "cod_ibge": "2500106",
                        "uf": "PB",
                        "esfera": "M",
                        "ente": "Agua Branca",
                        "cnpj": "1",
                        "populacao": 1000,
                    },
                    {
                        "cod_ibge": "2500106",
                        "uf": "PB",
                        "esfera": "M",
                        "ente": "Agua Branca Atualizado",
                        "cnpj": "2",
                        "populacao": 1001,
                    },
                    {
                        "cod_ibge": "2500205",
                        "uf": "PB",
                        "esfera": "M",
                        "ente": "Aguiar",
                        "cnpj": "3",
                        "populacao": 2000,
                    },
                    {
                        "cod_ibge": "2300101",
                        "uf": "CE",
                        "esfera": "M",
                        "ente": "Abaiara",
                        "cnpj": "4",
                        "populacao": 3000,
                    },
                ]
            }

    def fake_get(*args, **kwargs):
        return DummyResponse()

    def fake_get_artifact_path(uf: str, artifact_key: str, **_kwargs):
        assert artifact_key == "municipios_tabela"
        processed = temp_root / "processed" / uf.upper()
        processed.mkdir(parents=True, exist_ok=True)
        return processed / f"municipios_{uf.lower()}_tabela.csv"

    def fake_publish_raw_merge(df, table, uf, key_cols):
        published["df"] = df.copy()
        published["table"] = table
        published["uf"] = uf
        published["key_cols"] = key_cols

    monkeypatch.setattr(municipios.httpx, "get", fake_get)
    monkeypatch.setattr(municipios, "get_artifact_path", fake_get_artifact_path)
    monkeypatch.setattr(municipios, "publish_raw_merge", fake_publish_raw_merge)

    try:
        result = municipios.run("PB")

        assert len(result) == 2
        assert published["table"] == "dim_municipios"
        assert published["uf"] == "PB"
        assert published["key_cols"] == ["uf", "cod_ibge"]
        assert published["df"]["cod_ibge"].tolist() == ["2500106", "2500205"]
        assert published["df"].loc[published["df"]["cod_ibge"] == "2500106", "ente"].iloc[0] == "Agua Branca Atualizado"

        csv_path = temp_root / "processed" / "PB" / "municipios_pb_tabela.csv"
        assert csv_path.exists()

        csv_df = pd.read_csv(csv_path, dtype={"cod_ibge": str})
        assert csv_df["cod_ibge"].tolist() == ["2500106", "2500205"]
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_carregar_municipios_faz_fallback_para_api_quando_csv_nao_existe(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "items": [
                    {
                        "cod_ibge": "2800100",
                        "uf": "SE",
                        "esfera": "M",
                        "ente": "Amparo de Sao Francisco",
                        "cnpj": "1",
                        "populacao": 2000,
                    },
                    {
                        "cod_ibge": "3100104",
                        "uf": "MG",
                        "esfera": "M",
                        "ente": "Abadia dos Dourados",
                        "cnpj": "2",
                        "populacao": 3000,
                    },
                ]
            }

    temp_root = Path.cwd() / ".pytest_artifacts" / f"municipios_{uuid4().hex[:8]}"
    temp_root.mkdir(parents=True, exist_ok=True)

    def fake_get(*args, **kwargs):
        return DummyResponse()

    def fake_get_artifact_path(uf: str, artifact_key: str, **_kwargs):
        assert artifact_key == "municipios_tabela"
        processed = temp_root / "processed" / uf.upper()
        processed.mkdir(parents=True, exist_ok=True)
        return processed / f"municipios_{uf.lower()}_tabela.csv"

    monkeypatch.setattr(municipios.httpx, "get", fake_get)
    monkeypatch.setattr(municipios, "get_artifact_path", fake_get_artifact_path)

    try:
        result = municipios.carregar_municipios("SE", prefer_local=True, persist_local=False)
        assert len(result) == 1
        assert result["cod_ibge"].tolist() == ["2800100"]
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

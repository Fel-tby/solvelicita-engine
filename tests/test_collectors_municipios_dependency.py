import pandas as pd

from src.collectors import cauc, dca


def test_cauc_run_carrega_municipios_sem_dependencia_de_csv(monkeypatch):
    published = {}

    municipios_df = pd.DataFrame(
        [
            {"cod_ibge": "2800100", "ente": "Amparo", "populacao": 2000},
            {"cod_ibge": "2800209", "ente": "Aquidaba", "populacao": 5000},
        ]
    )

    csv_text = "\n".join(
        [
            '"Data da Pesquisa: 2026-04-12"',
            'linha 2',
            'linha 3',
            'UF;Nome do Ente Federado;Código IBGE;Fonte',
            'SE;Amparo;2800100;CKAN',
            'SE;Aquidaba;2800209;CKAN',
            'MG;Abadia;3100104;CKAN',
        ]
    )

    class DummyResponse:
        content = csv_text.encode("utf-8")

        def raise_for_status(self):
            return None

    monkeypatch.setattr(cauc, "carregar_municipios", lambda **kwargs: municipios_df)
    monkeypatch.setattr(cauc.requests, "get", lambda *args, **kwargs: DummyResponse())
    monkeypatch.setattr(
        cauc,
        "publish_raw_merge",
        lambda df, table, uf, key_cols: published.update(
            {"df": df.copy(), "table": table, "uf": uf, "key_cols": key_cols}
        ),
    )

    result = cauc.run("SE")

    assert len(result) == 2
    assert result["Código IBGE"].tolist() == ["2800100", "2800209"]
    assert published["table"] == "cauc"
    assert published["uf"] == "SE"


def test_cauc_download_retry_em_erro_temporario(monkeypatch):
    chamadas = []
    csv_text = "\n".join(
        [
            '"Data da Pesquisa: 2026-04-12"',
            "linha 2",
            "linha 3",
            "UF;Nome do Ente Federado;Codigo IBGE;Fonte",
            "SE;Amparo;2800100;CKAN",
        ]
    )

    class DummyResponse:
        def __init__(self, status_code, content=b""):
            self.status_code = status_code
            self.content = content

        def raise_for_status(self):
            if self.status_code >= 400:
                exc = cauc.requests.HTTPError(f"{self.status_code} Server Error")
                exc.response = self
                raise exc

    def fake_get(*args, **kwargs):
        chamadas.append((args, kwargs))
        if len(chamadas) == 1:
            return DummyResponse(503)
        return DummyResponse(200, csv_text.encode("utf-8"))

    monkeypatch.setattr(cauc.requests, "get", fake_get)
    monkeypatch.setattr(cauc.time, "sleep", lambda _seconds: None)

    bulk_csv = cauc.download_cauc_bulk_csv(max_attempts=2, backoff_seconds=0)

    assert len(chamadas) == 2
    assert bulk_csv.data_pesquisa == "2026-04-12"
    assert len(bulk_csv.df_raw) == 1


def test_dca_run_carrega_municipios_sem_dependencia_de_csv(monkeypatch):
    published = {}
    municipios_df = pd.DataFrame(
        [
            {"cod_ibge": "2800100", "ente": "Amparo", "populacao": 2000},
        ]
    )
    coletado_df = pd.DataFrame(
        [
            {
                "cod_ibge": "2800100",
                "ente": "Amparo",
                "populacao": 2000,
                "ano": 2025,
                "ativo_financeiro": 10.0,
                "passivo_financeiro": 4.0,
                "rec_tributaria": 1.0,
                "rec_corrente": 8.0,
                "bp_disponivel": True,
                "rec_disponivel": True,
            }
        ]
    )

    monkeypatch.setattr(dca, "carregar_municipios", lambda **kwargs: municipios_df)
    monkeypatch.setattr(dca, "coletar_dca", lambda municipios, anos: coletado_df.copy())
    monkeypatch.setattr(
        dca,
        "publish_raw_merge",
        lambda df, table, uf, key_cols: published.update(
            {"df": df.copy(), "table": table, "uf": uf, "key_cols": key_cols}
        ),
    )

    result = dca.run(mode="incremental", uf="SE")

    assert len(result) == 1
    assert published["table"] == "dca"
    assert published["uf"] == "SE"

import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd

from processors import dca_postprocessor, siconfi_postprocessor


def test_dca_postprocessor_uses_loader_for_query_and_merge(monkeypatch):
    temp_root = Path.cwd() / ".pytest_artifacts" / f"dca_post_{uuid4().hex[:8]}"
    temp_root.mkdir(parents=True, exist_ok=True)
    calls = {"queries": [], "merge": None}

    def fake_project():
        return "proj_teste"

    def fake_query_to_dataframe(query: str, *, strict: bool = True):
        calls["queries"].append((query, strict))
        return pd.DataFrame(
            [
                {"cod_ibge": 2800100, "autonomia_raw": 0.05},
                {"cod_ibge": 2800100, "autonomia_raw": 0.07},
                {"cod_ibge": 2800209, "autonomia_raw": 0.10},
            ]
        )

    def fake_merge_dataframe_to_table(df, **kwargs):
        calls["merge"] = (df.copy(), kwargs)

    def fake_get_artifact_path(uf: str, artifact_key: str, **_kwargs):
        assert artifact_key == "dca_indicadores"
        processed = temp_root / "processed" / uf.upper()
        processed.mkdir(parents=True, exist_ok=True)
        return processed / f"dca_indicadores_{uf.lower()}.csv"

    monkeypatch.setattr(dca_postprocessor, "get_bigquery_project", fake_project)
    monkeypatch.setattr(dca_postprocessor, "query_to_dataframe", fake_query_to_dataframe)
    monkeypatch.setattr(dca_postprocessor, "merge_dataframe_to_table", fake_merge_dataframe_to_table)
    monkeypatch.setattr(dca_postprocessor, "get_artifact_path", fake_get_artifact_path)

    try:
        dca_postprocessor.run("SP")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    assert len(calls["queries"]) == 1
    query, strict = calls["queries"][0]
    assert strict is True
    assert "`proj_teste.intermediate.int_autonomia_base`" in query
    assert "WHERE m.uf = 'SP'" in query

    merged_df, kwargs = calls["merge"]
    assert kwargs["table_ref"] == "proj_teste.intermediate.int_dca_postprocessed"
    assert kwargs["temp_table_ref"] == "proj_teste.mart._tmp_dca_post"
    assert kwargs["key_cols"] == ["cod_ibge"]
    assert merged_df["uf"].tolist() == ["SP", "SP"]
    assert merged_df["autonomia_critica"].tolist() == [True, False]


def test_siconfi_postprocessor_uses_loader_for_query_and_merge(monkeypatch):
    temp_root = Path.cwd() / ".pytest_artifacts" / f"siconfi_post_{uuid4().hex[:8]}"
    temp_root.mkdir(parents=True, exist_ok=True)
    calls = {"queries": [], "merge": None}

    def fake_project():
        return "proj_teste"

    def fake_query_to_dataframe(query: str, *, strict: bool = True):
        calls["queries"].append((query, strict))

        if "int_eorcam" in query:
            return pd.DataFrame(
                [
                    {"cod_ibge": 2800100, "ano": 2025, "entregou_rreo": True, "eorcam_raw": 0.8},
                    {"cod_ibge": 2800100, "ano": 2024, "entregou_rreo": True, "eorcam_raw": 0.6},
                ]
            )
        if "int_lliq_base" in query:
            return pd.DataFrame(
                [
                    {
                        "cod_ibge": 2800100,
                        "ano": 2025,
                        "periodo_rgf": 2,
                        "periodicidade_rgf": "S",
                        "receita_realizada": 100.0,
                        "dcl_apos_rp_total": 10.0,
                        "dcl_apos_rp_rpps": 2.0,
                        "dcl_pre_rp_total": None,
                        "dcl_pre_rp_rpps": None,
                    }
                ]
            )
        if "SELECT cod_ibge, populacao FROM" in query:
            return pd.DataFrame([{"cod_ibge": 2800100, "populacao": 10000}])
        if "int_siconfi_indicadores_anuais" in query:
            return pd.DataFrame([{"cod_ibge": 2800100, "uf": "SE", "instituicao": "Teste", "ano": 2025}])
        raise AssertionError(f"Consulta nao esperada: {query}")

    def fake_merge_dataframe_to_table(df, **kwargs):
        calls["merge"] = (df.copy(), kwargs)

    def fake_get_artifact_path(uf: str, artifact_key: str, **_kwargs):
        processed = temp_root / "processed" / uf.upper()
        processed.mkdir(parents=True, exist_ok=True)
        filenames = {
            "siconfi_indicadores": f"siconfi_indicadores_{uf.lower()}.csv",
            "siconfi_postprocessed": f"siconfi_postprocessed_{uf.lower()}.csv",
        }
        return processed / filenames[artifact_key]

    monkeypatch.setattr(siconfi_postprocessor, "get_bigquery_project", fake_project)
    monkeypatch.setattr(siconfi_postprocessor, "query_to_dataframe", fake_query_to_dataframe)
    monkeypatch.setattr(siconfi_postprocessor, "merge_dataframe_to_table", fake_merge_dataframe_to_table)
    monkeypatch.setattr(siconfi_postprocessor, "get_artifact_path", fake_get_artifact_path)

    try:
        siconfi_postprocessor.run("SE")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    assert len(calls["queries"]) == 4
    assert all(strict is True for _, strict in calls["queries"])
    assert any("`proj_teste.intermediate.int_eorcam`" in query for query, _ in calls["queries"])
    assert any("`proj_teste.intermediate.int_lliq_base`" in query for query, _ in calls["queries"])
    assert any("`proj_teste.mart.mart_indicadores_municipios`" in query for query, _ in calls["queries"])
    assert any("`proj_teste.intermediate.int_siconfi_indicadores_anuais`" in query for query, _ in calls["queries"])

    merged_df, kwargs = calls["merge"]
    assert kwargs["table_ref"] == "proj_teste.intermediate.int_siconfi_postprocessed"
    assert kwargs["temp_table_ref"] == "proj_teste.mart._tmp_siconfi_post"
    assert kwargs["key_cols"] == ["cod_ibge"]
    assert merged_df["uf"].tolist() == ["SE"]
    assert "eorcam_raw" in merged_df.columns
    assert "lliq_raw" in merged_df.columns

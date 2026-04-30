import pandas as pd

from src.utils.bigquery_loader import (
    _build_merge_sql,
    _build_replace_slice_sql,
    _dedupe_by_keys,
    _merge_max_gib_for_table,
    _normalize_key_columns,
    _replace_slice_max_gib_for_table,
    _sanitize,
)


def test_normalize_key_columns_matches_sanitize_rules():
    assert _normalize_key_columns(["cod_ibge", "data coleta", "1.1"]) == [
        "cod_ibge",
        "data_coleta",
        "c_1_1",
    ]


def test_sanitize_adds_and_normalizes_uf():
    df = pd.DataFrame(
        [
            {"cod_ibge": "2500106", "valor": 1},
            {"cod_ibge": "2500205", "valor": 2},
        ]
    )
    result = _sanitize(df, "pb")
    assert "uf" in result.columns
    assert set(result["uf"].tolist()) == {"PB"}


def test_dedupe_by_keys_keeps_last():
    df = pd.DataFrame(
        [
            {"uf": "PB", "cod_ibge": "2500106", "ano": "2024", "valor": "1"},
            {"uf": "PB", "cod_ibge": "2500106", "ano": "2024", "valor": "2"},
            {"uf": "PB", "cod_ibge": "2500205", "ano": "2024", "valor": "3"},
        ]
    )
    result = _dedupe_by_keys(df, ["uf", "cod_ibge", "ano"], "dca", "PB")
    assert len(result) == 2
    valor = result.loc[result["cod_ibge"] == "2500106", "valor"].iloc[0]
    assert valor == "2"


def test_build_merge_sql_contains_keys_and_insert():
    sql = _build_merge_sql(
        target_ref="proj.raw.dca",
        temp_ref="proj.raw.__tmp_dca",
        cols=["uf", "cod_ibge", "ano", "valor"],
        key_cols=["uf", "cod_ibge", "ano"],
    )
    assert "MERGE `proj.raw.dca` T" in sql
    assert "USING `proj.raw.__tmp_dca` S" in sql
    assert "T.`uf` = S.`uf`" in sql
    assert "T.`cod_ibge` = S.`cod_ibge`" in sql
    assert "T.`ano` = S.`ano`" in sql
    assert "WHEN NOT MATCHED THEN" in sql
    assert "INSERT (`uf`, `cod_ibge`, `ano`, `valor`)" in sql


def test_build_replace_slice_sql_deletes_only_requested_slice_before_insert():
    sql = _build_replace_slice_sql(
        target_ref="proj.raw.siconfi_rreo",
        temp_ref="proj.raw.__tmp_siconfi_rreo",
        cols=["uf", "cod_ibge", "exercicio", "valor"],
        slice_cols=["exercicio"],
    )

    assert "BEGIN TRANSACTION;" in sql
    assert "DELETE FROM `proj.raw.siconfi_rreo`" in sql
    assert "`uf` = @uf AND `exercicio` IN UNNEST(@slice_exercicio)" in sql
    assert "INSERT INTO `proj.raw.siconfi_rreo` (`uf`, `cod_ibge`, `exercicio`, `valor`)" in sql
    assert "FROM `proj.raw.__tmp_siconfi_rreo`" in sql
    assert "COMMIT TRANSACTION;" in sql


def test_merge_max_gib_uses_table_default(monkeypatch):
    monkeypatch.delenv("BQ_MERGE_MAX_GIB_SICONFI_RREO", raising=False)
    monkeypatch.delenv("BQ_MERGE_MAX_GIB_DEFAULT", raising=False)

    assert _merge_max_gib_for_table("siconfi_rreo") == 10.0


def test_merge_max_gib_specific_env_overrides_default(monkeypatch):
    monkeypatch.setenv("BQ_MERGE_MAX_GIB_DEFAULT", "3")
    monkeypatch.setenv("BQ_MERGE_MAX_GIB_SICONFI_RREO", "12.5")

    assert _merge_max_gib_for_table("siconfi_rreo") == 12.5


def test_replace_slice_max_gib_uses_table_default(monkeypatch):
    monkeypatch.delenv("BQ_REPLACE_SLICE_MAX_GIB_SICONFI_RREO", raising=False)
    monkeypatch.delenv("BQ_REPLACE_SLICE_MAX_GIB_DEFAULT", raising=False)

    assert _replace_slice_max_gib_for_table("siconfi_rreo") == 2.0


def test_replace_slice_max_gib_specific_env_overrides_default(monkeypatch):
    monkeypatch.setenv("BQ_REPLACE_SLICE_MAX_GIB_DEFAULT", "0.5")
    monkeypatch.setenv("BQ_REPLACE_SLICE_MAX_GIB_SICONFI_RREO", "1.25")

    assert _replace_slice_max_gib_for_table("siconfi_rreo") == 1.25

import shutil
from pathlib import Path
from uuid import uuid4

from src.utils import paths


def _make_scratch(prefix: str) -> Path:
    root = Path.cwd() / ".pytest_artifacts" / f"{prefix}_{uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_get_artifact_path_preserves_current_public_filenames():
    scratch = _make_scratch("paths_contract")
    try:
        assert paths.get_artifact_path("SE", "municipios_tabela", root=scratch) == (
            scratch / "data" / "processed" / "SE" / "municipios_se_tabela.csv"
        )
        assert paths.get_artifact_path("SE", "score_municipios_pncp", root=scratch) == (
            scratch / "data" / "outputs" / "SE" / "score_municipios_se_pncp.csv"
        )
        assert paths.get_artifact_path("SE", "pncp_checkpoint", root=scratch) == (
            scratch / "data" / "raw" / "pncp" / "SE" / "pncp_parcial_se.jsonl"
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_find_ufs_with_artifact_uses_explicit_artifact_contract():
    scratch = _make_scratch("paths_find")
    try:
        pb_csv = paths.get_artifact_path("PB", "municipios_tabela", root=scratch)
        pb_csv.touch()

        se_dir = scratch / "data" / "processed" / "SE"
        se_dir.mkdir(parents=True, exist_ok=True)
        (se_dir / "arquivo_solto.csv").touch()

        assert paths.find_ufs_with_artifact("municipios_tabela", root=scratch) == ["PB"]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_bigquery_csv_fallback_paths_are_not_hardcoded_to_pb():
    scratch = _make_scratch("paths_fallback")
    try:
        candidates = paths.get_bigquery_csv_fallback_paths(
            "score_municipios",
            uf="SE",
            root=scratch,
        )

        assert candidates == [
            scratch / "data" / "outputs" / "SE" / "score_municipios_se.csv",
            scratch / "data" / "outputs" / "SE" / "score_municipios_se_pncp.csv",
        ]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_legacy_aliases_remain_available_for_pb():
    assert paths.PROCESSED == paths.get_artifact_path("PB", "municipios_tabela").parent
    assert paths.OUTPUTS == paths.get_artifact_path("PB", "score_municipios_pncp").parent

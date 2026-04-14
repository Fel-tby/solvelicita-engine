import builtins
import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest

import pipeline


def _make_workspace_scratch_dir(prefix: str) -> Path:
    root = Path.cwd() / "_tmp_tests" / f"{prefix}_{uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_coletores_execucao_preserva_contrato_atual():
    assert pipeline.coletores_execucao("PB", {"collect"}, None) == pipeline.COLETORES_ORDEM
    assert pipeline.coletores_execucao("ALL", {"collect"}, None) == ["cauc"]
    assert pipeline.coletores_execucao("PB", {"score", "sync"}, None) is None


def test_descobrir_ufs_presentes_usa_artefato_processed_por_uf(monkeypatch):
    root = _make_workspace_scratch_dir("pipeline_processed")
    try:
        monkeypatch.setattr(pipeline, "ROOT", root)

        pb_dir = root / "data" / "processed" / "PB"
        pb_dir.mkdir(parents=True)
        (pb_dir / "municipios_pb_tabela.csv").touch()

        se_dir = root / "data" / "processed" / "SE"
        se_dir.mkdir(parents=True)
        (se_dir / "municipios_se_tabela.csv").touch()

        ce_dir = root / "data" / "processed" / "CE"
        ce_dir.mkdir(parents=True)
        (ce_dir / "outro_arquivo.csv").touch()

        assert pipeline.descobrir_ufs_presentes() == ["PB", "SE"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_descobrir_ufs_presentes_sync_only_usa_score_pncp_por_uf(monkeypatch):
    root = _make_workspace_scratch_dir("pipeline_outputs")
    try:
        monkeypatch.setattr(pipeline, "ROOT", root)

        pb_dir = root / "data" / "outputs" / "PB"
        pb_dir.mkdir(parents=True)
        (pb_dir / "score_municipios_pb_pncp.csv").touch()

        rn_dir = root / "data" / "outputs" / "RN"
        rn_dir.mkdir(parents=True)
        (rn_dir / "score_municipios_rn.csv").touch()

        assert pipeline.descobrir_ufs_presentes(for_sync_only=True) == ["PB"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_main_non_interactive_preserva_defaults_operacionais(monkeypatch):
    chamadas = []

    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--yes"])
    monkeypatch.setattr(pipeline.time, "time", lambda: 0.0)
    monkeypatch.setattr(pipeline, "get_paths", lambda uf: chamadas.append(("get_paths", uf)))
    monkeypatch.setattr(
        pipeline,
        "etapa_collect",
        lambda mode, uf, coletores=None: chamadas.append(("collect", mode, uf, coletores)),
    )
    monkeypatch.setattr(pipeline, "etapa_dbt", lambda uf: chamadas.append(("dbt", uf)))
    monkeypatch.setattr(pipeline, "etapa_process", lambda uf: chamadas.append(("process", uf)))
    monkeypatch.setattr(
        pipeline,
        "etapa_score",
        lambda uf, mode=None: chamadas.append(("score", uf, mode)),
    )
    monkeypatch.setattr(pipeline, "etapa_sync", lambda uf: chamadas.append(("sync", uf)))
    monkeypatch.setattr(
        builtins,
        "input",
        lambda *_args, **_kwargs: pytest.fail("input nao deveria ser chamado com --yes"),
    )

    pipeline.main()

    assert chamadas == [
        ("get_paths", "PB"),
        ("collect", "incremental", "PB", pipeline.COLETORES_ORDEM),
        ("dbt", "PB"),
        ("process", "PB"),
        ("score", "PB", "incremental"),
        ("sync", "PB"),
    ]

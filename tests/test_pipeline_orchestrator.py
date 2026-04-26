import builtins
import sys

import pytest

import pipeline


def test_normalizar_coletores_ordena_e_remove_duplicatas():
    assert pipeline.normalizar_coletores("pncp,cauc,pncp,dca") == ["cauc", "dca", "pncp"]


def test_normalizar_coletores_rejeita_invalido():
    with pytest.raises(ValueError):
        pipeline.normalizar_coletores("cauc,invalido")


def test_validar_uf_all_legado_usa_brasil_oficial():
    ufs, all_legado = pipeline.validar_uf_all(
        "incremental",
        {"collect", "dbt", "process", "score", "sync"},
        None,
    )

    assert ufs == pipeline.ALL_UFS_BRASIL
    assert all_legado is True


def test_validar_uf_all_real_usa_brasil_oficial():
    ufs, all_legado = pipeline.validar_uf_all(
        "incremental",
        {"collect", "dbt", "process", "score", "sync"},
        ["cauc", "siconfi"],
    )

    assert ufs == pipeline.ALL_UFS_BRASIL
    assert all_legado is False


def test_all_ufs_brasil_contem_27_unidades_federativas():
    assert len(pipeline.ALL_UFS_BRASIL) == 27
    assert "DF" in pipeline.ALL_UFS_BRASIL
    assert "SP" in pipeline.ALL_UFS_BRASIL


def test_region_sul_resolve_ufs_oficiais():
    assert pipeline.normalizar_regiao("sul") == "SUL"
    assert pipeline.ufs_da_regiao("SUL") == ["PR", "RS", "SC"]


def test_validar_uf_all_sem_collect_filtra_mg(monkeypatch):
    monkeypatch.setattr(
        pipeline.pipeline_jobs,
        "discover_present_ufs_job",
        lambda request: pipeline.pipeline_jobs.DiscoverPresentUfsResult(["MG", "PB", "SE"]),
    )

    ufs, all_legado = pipeline.validar_uf_all("incremental", {"process", "score", "sync"})

    assert ufs == ["MG", "PB", "SE"]
    assert all_legado is False


def test_main_all_collect_real_usa_collectors_e_nao_chama_prompt(monkeypatch):
    chamadas = []

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pipeline.py",
            "--uf",
            "ALL",
            "--mode",
            "incremental",
            "--steps",
            "collect,dbt,process,score,sync",
            "--collectors",
            "cauc",
            "--yes",
        ],
    )
    monkeypatch.setattr(pipeline.time, "time", lambda: 0.0)
    monkeypatch.setattr(pipeline, "etapa_collect_all", lambda mode, ufs, coletores: chamadas.append(("collect_all", mode, ufs, coletores)))
    monkeypatch.setattr(pipeline, "etapa_collect_cauc_incremental_all", lambda ufs: chamadas.append(("collect_legado", ufs)))
    monkeypatch.setattr(pipeline, "etapa_dbt", lambda uf: chamadas.append(("dbt", uf)))
    monkeypatch.setattr(pipeline, "etapa_process", lambda uf: chamadas.append(("process", uf)))
    monkeypatch.setattr(pipeline, "etapa_score", lambda uf, mode=None: chamadas.append(("score", uf, mode)))
    monkeypatch.setattr(pipeline, "etapa_sync", lambda uf: chamadas.append(("sync", uf)))
    monkeypatch.setattr(builtins, "input", lambda *_args, **_kwargs: pytest.fail("input nao deveria ser chamado com --yes"))

    pipeline.main()

    assert ("collect_all", "incremental", pipeline.ALL_UFS_BRASIL, ["cauc"]) in chamadas
    assert not any(item[0] == "collect_legado" for item in chamadas)


def test_main_all_collect_sem_collectors_permanece_legado(monkeypatch):
    chamadas = []

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pipeline.py",
            "--uf",
            "ALL",
            "--mode",
            "incremental",
            "--steps",
            "collect,dbt,process,score,sync",
            "--yes",
        ],
    )
    monkeypatch.setattr(pipeline.time, "time", lambda: 0.0)
    monkeypatch.setattr(pipeline, "etapa_collect_all", lambda mode, ufs, coletores: chamadas.append(("collect_all", mode, ufs, coletores)))
    monkeypatch.setattr(pipeline, "etapa_collect_cauc_incremental_all", lambda ufs: chamadas.append(("collect_legado", ufs)))
    monkeypatch.setattr(pipeline, "etapa_dbt", lambda uf: chamadas.append(("dbt", uf)))
    monkeypatch.setattr(pipeline, "etapa_process", lambda uf: chamadas.append(("process", uf)))
    monkeypatch.setattr(pipeline, "etapa_score", lambda uf, mode=None: chamadas.append(("score", uf, mode)))
    monkeypatch.setattr(pipeline, "etapa_sync", lambda uf: chamadas.append(("sync", uf)))
    monkeypatch.setattr(builtins, "input", lambda *_args, **_kwargs: pytest.fail("input nao deveria ser chamado com --yes"))

    pipeline.main()

    assert ("collect_legado", pipeline.ALL_UFS_BRASIL) in chamadas
    assert not any(item[0] == "collect_all" for item in chamadas)


def test_main_region_collect_full_usa_ufs_da_regiao(monkeypatch):
    chamadas = []

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pipeline.py",
            "--region",
            "SUL",
            "--mode",
            "full",
            "--steps",
            "collect",
            "--collectors",
            "cauc",
            "--yes",
        ],
    )
    monkeypatch.setattr(pipeline.time, "time", lambda: 0.0)
    monkeypatch.setattr(pipeline, "etapa_collect_all", lambda mode, ufs, coletores: chamadas.append(("collect_all", mode, ufs, coletores)))
    monkeypatch.setattr(pipeline, "etapa_collect_cauc_incremental_all", lambda ufs: chamadas.append(("collect_legado", ufs)))
    monkeypatch.setattr(pipeline, "etapa_dbt", lambda uf: chamadas.append(("dbt", uf)))
    monkeypatch.setattr(pipeline, "etapa_process", lambda uf: chamadas.append(("process", uf)))
    monkeypatch.setattr(pipeline, "etapa_score", lambda uf, mode=None: chamadas.append(("score", uf, mode)))
    monkeypatch.setattr(pipeline, "etapa_sync", lambda uf: chamadas.append(("sync", uf)))
    monkeypatch.setattr(builtins, "input", lambda *_args, **_kwargs: pytest.fail("input nao deveria ser chamado com --yes"))

    pipeline.main()

    assert ("collect_all", "full", ["PR", "RS", "SC"], ["cauc"]) in chamadas
    assert not any(item[0] == "collect_legado" for item in chamadas)

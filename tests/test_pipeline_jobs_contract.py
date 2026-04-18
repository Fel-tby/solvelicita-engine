from pathlib import Path

from src.jobs import pipeline_jobs


def test_execute_pipeline_run_returns_explicit_result_for_single_uf():
    calls = []

    deps = pipeline_jobs.PipelineExecutionDeps(
        prepare_paths=lambda uf: calls.append(("prepare_paths", uf)),
        run_collect=lambda mode, uf, coletores=None: calls.append(("collect", mode, uf, coletores)),
        run_collect_legacy_all=lambda ufs: calls.append(("collect_legacy_all", tuple(ufs))),
        run_collect_all=lambda mode, ufs, coletores: calls.append(
            ("collect_all", mode, tuple(ufs), tuple(coletores))
        ),
        run_dbt=lambda uf: calls.append(("dbt", uf)),
        run_process=lambda uf: calls.append(("process", uf)),
        run_score=lambda uf, mode=None: calls.append(("score", uf, mode)),
        run_sync=lambda uf: calls.append(("sync", uf)),
    )

    result = pipeline_jobs.execute_pipeline_run(
        pipeline_jobs.PipelineRunInput(
            uf="PB",
            mode="incremental",
            etapas={"collect", "dbt", "process", "score", "sync"},
            coletores=None,
            root=Path.cwd(),
        ),
        deps,
    )

    assert isinstance(result, pipeline_jobs.PipelineRunResult)
    assert result.run_id
    assert result.status == "succeeded"
    assert result.uf == "PB"
    assert result.mode == "incremental"
    assert result.target_ufs == ["PB"]
    assert result.requested_steps == ["collect", "dbt", "process", "score", "sync"]
    assert result.coletores_resolvidos == pipeline_jobs.COLETORES_ORDEM
    assert result.all_legado is False
    assert [(step.step, step.target, step.mode, step.status) for step in result.steps_executed] == [
        ("collect", "PB", "incremental", "succeeded"),
        ("dbt", "PB", None, "succeeded"),
        ("process", "PB", None, "succeeded"),
        ("score", "PB", "incremental", "succeeded"),
        ("sync", "PB", None, "succeeded"),
    ]
    assert all(step.duration_seconds >= 0 for step in result.steps_executed)
    assert calls == [
        ("prepare_paths", "PB"),
        ("collect", "incremental", "PB", pipeline_jobs.COLETORES_ORDEM),
        ("dbt", "PB"),
        ("process", "PB"),
        ("score", "PB", "incremental"),
        ("sync", "PB"),
    ]


def test_validate_all_uf_job_returns_explicit_result_for_legacy_collect_all():
    result = pipeline_jobs.validate_all_uf_job(
        pipeline_jobs.ValidateAllUfInput(
            mode="incremental",
            etapas={"collect", "dbt", "process", "score", "sync"},
            coletores=None,
            root=Path.cwd(),
        )
    )

    assert isinstance(result, pipeline_jobs.ValidateAllUfResult)
    assert result.ufs == pipeline_jobs.ALL_UFS_NORDESTE
    assert result.all_legado is True


def test_resolve_collectors_job_returns_explicit_result():
    result = pipeline_jobs.resolve_collectors_job(
        pipeline_jobs.ResolveCollectorsInput(
            uf="PB",
            etapas={"collect", "score"},
            coletores=["cauc", "pncp"],
        )
    )

    assert isinstance(result, pipeline_jobs.ResolveCollectorsResult)
    assert result.coletores == ["cauc", "pncp"]


def test_run_collect_all_job_reusa_download_cauc(monkeypatch):
    sentinel = object()
    chamadas = []

    monkeypatch.setattr(pipeline_jobs, "get_paths", lambda uf: None)
    monkeypatch.setattr(
        pipeline_jobs.cauc,
        "download_cauc_bulk_csv",
        lambda: chamadas.append(("download_cauc",)) or sentinel,
    )
    monkeypatch.setattr(
        pipeline_jobs.cauc,
        "run",
        lambda uf, bulk_csv=None: chamadas.append(("cauc", uf, bulk_csv)),
    )

    result = pipeline_jobs.run_collect_all_job(
        pipeline_jobs.CollectAllJobInput(
            mode="incremental",
            ufs=["AL", "BA", "CE"],
            coletores=["cauc"],
        )
    )

    assert isinstance(result, pipeline_jobs.CollectAllJobResult)
    assert chamadas == [
        ("download_cauc",),
        ("cauc", "AL", sentinel),
        ("cauc", "BA", sentinel),
        ("cauc", "CE", sentinel),
    ]


def test_execute_pipeline_run_wraps_failed_step_with_partial_result():
    deps = pipeline_jobs.PipelineExecutionDeps(
        prepare_paths=lambda uf: None,
        run_collect=lambda mode, uf, coletores=None: None,
        run_collect_legacy_all=lambda ufs: None,
        run_collect_all=lambda mode, ufs, coletores: None,
        run_dbt=lambda uf: (_ for _ in ()).throw(RuntimeError("dbt explodiu")),
        run_process=lambda uf: None,
        run_score=lambda uf, mode=None: None,
        run_sync=lambda uf: None,
    )

    try:
        pipeline_jobs.execute_pipeline_run(
            pipeline_jobs.PipelineRunInput(
                uf="PB",
                mode="incremental",
                etapas={"collect", "dbt"},
                coletores=None,
                root=Path.cwd(),
                run_id="run_teste",
            ),
            deps,
        )
    except pipeline_jobs.PipelineExecutionError as exc:
        result = exc.result
    else:
        raise AssertionError("Esperava PipelineExecutionError")

    assert result.run_id == "run_teste"
    assert result.status == "failed"
    assert [(step.step, step.status) for step in result.steps_executed] == [
        ("collect", "succeeded"),
        ("dbt", "failed"),
    ]
    assert result.steps_executed[-1].error_message == "dbt explodiu"

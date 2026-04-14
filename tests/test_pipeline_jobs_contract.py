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
    assert result.target_ufs == ["PB"]
    assert result.coletores_resolvidos == pipeline_jobs.COLETORES_ORDEM
    assert result.all_legado is False
    assert [(step.step, step.target, step.mode) for step in result.steps_executed] == [
        ("collect", "PB", "incremental"),
        ("dbt", "PB", None),
        ("process", "PB", None),
        ("score", "PB", "incremental"),
        ("sync", "PB", None),
    ]
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

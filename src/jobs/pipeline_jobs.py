from __future__ import annotations

import os
import platform
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.config.settings import build_runtime_env
from src.collectors import cauc, dca, municipios, pncp, siconfi
from src.engine import solvency
from src.processors import dca_postprocessor, siconfi_postprocessor
from src.utils.paths import find_ufs_with_artifact, get_paths
from src.utils.run_observability import build_run_id, isoformat_utc, utc_now
from src.utils.supabase_sync import run as supabase_sync

ETAPAS_VALIDAS = {"collect", "dbt", "process", "score", "sync"}
ETAPAS_ORDEM = ["collect", "dbt", "process", "score", "sync"]
COLETORES_VALIDOS = {"municipios", "cauc", "siconfi", "dca", "pncp"}
COLETORES_ORDEM = ["municipios", "cauc", "siconfi", "dca", "pncp"]
ALL_UFS_TOKEN = "ALL"
ALL_UFS_NORDESTE = ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]
ALL_UFS_BRASIL = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
    "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
    "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]


@dataclass(frozen=True)
class CollectJobInput:
    mode: str
    uf: str
    coletores: list[str] | None = None
    cauc_bulk_provider: Callable[[], cauc.CaucBulkCsv] | None = None


@dataclass(frozen=True)
class CollectJobResult:
    uf: str
    mode: str
    coletores_executados: list[str]


@dataclass(frozen=True)
class CollectLegacyAllJobInput:
    ufs: list[str]


@dataclass(frozen=True)
class CollectLegacyAllJobResult:
    ufs: list[str]


@dataclass(frozen=True)
class CollectAllJobInput:
    mode: str
    ufs: list[str]
    coletores: list[str]


@dataclass(frozen=True)
class CollectAllJobResult:
    mode: str
    ufs: list[str]
    coletores_executados: list[str]


@dataclass(frozen=True)
class DbtJobInput:
    uf: str
    root: Path


@dataclass(frozen=True)
class DbtJobResult:
    uf: str
    executable: Path


@dataclass(frozen=True)
class ProcessJobInput:
    uf: str


@dataclass(frozen=True)
class ProcessJobResult:
    uf: str


@dataclass(frozen=True)
class ScoreJobInput:
    uf: str
    pipeline_version: str
    mode: str | None = None


@dataclass(frozen=True)
class ScoreJobResult:
    uf: str
    pipeline_version: str
    mode: str | None


@dataclass(frozen=True)
class SyncJobInput:
    uf: str


@dataclass(frozen=True)
class SyncJobResult:
    uf: str


@dataclass(frozen=True)
class DiscoverPresentUfsInput:
    root: Path
    for_sync_only: bool = False


@dataclass(frozen=True)
class DiscoverPresentUfsResult:
    ufs: list[str]


@dataclass(frozen=True)
class ResolveCollectorsInput:
    uf: str
    etapas: set[str]
    coletores: list[str] | None


@dataclass(frozen=True)
class ResolveCollectorsResult:
    coletores: list[str] | None


@dataclass(frozen=True)
class ValidateAllUfInput:
    mode: str
    etapas: set[str]
    coletores: list[str] | None
    root: Path


@dataclass(frozen=True)
class ValidateAllUfResult:
    ufs: list[str]
    all_legado: bool


@dataclass(frozen=True)
class PipelineRunInput:
    uf: str
    mode: str
    etapas: set[str]
    coletores: list[str] | None
    root: Path
    run_id: str | None = None


@dataclass(frozen=True)
class ExecutedStepResult:
    step: str
    target: str
    status: str
    started_at: str
    finished_at: str
    duration_seconds: float
    mode: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class PipelineRunResult:
    run_id: str
    status: str
    started_at: str
    finished_at: str
    duration_seconds: float
    uf: str
    mode: str
    target_ufs: list[str]
    requested_steps: list[str]
    coletores_resolvidos: list[str] | None
    all_legado: bool
    steps_executed: list[ExecutedStepResult]


class PipelineExecutionError(RuntimeError):
    def __init__(self, result: PipelineRunResult, cause: Exception):
        self.result = result
        self.cause = cause
        super().__init__(str(cause))


@dataclass(frozen=True)
class PipelineExecutionDeps:
    prepare_paths: Callable[[str], object]
    run_collect: Callable[[str, str, list[str] | None], object]
    run_collect_legacy_all: Callable[[list[str]], object]
    run_collect_all: Callable[[str, list[str], list[str]], object]
    run_dbt: Callable[[str], object]
    run_process: Callable[[str], object]
    run_score: Callable[[str, str | None], object]
    run_sync: Callable[[str], object]


def _step_start(run_id: str, step: str, target: str, mode: str | None) -> tuple[datetime, float]:
    started_at = utc_now()
    mode_scope = f" mode={mode}" if mode else ""
    print(
        f"  [RUN {run_id}] inicio step={step} target={target}{mode_scope} "
        f"at={isoformat_utc(started_at)}"
    )
    return started_at, time.perf_counter()


def _step_end(
    *,
    run_id: str,
    step: str,
    target: str,
    mode: str | None,
    started_at: datetime,
    started_perf: float,
    status: str,
    error_message: str | None = None,
) -> ExecutedStepResult:
    finished_at = utc_now()
    duration_seconds = round(time.perf_counter() - started_perf, 3)
    mode_scope = f" mode={mode}" if mode else ""
    line = (
        f"  [RUN {run_id}] fim step={step} target={target}{mode_scope} "
        f"status={status} duracao={duration_seconds:.3f}s at={isoformat_utc(finished_at)}"
    )
    if error_message:
        line += f" erro={error_message}"
    print(line)
    return ExecutedStepResult(
        step=step,
        target=target,
        status=status,
        started_at=isoformat_utc(started_at),
        finished_at=isoformat_utc(finished_at),
        duration_seconds=duration_seconds,
        mode=mode,
        error_message=error_message,
    )


def _execute_tracked_step(
    *,
    run_id: str,
    step: str,
    target: str,
    mode: str | None,
    runner: Callable[[], object],
) -> ExecutedStepResult:
    started_at, started_perf = _step_start(run_id, step, target, mode)
    try:
        runner()
    except Exception as exc:
        return _step_end(
            run_id=run_id,
            step=step,
            target=target,
            mode=mode,
            started_at=started_at,
            started_perf=started_perf,
            status="failed",
            error_message=str(exc),
        )

    return _step_end(
        run_id=run_id,
        step=step,
        target=target,
        mode=mode,
        started_at=started_at,
        started_perf=started_perf,
        status="succeeded",
    )


def _build_run_result(
    *,
    run_id: str,
    status: str,
    run_started_at: datetime,
    request: PipelineRunInput,
    target_ufs: list[str],
    resolved_collectors: list[str] | None,
    all_legado: bool,
    steps_executed: list[ExecutedStepResult],
) -> PipelineRunResult:
    finished_at = utc_now()
    return PipelineRunResult(
        run_id=run_id,
        status=status,
        started_at=isoformat_utc(run_started_at),
        finished_at=isoformat_utc(finished_at),
        duration_seconds=round((finished_at - run_started_at).total_seconds(), 3),
        uf=request.uf,
        mode=request.mode,
        target_ufs=target_ufs,
        requested_steps=[step for step in ETAPAS_ORDEM if step in request.etapas],
        coletores_resolvidos=resolved_collectors,
        all_legado=all_legado,
        steps_executed=steps_executed,
    )


def _build_cauc_bulk_provider() -> Callable[[], cauc.CaucBulkCsv]:
    bulk_csv: cauc.CaucBulkCsv | None = None

    def get_bulk_csv() -> cauc.CaucBulkCsv:
        nonlocal bulk_csv
        if bulk_csv is None:
            bulk_csv = cauc.download_cauc_bulk_csv()
        return bulk_csv

    return get_bulk_csv


def run_collect_job(request: CollectJobInput) -> CollectJobResult:
    print("\n" + "=" * 55)
    print(f"  ETAPA: COLETA [{request.mode.upper()}] - {request.uf}")
    print("=" * 55)

    coletores_ativos = request.coletores or list(COLETORES_ORDEM)
    etapas_coleta: list[tuple[str, Callable[[], None]]] = []

    if "municipios" in coletores_ativos:
        etapas_coleta.append(("Municipios", lambda: municipios.run(uf=request.uf)))
    if "cauc" in coletores_ativos:
        etapas_coleta.append(
            (
                "CAUC",
                lambda: cauc.run(
                    uf=request.uf,
                    bulk_csv=(
                        request.cauc_bulk_provider()
                        if request.cauc_bulk_provider is not None
                        else None
                    ),
                ),
            )
        )
    if "siconfi" in coletores_ativos:
        etapas_coleta.append(
            (
                f"SICONFI [{request.mode}]",
                lambda: siconfi.run(mode=request.mode, uf=request.uf),
            )
        )
    if "dca" in coletores_ativos:
        etapas_coleta.append(
            (f"DCA [{request.mode}]", lambda: dca.run(mode=request.mode, uf=request.uf))
        )
    if "pncp" in coletores_ativos:
        etapas_coleta.append(
            (f"PNCP [{request.mode}]", lambda: pncp.run(mode=request.mode, uf=request.uf))
        )

    total = len(etapas_coleta)
    for idx, (label, runner) in enumerate(etapas_coleta, start=1):
        print(f"\n[{idx}/{total}] {label}...")
        runner()

    return CollectJobResult(
        uf=request.uf,
        mode=request.mode,
        coletores_executados=list(coletores_ativos),
    )


def run_collect_legacy_all_job(request: CollectLegacyAllJobInput) -> CollectLegacyAllJobResult:
    print("\n" + "=" * 55)
    print("  ETAPA: COLETA INCREMENTAL CAUC - ALL (LEGADO)")
    print("=" * 55)

    total = len(request.ufs)
    cauc_bulk_provider = _build_cauc_bulk_provider()
    for idx, uf in enumerate(request.ufs, start=1):
        print(f"\n[{idx}/{total}] CAUC incremental - {uf}...")
        get_paths(uf)
        cauc.run(uf=uf, bulk_csv=cauc_bulk_provider())

    return CollectLegacyAllJobResult(ufs=list(request.ufs))


def run_collect_all_job(request: CollectAllJobInput) -> CollectAllJobResult:
    total = len(request.ufs)
    cauc_bulk_provider = (
        _build_cauc_bulk_provider() if "cauc" in request.coletores else None
    )
    for idx, uf in enumerate(request.ufs, start=1):
        print("\n" + "-" * 55)
        print(f"  COLETA ALL [{idx}/{total}] - {uf}")
        print("-" * 55)
        get_paths(uf)
        run_collect_job(
            CollectJobInput(
                mode=request.mode,
                uf=uf,
                coletores=request.coletores,
                cauc_bulk_provider=cauc_bulk_provider,
            )
        )

    return CollectAllJobResult(
        mode=request.mode,
        ufs=list(request.ufs),
        coletores_executados=list(request.coletores),
    )


def run_dbt_job(request: DbtJobInput) -> DbtJobResult:
    print("\n" + "=" * 55)
    print(f"  ETAPA: DBT TRANSFORM - {request.uf}")
    print("=" * 55)

    print("\n[1/1] Rodando modelos do dbt no BigQuery (via venv_dbt)...")

    if platform.system() == "Windows":
        dbt_exe = request.root / "venv_dbt" / "Scripts" / "dbt.exe"
    else:
        dbt_exe = request.root / "venv_dbt" / "bin" / "dbt"

    if not dbt_exe.exists():
        raise FileNotFoundError(f"executavel dbt nao encontrado em: {dbt_exe}")

    env = build_runtime_env(os.environ.copy())
    result = subprocess.run([str(dbt_exe), "run"], cwd=str(request.root / "dbt"), env=env)
    if result.returncode != 0:
        raise RuntimeError(f"erro na execucao do dbt (exit={result.returncode})")

    return DbtJobResult(uf=request.uf, executable=dbt_exe)


def run_process_job(request: ProcessJobInput) -> ProcessJobResult:
    print("\n" + "=" * 55)
    print(f"  ETAPA: POSTPROCESSORS BigQuery - {request.uf}")
    print("=" * 55)

    print("\n[1/2] SICONFI postprocessor...")
    siconfi_postprocessor.run(uf=request.uf)

    print("\n[2/2] DCA postprocessor...")
    dca_postprocessor.run(uf=request.uf)

    return ProcessJobResult(uf=request.uf)


def run_score_job(request: ScoreJobInput) -> ScoreJobResult:
    print("\n" + "=" * 55)
    print(f"  ETAPA: SCORE - {request.uf}")
    print("=" * 55)

    print("\n[1/1] Solvency engine (source=bigquery)...")
    solvency.run(
        uf=request.uf,
        source="bigquery",
        strict_bigquery=True,
        publish_snapshot=True,
        run_type="pipeline",
        pipeline_mode=request.mode,
        pipeline_version=request.pipeline_version,
    )

    return ScoreJobResult(
        uf=request.uf,
        pipeline_version=request.pipeline_version,
        mode=request.mode,
    )


def run_sync_job(request: SyncJobInput) -> SyncJobResult:
    print("\n" + "=" * 55)
    print(f"  ETAPA: SYNC - Supabase - {request.uf}")
    print("=" * 55)

    print("\n[1/1] Sincronizando com Supabase...")
    supabase_sync(uf=request.uf)
    return SyncJobResult(uf=request.uf)


def discover_present_ufs_job(request: DiscoverPresentUfsInput) -> DiscoverPresentUfsResult:
    if request.for_sync_only:
        return DiscoverPresentUfsResult(
            ufs=find_ufs_with_artifact("score_municipios_pncp", root=request.root)
        )

    return DiscoverPresentUfsResult(
        ufs=find_ufs_with_artifact("municipios_tabela", root=request.root)
    )


def filter_ufs_all(ufs: list[str]) -> list[str]:
    return [uf for uf in ALL_UFS_NORDESTE if uf in set(ufs)]


def resolve_collectors_job(request: ResolveCollectorsInput) -> ResolveCollectorsResult:
    if "collect" not in request.etapas:
        return ResolveCollectorsResult(coletores=None)
    if request.uf == ALL_UFS_TOKEN and request.coletores is None:
        return ResolveCollectorsResult(coletores=["cauc"])
    if request.coletores is None:
        return ResolveCollectorsResult(coletores=list(COLETORES_ORDEM))
    return ResolveCollectorsResult(coletores=list(request.coletores))


def validate_all_uf_job(request: ValidateAllUfInput) -> ValidateAllUfResult:
    permitido_sem_collect = {"process", "score", "sync"}
    permitido_com_collect_legado = {"collect", "dbt", "process", "score", "sync"}

    if "collect" in request.etapas:
        if request.mode != "incremental":
            raise ValueError("  Erro: com --uf ALL + collect, o modo deve ser incremental.")

        if request.coletores is None:
            if request.etapas != permitido_com_collect_legado:
                raise ValueError(
                    "  Erro: com --uf ALL + collect sem --collectors, o fluxo permitido "
                    "permanece exatamente collect,dbt,process,score,sync."
                )
            return ValidateAllUfResult(ufs=list(ALL_UFS_NORDESTE), all_legado=True)

        return ValidateAllUfResult(ufs=list(ALL_UFS_NORDESTE), all_legado=False)

    if not request.etapas.issubset(permitido_sem_collect):
        raise ValueError(
            "  Erro: --uf ALL sem collect aceita apenas etapas entre process,score,sync."
        )

    discovered = discover_present_ufs_job(
        DiscoverPresentUfsInput(
            root=request.root,
            for_sync_only=(request.etapas == {"sync"}),
        )
    )
    ufs = sorted(set(discovered.ufs))
    if not ufs:
        raise ValueError(
            "  Erro: nenhuma UF elegivel foi encontrada no workspace para --uf ALL."
        )

    return ValidateAllUfResult(ufs=ufs, all_legado=False)


def execute_pipeline_run(
    request: PipelineRunInput,
    deps: PipelineExecutionDeps,
) -> PipelineRunResult:
    run_started_at = utc_now()
    run_id = request.run_id or build_run_id(uf=request.uf, mode=request.mode, now=run_started_at)
    resolved = resolve_collectors_job(
        ResolveCollectorsInput(
            uf=request.uf,
            etapas=request.etapas,
            coletores=request.coletores,
        )
    )

    if request.uf == ALL_UFS_TOKEN:
        validated = validate_all_uf_job(
            ValidateAllUfInput(
                mode=request.mode,
                etapas=request.etapas,
                coletores=request.coletores,
                root=request.root,
            )
        )
        target_ufs = list(validated.ufs)
        all_legado = validated.all_legado
    else:
        target_ufs = [request.uf]
        all_legado = False
        deps.prepare_paths(request.uf)

    steps_executed: list[ExecutedStepResult] = []

    print(
        f"  [RUN {run_id}] inicio execucao uf={request.uf} mode={request.mode} "
        f"steps={','.join(step for step in ETAPAS_ORDEM if step in request.etapas)} "
        f"targets={','.join(target_ufs)}"
    )

    def run_step(step: str, target: str, mode: str | None, runner: Callable[[], object]) -> None:
        result = _execute_tracked_step(
            run_id=run_id,
            step=step,
            target=target,
            mode=mode,
            runner=runner,
        )
        steps_executed.append(result)
        if result.status != "succeeded":
            raise PipelineExecutionError(
                _build_run_result(
                    run_id=run_id,
                    status="failed",
                    run_started_at=run_started_at,
                    request=request,
                    target_ufs=target_ufs,
                    resolved_collectors=resolved.coletores,
                    all_legado=all_legado,
                    steps_executed=steps_executed,
                ),
                RuntimeError(result.error_message or f"Falha na etapa {step}"),
            )

    if request.uf == ALL_UFS_TOKEN:
        if "collect" in request.etapas:
            if all_legado:
                run_step(
                    "collect",
                    ALL_UFS_TOKEN,
                    request.mode,
                    lambda: deps.run_collect_legacy_all(target_ufs),
                )
            else:
                assert resolved.coletores is not None
                run_step(
                    "collect",
                    ALL_UFS_TOKEN,
                    request.mode,
                    lambda: deps.run_collect_all(request.mode, target_ufs, resolved.coletores),
                )

        if "dbt" in request.etapas:
            run_step("dbt", ALL_UFS_TOKEN, None, lambda: deps.run_dbt(ALL_UFS_TOKEN))

        if "process" in request.etapas:
            for uf in target_ufs:
                run_step("process", uf, None, lambda uf_value=uf: deps.run_process(uf_value))

        if "score" in request.etapas:
            for uf in target_ufs:
                run_step(
                    "score",
                    uf,
                    request.mode,
                    lambda uf_value=uf: deps.run_score(uf_value, request.mode),
                )

        if "sync" in request.etapas:
            for uf in target_ufs:
                run_step("sync", uf, None, lambda uf_value=uf: deps.run_sync(uf_value))
    else:
        if "collect" in request.etapas:
            run_step(
                "collect",
                request.uf,
                request.mode,
                lambda: deps.run_collect(request.mode, request.uf, resolved.coletores),
            )

        if "dbt" in request.etapas:
            run_step("dbt", request.uf, None, lambda: deps.run_dbt(request.uf))

        if "process" in request.etapas:
            run_step("process", request.uf, None, lambda: deps.run_process(request.uf))

        if "score" in request.etapas:
            run_step(
                "score",
                request.uf,
                request.mode,
                lambda: deps.run_score(request.uf, request.mode),
            )

        if "sync" in request.etapas:
            run_step("sync", request.uf, None, lambda: deps.run_sync(request.uf))

    result = _build_run_result(
        run_id=run_id,
        status="succeeded",
        run_started_at=run_started_at,
        request=request,
        target_ufs=target_ufs,
        resolved_collectors=resolved.coletores,
        all_legado=all_legado,
        steps_executed=steps_executed,
    )
    print(
        f"  [RUN {run_id}] fim execucao status={result.status} "
        f"duracao={result.duration_seconds:.3f}s"
    )
    return result

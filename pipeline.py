"""
pipeline.py - Orquestrador central do SolveLicita v9.1

Caminho canonico:
BigQuery -> postprocessors -> solvency -> Supabase

Uso:
    python pipeline.py
    python pipeline.py --uf CE
    python pipeline.py --region NORDESTE --mode incremental --steps collect,dbt,process,score,sync
    python pipeline.py --uf ALL --steps process,score,sync
    python pipeline.py --uf ALL --mode incremental --steps collect,dbt,process,score,sync
    python pipeline.py --uf ALL --mode incremental --steps collect,dbt,process,score,sync --collectors cauc --yes

Regras para --uf ALL:
    - sem collect: aceita apenas process, score e sync, usando as UFs descobertas no workspace
    - com collect e sem --collectors: preserva o modo legado CAUC-only
    - com collect e com --collectors: ALL real para as UFs oficiais do Brasil
"""

import sys
import time
from pathlib import Path

from src.jobs import pipeline_jobs

ROOT = Path(__file__).resolve().parent

ETAPAS_VALIDAS = pipeline_jobs.ETAPAS_VALIDAS
ETAPAS_ORDEM = pipeline_jobs.ETAPAS_ORDEM
COLETORES_VALIDOS = pipeline_jobs.COLETORES_VALIDOS
COLETORES_ORDEM = pipeline_jobs.COLETORES_ORDEM
ALL_UFS_TOKEN = pipeline_jobs.ALL_UFS_TOKEN
ALL_UFS_BRASIL = pipeline_jobs.ALL_UFS_BRASIL
REGION_UF_PREFIX = pipeline_jobs.REGION_UF_PREFIX
PIPELINE_VERSION = "v9.1"


def selecionar_uf() -> str:
    print()
    print("  UF alvo (ex: PB, CE, RN, ALL). Enter = PB")
    uf = input("  UF: ").strip().upper()
    return uf if uf else "PB"


def selecionar_modo() -> str:
    print()
    print("  [1] Full")
    print("  [2] Incremental")
    print()
    while True:
        escolha = input("  Modo de coleta [1/2]: ").strip()
        if escolha == "1":
            return "full"
        if escolha == "2":
            return "incremental"
        print("  Opcao invalida. Digite 1 para Full ou 2 para Incremental.")


def selecionar_etapas() -> set[str]:
    print()
    print("  Etapas a executar:")
    print("  [1] Todas (collect -> dbt -> process -> score -> sync)")
    print("  [2] Todas sem sync (collect -> dbt -> process -> score)")
    print("  [3] process + score + sync (dados ja coletados e dbt rodado)")
    print("  [4] score + sync (postprocessors ja rodaram)")
    print("  [5] Apenas sync (score ja calculado)")
    print("  [6] Personalizado (digitar etapas)")
    print()
    while True:
        escolha = input("  Etapas [1/2/3/4/5/6]: ").strip()
        if escolha == "1":
            return {"collect", "dbt", "process", "score", "sync"}
        if escolha == "2":
            return {"collect", "dbt", "process", "score"}
        if escolha == "3":
            return {"process", "score", "sync"}
        if escolha == "4":
            return {"score", "sync"}
        if escolha == "5":
            return {"sync"}
        if escolha == "6":
            raw = input("  Digite etapas (collect,dbt,process,score,sync): ").strip()
            etapas = {e.strip() for e in raw.split(",") if e.strip()}
            invalidas = etapas - ETAPAS_VALIDAS
            if invalidas:
                print(f"  Etapas invalidas: {invalidas}. Use: collect, dbt, process, score, sync.")
                continue
            return etapas
        print("  Opcao invalida.")


def obter_argumento(args: list[str], flag: str) -> str | None:
    if flag in args:
        idx = args.index(flag)
        return args[idx + 1] if idx + 1 < len(args) else None

    prefix = f"{flag}="
    for arg in args:
        if arg.startswith(prefix):
            return arg.split("=", 1)[1]
    return None


def parse_etapas(raw: str | None) -> set[str] | None:
    if raw is None:
        return None
    etapas = {e.strip() for e in raw.split(",") if e.strip()}
    invalidas = etapas - ETAPAS_VALIDAS
    if invalidas:
        raise ValueError(
            f"  Erro: etapas invalidas: {invalidas}. Use: collect, dbt, process, score, sync."
        )
    return etapas


def _parse_csv_arg(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalizar_coletores(raw: str | None) -> list[str] | None:
    coletores = _parse_csv_arg(raw)
    if coletores is None:
        return None
    if not coletores:
        raise ValueError("  Erro: --collectors nao pode ser vazio.")

    invalidos = {c.lower() for c in coletores} - COLETORES_VALIDOS
    if invalidos:
        raise ValueError(
            f"  Erro: coletores invalidos: {invalidos}. "
            "Use: municipios, cauc, siconfi, siconfi_icf, dca, pncp."
        )

    selecionados = []
    coletores_set = {c.lower() for c in coletores}
    for coletor in COLETORES_ORDEM:
        if coletor in coletores_set:
            selecionados.append(coletor)
    return selecionados


def get_paths(uf: str):
    return pipeline_jobs.get_paths(uf)


def coletores_execucao(uf: str, etapas: set[str], coletores: list[str] | None) -> list[str] | None:
    result = pipeline_jobs.resolve_collectors_job(
        pipeline_jobs.ResolveCollectorsInput(uf=uf, etapas=etapas, coletores=coletores)
    )
    return result.coletores


def descobrir_ufs_presentes(*, for_sync_only: bool = False) -> list[str]:
    result = pipeline_jobs.discover_present_ufs_job(
        pipeline_jobs.DiscoverPresentUfsInput(root=ROOT, for_sync_only=for_sync_only)
    )
    return result.ufs


def filtrar_ufs_all(ufs: list[str]) -> list[str]:
    return pipeline_jobs.filter_ufs_all(ufs)


def normalizar_regiao(raw: str | None) -> str | None:
    if raw is None:
        return None
    return pipeline_jobs.normalize_region(raw)


def ufs_da_regiao(region: str) -> list[str]:
    return pipeline_jobs.get_ufs_for_region(region)


def validar_uf_all(
    mode: str,
    etapas: set[str],
    coletores: list[str] | None = None,
) -> tuple[list[str], bool]:
    try:
        result = pipeline_jobs.validate_all_uf_job(
            pipeline_jobs.ValidateAllUfInput(
                mode=mode,
                etapas=etapas,
                coletores=coletores,
                root=ROOT,
            )
        )
    except ValueError as exc:
        print(str(exc))
        sys.exit(1)
    return result.ufs, result.all_legado


def etapa_collect(mode: str, uf: str, *, coletores: list[str] | None = None):
    return pipeline_jobs.run_collect_job(
        pipeline_jobs.CollectJobInput(mode=mode, uf=uf, coletores=coletores)
    )


def etapa_collect_cauc_incremental_all(ufs: list[str]):
    return pipeline_jobs.run_collect_legacy_all_job(
        pipeline_jobs.CollectLegacyAllJobInput(ufs=list(ufs))
    )


def etapa_collect_all(mode: str, ufs: list[str], *, coletores: list[str]):
    return pipeline_jobs.run_collect_all_job(
        pipeline_jobs.CollectAllJobInput(mode=mode, ufs=list(ufs), coletores=list(coletores))
    )


def etapa_dbt(uf: str):
    try:
        return pipeline_jobs.run_dbt_job(
            pipeline_jobs.DbtJobInput(uf=uf, root=ROOT)
        )
    except FileNotFoundError as exc:
        print(f"  Aviso: {exc}")
        sys.exit(1)
    except RuntimeError:
        print("  Aviso: erro na execucao do dbt.")
        sys.exit(1)


def etapa_process(uf: str):
    return pipeline_jobs.run_process_job(pipeline_jobs.ProcessJobInput(uf=uf))


def etapa_score(uf: str, mode: str | None = None):
    return pipeline_jobs.run_score_job(
        pipeline_jobs.ScoreJobInput(
            uf=uf,
            pipeline_version=f"pipeline.py {PIPELINE_VERSION}",
            mode=mode,
        )
    )


def etapa_sync(uf: str):
    return pipeline_jobs.run_sync_job(pipeline_jobs.SyncJobInput(uf=uf))


def main() -> None:
    args = sys.argv[1:]
    non_interactive = "--yes" in args or "--non-interactive" in args

    uf_raw = obter_argumento(args, "--uf")
    region_raw = obter_argumento(args, "--region")
    uf = uf_raw.upper() if uf_raw else None
    region = None

    mode = obter_argumento(args, "--mode")
    if mode is not None and mode not in ("full", "incremental"):
        print(f"  Erro: --mode deve ser 'full' ou 'incremental'. Recebido: '{mode}'")
        sys.exit(1)

    try:
        etapas = parse_etapas(obter_argumento(args, "--steps"))
        coletores = normalizar_coletores(obter_argumento(args, "--collectors"))
        region = normalizar_regiao(region_raw)
    except ValueError as exc:
        print(str(exc))
        sys.exit(1)

    if uf is not None and region is not None:
        print("  Erro: use --uf ou --region, nao ambos.")
        sys.exit(1)

    if region is not None:
        uf = f"{REGION_UF_PREFIX}{region}"

    if uf is None:
        uf = "PB" if non_interactive else selecionar_uf()

    if mode is None:
        if non_interactive:
            mode = "incremental"
        elif etapas is None or "collect" in etapas:
            mode = selecionar_modo()
        else:
            mode = "incremental"

    if etapas is None:
        etapas = set(ETAPAS_ORDEM) if non_interactive else selecionar_etapas()

    ufs_all = None
    all_legado = False
    if region is not None:
        ufs_all = ufs_da_regiao(region)
    elif uf == ALL_UFS_TOKEN:
        ufs_all, all_legado = validar_uf_all(mode, etapas, coletores)

    etapas_str = " -> ".join(e for e in ETAPAS_ORDEM if e in etapas)
    alvo_str = ", ".join(ufs_all) if ufs_all else uf
    coletores_resolvidos = coletores_execucao(uf, etapas, coletores)
    coletores_str = ", ".join(c.upper() for c in coletores_resolvidos) if coletores_resolvidos else "-"

    print()
    print("  ---------------------------------------------")
    print(f"  UF    : {alvo_str}")
    print(f"  Modo  : {mode}")
    print(f"  Etapas: {etapas_str}")
    if "collect" in etapas:
        print(f"  Coleta: {coletores_str}")
    print("  ---------------------------------------------")
    print()
    if uf == ALL_UFS_TOKEN and "collect" in etapas and all_legado:
        print("  Aviso: --uf ALL + collect sem --collectors esta em modo legado CAUC-only nacional.")
        print()
    if not non_interactive:
        input("  Pressione Enter para iniciar ou Ctrl+C para cancelar...")

    t0 = time.time()
    request = pipeline_jobs.PipelineRunInput(
        uf=uf,
        mode=mode,
        etapas=set(etapas),
        coletores=coletores,
        root=ROOT,
        region=region,
    )
    deps = pipeline_jobs.PipelineExecutionDeps(
        prepare_paths=get_paths,
        run_collect=lambda mode_value, uf_value, coletores_value=None: etapa_collect(
            mode_value,
            uf_value,
            coletores=coletores_value,
        ),
        run_collect_legacy_all=etapa_collect_cauc_incremental_all,
        run_collect_all=lambda mode_value, ufs_value, coletores_value: etapa_collect_all(
            mode_value,
            ufs_value,
            coletores=coletores_value,
        ),
        run_dbt=etapa_dbt,
        run_process=etapa_process,
        run_score=etapa_score,
        run_sync=etapa_sync,
    )

    try:
        result = pipeline_jobs.execute_pipeline_run(request, deps)
    except KeyboardInterrupt:
        print("\n\n  Pipeline interrompido pelo usuario.")
        sys.exit(0)
    except pipeline_jobs.PipelineExecutionError as exc:
        result = exc.result
        print()
        print(f"  Run ID   : {result.run_id}")
        print(f"  Status   : {result.status}")
        print(f"  Inicio   : {result.started_at}")
        print(f"  Fim      : {result.finished_at}")
        print(f"  Duracao  : {result.duration_seconds:.1f}s")
        if result.steps_executed:
            last_step = result.steps_executed[-1]
            print(f"  Falha em : {last_step.step} ({last_step.target})")
            if last_step.error_message:
                print(f"  Erro     : {last_step.error_message}")
        sys.exit(1)
    except ValueError as exc:
        print(str(exc))
        sys.exit(1)

    elapsed = time.time() - t0
    print()
    print(f"  Run ID   : {result.run_id}")
    print(f"  Status   : {result.status}")
    print(f"  Pipeline concluido em {elapsed/60:.1f} min")
    print("  Dashboard: https://solvelicita.tech")
    print()


if __name__ == "__main__":
    main()

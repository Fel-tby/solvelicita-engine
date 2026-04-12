"""
pipeline.py - Orquestrador central do SolveLicita v9.1

Caminho canonico:
BigQuery -> postprocessors -> solvency -> Supabase

Uso:
    python pipeline.py
    python pipeline.py --uf CE
    python pipeline.py --uf ALL --steps process,score,sync
    python pipeline.py --uf ALL --mode incremental --steps collect,dbt,process,score,sync
    python pipeline.py --uf ALL --mode incremental --steps collect,dbt,process,score,sync --collectors cauc --yes

Regras para --uf ALL:
    - sem collect: aceita apenas process, score e sync
    - com collect e sem --collectors: preserva o modo legado CAUC-only
    - com collect e com --collectors: ALL real para as UFs oficiais do Nordeste
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.collectors import cauc, dca, municipios, pncp, siconfi
from src.engine import solvency
from src.processors import dca_postprocessor, siconfi_postprocessor
from src.utils.paths import get_paths
from src.utils.supabase_sync import run as supabase_sync


ETAPAS_VALIDAS = {"collect", "dbt", "process", "score", "sync"}
ETAPAS_ORDEM = ["collect", "dbt", "process", "score", "sync"]
COLETORES_VALIDOS = {"municipios", "cauc", "siconfi", "dca", "pncp"}
COLETORES_ORDEM = ["municipios", "cauc", "siconfi", "dca", "pncp"]
ALL_UFS_TOKEN = "ALL"
ALL_UFS_NORDESTE = ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]
PIPELINE_VERSION = "v9.1"


def selecionar_uf() -> str:
    print()
    print("  UF alvo (ex: PB, CE, RN, ALL=Nordeste). Enter = PB")
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
            "Use: municipios, cauc, siconfi, dca, pncp."
        )

    selecionados = []
    coletores_set = {c.lower() for c in coletores}
    for coletor in COLETORES_ORDEM:
        if coletor in coletores_set:
            selecionados.append(coletor)
    return selecionados


def coletores_execucao(uf: str, etapas: set[str], coletores: list[str] | None) -> list[str] | None:
    if "collect" not in etapas:
        return None
    if uf == ALL_UFS_TOKEN and coletores is None:
        return ["cauc"]
    if coletores is None:
        return list(COLETORES_ORDEM)
    return list(coletores)


def etapa_collect(mode: str, uf: str, *, coletores: list[str] | None = None) -> None:
    print("\n" + "=" * 55)
    print(f"  ETAPA: COLETA [{mode.upper()}] - {uf}")
    print("=" * 55)

    coletores_ativos = coletores or list(COLETORES_ORDEM)
    etapas_coleta = []

    if "municipios" in coletores_ativos:
        etapas_coleta.append(("Municipios", lambda: municipios.run(uf=uf)))
    if "cauc" in coletores_ativos:
        etapas_coleta.append(("CAUC", lambda: cauc.run(uf=uf)))
    if "siconfi" in coletores_ativos:
        etapas_coleta.append((f"SICONFI [{mode}]", lambda: siconfi.run(mode=mode, uf=uf)))
    if "dca" in coletores_ativos:
        etapas_coleta.append((f"DCA [{mode}]", lambda: dca.run(mode=mode, uf=uf)))
    if "pncp" in coletores_ativos:
        etapas_coleta.append((f"PNCP [{mode}]", lambda: pncp.run(mode=mode, uf=uf)))

    total = len(etapas_coleta)
    for idx, (label, runner) in enumerate(etapas_coleta, start=1):
        print(f"\n[{idx}/{total}] {label}...")
        runner()


def etapa_collect_cauc_incremental_all(ufs: list[str]) -> None:
    print("\n" + "=" * 55)
    print("  ETAPA: COLETA INCREMENTAL CAUC - ALL (LEGADO)")
    print("=" * 55)

    total = len(ufs)
    for idx, uf in enumerate(ufs, start=1):
        print(f"\n[{idx}/{total}] CAUC incremental - {uf}...")
        get_paths(uf)
        cauc.run(uf=uf)


def etapa_collect_all(mode: str, ufs: list[str], *, coletores: list[str]) -> None:
    total = len(ufs)
    for idx, uf in enumerate(ufs, start=1):
        print("\n" + "-" * 55)
        print(f"  COLETA ALL [{idx}/{total}] - {uf}")
        print("-" * 55)
        get_paths(uf)
        etapa_collect(mode, uf, coletores=coletores)


def etapa_dbt(uf: str) -> None:
    print("\n" + "=" * 55)
    print(f"  ETAPA: DBT TRANSFORM - {uf}")
    print("=" * 55)

    print("\n[1/1] Rodando modelos do dbt no BigQuery (via venv_dbt)...")

    import os
    import platform

    if platform.system() == "Windows":
        dbt_exe = ROOT / "venv_dbt" / "Scripts" / "dbt.exe"
    else:
        dbt_exe = ROOT / "venv_dbt" / "bin" / "dbt"

    if not dbt_exe.exists():
        print(f"  Aviso: executavel dbt nao encontrado em: {dbt_exe}")
        sys.exit(1)

    env = os.environ.copy()
    sa_path = env.get("GCP_SA_KEY_PATH")
    if sa_path and not Path(sa_path).is_absolute():
        env["GCP_SA_KEY_PATH"] = str((ROOT / sa_path).resolve())

    res = subprocess.run([str(dbt_exe), "run"], cwd=str(ROOT / "dbt"), env=env)
    if res.returncode != 0:
        print("  Aviso: erro na execucao do dbt.")
        sys.exit(res.returncode)


def etapa_process(uf: str) -> None:
    print("\n" + "=" * 55)
    print(f"  ETAPA: POSTPROCESSORS BigQuery - {uf}")
    print("=" * 55)

    print("\n[1/2] SICONFI postprocessor...")
    siconfi_postprocessor.run(uf=uf)

    print("\n[2/2] DCA postprocessor...")
    dca_postprocessor.run(uf=uf)


def etapa_score(uf: str, mode: str | None = None) -> None:
    print("\n" + "=" * 55)
    print(f"  ETAPA: SCORE - {uf}")
    print("=" * 55)

    print("\n[1/1] Solvency engine (source=bigquery)...")
    solvency.run(
        uf=uf,
        source="bigquery",
        strict_bigquery=True,
        publish_snapshot=True,
        run_type="pipeline",
        pipeline_mode=mode,
        pipeline_version=f"pipeline.py {PIPELINE_VERSION}",
    )


def etapa_sync(uf: str) -> None:
    print("\n" + "=" * 55)
    print(f"  ETAPA: SYNC - Supabase - {uf}")
    print("=" * 55)

    print("\n[1/1] Sincronizando com Supabase...")
    supabase_sync(uf=uf)


def descobrir_ufs_presentes(*, for_sync_only: bool = False) -> list[str]:
    if for_sync_only:
        base = ROOT / "data" / "outputs"
        ufs = []
        if base.exists():
            for item in sorted(base.iterdir()):
                if not item.is_dir():
                    continue
                uf = item.name.upper()
                score_csv = item / f"score_municipios_{uf.lower()}_pncp.csv"
                if score_csv.exists():
                    ufs.append(uf)
        return ufs

    base = ROOT / "data" / "processed"
    ufs = []
    if base.exists():
        for item in sorted(base.iterdir()):
            if not item.is_dir():
                continue
            uf = item.name.upper()
            tabela_mun = item / f"municipios_{uf.lower()}_tabela.csv"
            if tabela_mun.exists():
                ufs.append(uf)
    return ufs


def filtrar_ufs_all(ufs: list[str]) -> list[str]:
    """ALL executa apenas as UFs oficiais do Nordeste."""
    return [uf for uf in ALL_UFS_NORDESTE if uf in set(ufs)]


def validar_uf_all(mode: str, etapas: set[str], coletores: list[str] | None = None) -> tuple[list[str], bool]:
    permitido_sem_collect = {"process", "score", "sync"}
    permitido_com_collect_legado = {"collect", "dbt", "process", "score", "sync"}

    if "collect" in etapas:
        if mode != "incremental":
            print("  Erro: com --uf ALL + collect, o modo deve ser incremental.")
            sys.exit(1)

        if coletores is None:
            if etapas != permitido_com_collect_legado:
                print(
                    "  Erro: com --uf ALL + collect sem --collectors, o fluxo permitido "
                    "permanece exatamente collect,dbt,process,score,sync."
                )
                sys.exit(1)
            return list(ALL_UFS_NORDESTE), True

        return list(ALL_UFS_NORDESTE), False

    if not etapas.issubset(permitido_sem_collect):
        print(
            "  Erro: --uf ALL sem collect aceita apenas etapas entre "
            "process,score,sync."
        )
        sys.exit(1)

    ufs = descobrir_ufs_presentes(for_sync_only=(etapas == {"sync"}))
    ufs = filtrar_ufs_all(ufs)

    if not ufs:
        print(
            "  Erro: nenhuma UF do Nordeste foi encontrada no workspace para --uf ALL."
        )
        sys.exit(1)

    return ufs, False


def main() -> None:
    args = sys.argv[1:]
    non_interactive = "--yes" in args or "--non-interactive" in args

    uf_raw = obter_argumento(args, "--uf")
    uf = uf_raw.upper() if uf_raw else None

    mode = obter_argumento(args, "--mode")
    if mode is not None and mode not in ("full", "incremental"):
        print(f"  Erro: --mode deve ser 'full' ou 'incremental'. Recebido: '{mode}'")
        sys.exit(1)

    try:
        etapas = parse_etapas(obter_argumento(args, "--steps"))
        coletores = normalizar_coletores(obter_argumento(args, "--collectors"))
    except ValueError as exc:
        print(str(exc))
        sys.exit(1)

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
    if uf == ALL_UFS_TOKEN:
        ufs_all, all_legado = validar_uf_all(mode, etapas, coletores)

    if uf != ALL_UFS_TOKEN:
        get_paths(uf)

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
        print("  Aviso: --uf ALL + collect sem --collectors esta em modo legado CAUC-only.")
        print()
    if not non_interactive:
        input("  Pressione Enter para iniciar ou Ctrl+C para cancelar...")

    t0 = time.time()

    try:
        if uf == ALL_UFS_TOKEN:
            assert ufs_all is not None

            if "collect" in etapas:
                if all_legado:
                    etapa_collect_cauc_incremental_all(ufs_all)
                else:
                    assert coletores_resolvidos is not None
                    etapa_collect_all(mode, ufs_all, coletores=coletores_resolvidos)

            if "dbt" in etapas:
                etapa_dbt("ALL")

            if "process" in etapas:
                for uf_item in ufs_all:
                    etapa_process(uf_item)

            if "score" in etapas:
                for uf_item in ufs_all:
                    etapa_score(uf_item, mode=mode)

            if "sync" in etapas:
                for uf_item in ufs_all:
                    etapa_sync(uf_item)
        else:
            if "collect" in etapas:
                etapa_collect(mode, uf, coletores=coletores_resolvidos)

            if "dbt" in etapas:
                etapa_dbt(uf)

            if "process" in etapas:
                etapa_process(uf)

            if "score" in etapas:
                etapa_score(uf, mode=mode)

            if "sync" in etapas:
                etapa_sync(uf)

    except KeyboardInterrupt:
        print("\n\n  Pipeline interrompido pelo usuario.")
        sys.exit(0)

    elapsed = time.time() - t0
    print()
    print(f"  Pipeline concluido em {elapsed/60:.1f} min")
    print("  Dashboard: https://solvelicita.tech")
    print()


if __name__ == "__main__":
    main()

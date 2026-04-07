"""
pipeline.py - Orquestrador central do SolveLicita v9.1

Caminho canonico:
BigQuery -> postprocessors -> solvency -> Supabase

Uso:
    python pipeline.py
    python pipeline.py --uf CE
    python pipeline.py --uf ALL --steps process,score,sync
    python pipeline.py --uf ALL --mode incremental --steps collect,dbt,process,score,sync

Regras para --uf ALL:
    - sem collect: aceita apenas process, score e sync
    - com collect: faz somente coleta incremental de CAUC para cada UF presente,
      depois roda dbt uma vez e process -> score -> sync para todas as UFs
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
ALL_UFS_TOKEN = "ALL"


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


def etapa_collect(mode: str, uf: str) -> None:
    print("\n" + "=" * 55)
    print(f"  ETAPA: COLETA [{mode.upper()}] - {uf}")
    print("=" * 55)

    print("\n[1/5] Municipios...")
    municipios.run(uf=uf)

    print("\n[2/5] CAUC...")
    cauc.run(uf=uf)

    print(f"\n[3/5] SICONFI [{mode}]...")
    siconfi.run(mode=mode, uf=uf)

    print(f"\n[4/5] DCA [{mode}]...")
    dca.run(mode=mode, uf=uf)

    print(f"\n[5/5] PNCP [{mode}]...")
    pncp.run(mode=mode, uf=uf)


def etapa_collect_cauc_incremental_all(ufs: list[str]) -> None:
    print("\n" + "=" * 55)
    print("  ETAPA: COLETA INCREMENTAL CAUC - ALL")
    print("=" * 55)

    total = len(ufs)
    for idx, uf in enumerate(ufs, start=1):
        print(f"\n[{idx}/{total}] CAUC incremental - {uf}...")
        cauc.run(uf=uf)


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


def etapa_score(uf: str) -> None:
    print("\n" + "=" * 55)
    print(f"  ETAPA: SCORE - {uf}")
    print("=" * 55)

    print("\n[1/1] Solvency engine (source=bigquery)...")
    solvency.run(uf=uf, source="bigquery")


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


def validar_uf_all(mode: str, etapas: set[str]) -> list[str]:
    permitido_sem_collect = {"process", "score", "sync"}
    permitido_com_collect = {"collect", "dbt", "process", "score", "sync"}

    if "collect" in etapas:
        if etapas != permitido_com_collect:
            print(
                "  Erro: com --uf ALL + collect, o fluxo permitido e exatamente "
                "collect,dbt,process,score,sync."
            )
            sys.exit(1)
        if mode != "incremental":
            print("  Erro: com --uf ALL + collect, o modo deve ser incremental.")
            sys.exit(1)
        ufs = descobrir_ufs_presentes()
    else:
        if not etapas.issubset(permitido_sem_collect):
            print(
                "  Erro: --uf ALL sem collect aceita apenas etapas entre "
                "process,score,sync."
            )
            sys.exit(1)
        ufs = descobrir_ufs_presentes(for_sync_only=(etapas == {"sync"}))

    if not ufs:
        print("  Erro: nenhuma UF coletada foi encontrada no workspace para --uf ALL.")
        sys.exit(1)

    return ufs


def main() -> None:
    args = sys.argv[1:]

    if "--uf" in args:
        idx = args.index("--uf")
        uf = args[idx + 1].upper() if idx + 1 < len(args) else "PB"
    else:
        uf_inline = next((a.split("=", 1)[1] for a in args if a.startswith("--uf=")), None)
        uf = uf_inline.upper() if uf_inline else None

    if "--mode" in args:
        idx = args.index("--mode")
        mode = args[idx + 1] if idx + 1 < len(args) else None
        if mode not in ("full", "incremental"):
            print(f"  Erro: --mode deve ser 'full' ou 'incremental'. Recebido: '{mode}'")
            sys.exit(1)
    else:
        mode_inline = next((a.split("=", 1)[1] for a in args if a.startswith("--mode=")), None)
        mode = mode_inline if mode_inline in ("full", "incremental") else None

    if "--steps" in args:
        idx = args.index("--steps")
        raw = args[idx + 1] if idx + 1 < len(args) else ""
        etapas = {e.strip() for e in raw.split(",") if e.strip()}
        invalidas = etapas - ETAPAS_VALIDAS
        if invalidas:
            print(f"  Erro: etapas invalidas: {invalidas}. Use: collect, dbt, process, score, sync.")
            sys.exit(1)
    else:
        steps_inline = next((a.split("=", 1)[1] for a in args if a.startswith("--steps=")), None)
        if steps_inline:
            etapas = {e.strip() for e in steps_inline.split(",") if e.strip()}
            invalidas = etapas - ETAPAS_VALIDAS
            if invalidas:
                print(f"  Erro: etapas invalidas: {invalidas}.")
                sys.exit(1)
        else:
            etapas = None

    if uf is None:
        uf = selecionar_uf()

    if mode is None:
        if etapas is None or "collect" in etapas:
            mode = selecionar_modo()
        else:
            mode = "incremental"

    if etapas is None:
        etapas = selecionar_etapas()

    ufs_all = None
    if uf == ALL_UFS_TOKEN:
        ufs_all = validar_uf_all(mode, etapas)

    if uf != ALL_UFS_TOKEN:
        get_paths(uf)

    etapas_str = " -> ".join(e for e in ETAPAS_ORDEM if e in etapas)
    alvo_str = ", ".join(ufs_all) if ufs_all else uf

    print()
    print("  ---------------------------------------------")
    print(f"  UF    : {alvo_str}")
    print(f"  Modo  : {mode}")
    print(f"  Etapas: {etapas_str}")
    print("  ---------------------------------------------")
    print()
    input("  Pressione Enter para iniciar ou Ctrl+C para cancelar...")

    t0 = time.time()

    try:
        if uf == ALL_UFS_TOKEN:
            assert ufs_all is not None

            if "collect" in etapas:
                etapa_collect_cauc_incremental_all(ufs_all)

            if "dbt" in etapas:
                etapa_dbt("ALL")

            if "process" in etapas:
                for uf_item in ufs_all:
                    etapa_process(uf_item)

            if "score" in etapas:
                for uf_item in ufs_all:
                    etapa_score(uf_item)

            if "sync" in etapas:
                for uf_item in ufs_all:
                    etapa_sync(uf_item)
        else:
            if "collect" in etapas:
                etapa_collect(mode, uf)

            if "dbt" in etapas:
                etapa_dbt(uf)

            if "process" in etapas:
                etapa_process(uf)

            if "score" in etapas:
                etapa_score(uf)

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

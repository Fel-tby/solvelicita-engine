"""
pipeline.py — Orquestrador central do SolveLicita v9.0
Localização: raiz do projeto (ao lado de README.md).

Bloco 9: processors legados aposentados, etapa app removida.
Caminho canônico: BigQuery → postprocessors → solvency → pncp_agregador → Supabase.

Uso:
    python pipeline.py                                            # interativo
    python pipeline.py --uf CE                                   # outro estado
    python pipeline.py --mode full                               # força full
    python pipeline.py --mode incremental                        # força incremental
    python pipeline.py --steps process,score                     # pula coleta
    python pipeline.py --steps score,sync                        # score + Supabase
    python pipeline.py --uf CE --mode incremental --steps collect,score,sync

Etapas disponíveis:
    collect — coleta bruta (municipios, cauc, siconfi, dca, pncp)
    process — postprocessors BigQuery (siconfi_postprocessor, dca_postprocessor)
    score   — cálculo do score (solvency.py --source bigquery + pncp_agregador.py)
    sync    — sincroniza com o Supabase
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.collectors import municipios, cauc, siconfi, dca, pncp
from src.processors import siconfi_postprocessor, dca_postprocessor, pncp_agregador
from src.engine import solvency
from src.utils.paths import get_paths
from src.utils.supabase_sync import run as supabase_sync


ETAPAS_VALIDAS = {"collect", "process", "score", "sync"}
ETAPAS_ORDEM   = ["collect", "process", "score", "sync"]


# ── UI de seleção ──────────────────────────────────────────────────────────────

def selecionar_uf() -> str:
    print()
    print("  UF alvo (ex: PB, CE, RN). Enter = PB")
    uf = input("  UF: ").strip().upper()
    return uf if uf else "PB"


def selecionar_modo() -> str:
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║         SolveLicita — Pipeline de Dados  v9.0      ║")
    print("╠══════════════════════════════════════════════════════╣")
    print("║                                                      ║")
    print("║  [1] Full — histórico completo                      ║")
    print("║      (use na primeira execução)                      ║")
    print("║                                                      ║")
    print("║  [2] Incremental — apenas período recente           ║")
    print("║      (CAUC: snapshot atual                          ║")
    print("║       SICONFI: ano anterior + corrente              ║")
    print("║       DCA: último exercício                         ║")
    print("║       PNCP: últimos 60 dias)                        ║")
    print("║                                                      ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    while True:
        escolha = input("  Modo de coleta [1/2]: ").strip()
        if escolha == "1":
            return "full"
        if escolha == "2":
            return "incremental"
        print("  Opção inválida. Digite 1 para Full ou 2 para Incremental.")


def selecionar_etapas() -> set[str]:
    print()
    print("  Etapas a executar:")
    print("  [1] Todas (collect → process → score → sync)")
    print("  [2] Todas sem sync (collect → process → score)")
    print("  [3] process + score + sync (dados já coletados)")
    print("  [4] score + sync (postprocessors já rodaram)")
    print("  [5] Apenas sync (score já calculado)")
    print("  [6] Personalizado (digitar etapas)")
    print()
    while True:
        escolha = input("  Etapas [1/2/3/4/5/6]: ").strip()
        if escolha == "1": return {"collect", "process", "score", "sync"}
        if escolha == "2": return {"collect", "process", "score"}
        if escolha == "3": return {"process", "score", "sync"}
        if escolha == "4": return {"score", "sync"}
        if escolha == "5": return {"sync"}
        if escolha == "6":
            raw       = input("  Digite etapas (collect,process,score,sync): ").strip()
            etapas    = {e.strip() for e in raw.split(",")}
            invalidas = etapas - ETAPAS_VALIDAS
            if invalidas:
                print(f"  Etapas inválidas: {invalidas}. Use: collect, process, score, sync.")
                continue
            return etapas
        print("  Opção inválida.")


# ── Etapas do pipeline ─────────────────────────────────────────────────────────

def etapa_collect(mode: str, uf: str) -> None:
    print("\n" + "═" * 55)
    print(f"  ETAPA: COLETA [{mode.upper()}] — {uf}")
    print("═" * 55)

    print("\n[1/5] Municípios...")
    municipios.run(uf=uf)

    print("\n[2/5] CAUC...")
    cauc.run(uf=uf)

    print(f"\n[3/5] SICONFI [{mode}]...")
    siconfi.run(mode=mode, uf=uf)

    print(f"\n[4/5] DCA [{mode}]...")
    dca.run(mode=mode, uf=uf)

    print(f"\n[5/5] PNCP [{mode}]...")
    pncp.run(mode=mode, uf=uf)


def etapa_process(uf: str) -> None:
    """
    Postprocessors BigQuery — preenchem as colunas NULL deixadas pelo dbt.
    siconfi_postprocessor: eorcam_raw, lliq_raw, lliq_parcial, dias_atraso,
                           decay_fator, dado_suspeito_lliq, dado_defasado.
    dca_postprocessor:     autonomia_media, autonomia_critica.
    """
    print("\n" + "═" * 55)
    print(f"  ETAPA: POSTPROCESSORS BigQuery — {uf}")
    print("═" * 55)

    print("\n[1/2] SICONFI postprocessor...")
    siconfi_postprocessor.run(uf=uf)

    print("\n[2/2] DCA postprocessor...")
    dca_postprocessor.run(uf=uf)


def etapa_score(uf: str) -> None:
    """
    Lê mart_indicadores_municipios (BigQuery), calcula o score completo
    e enriquece com dados PNCP dos últimos 12 meses.
    """
    print("\n" + "═" * 55)
    print(f"  ETAPA: SCORE — {uf}")
    print("═" * 55)

    print("\n[1/2] Solvency engine (source=bigquery)...")
    solvency.run(uf=uf, source="bigquery")

    print("\n[2/2] PNCP agregador (últimos 12 meses)...")
    pncp_agregador.run(uf=uf)


def etapa_sync(uf: str) -> None:
    """
    Lê outputs/{UF}/score_municipios_{u}_pncp.csv e faz upsert no Supabase.
    """
    print("\n" + "═" * 55)
    print(f"  ETAPA: SYNC — Supabase — {uf}")
    print("═" * 55)

    print("\n[1/1] Sincronizando com Supabase...")
    supabase_sync(uf=uf)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    # Resolve uf
    if "--uf" in args:
        idx = args.index("--uf")
        uf  = args[idx + 1].upper() if idx + 1 < len(args) else "PB"
    else:
        uf_inline = next((a.split("=", 1)[1] for a in args if a.startswith("--uf=")), None)
        uf        = uf_inline.upper() if uf_inline else None

    # Resolve mode
    if "--mode" in args:
        idx  = args.index("--mode")
        mode = args[idx + 1] if idx + 1 < len(args) else None
        if mode not in ("full", "incremental"):
            print(f"  Erro: --mode deve ser 'full' ou 'incremental'. Recebido: '{mode}'")
            sys.exit(1)
    else:
        mode_inline = next((a.split("=", 1)[1] for a in args if a.startswith("--mode=")), None)
        mode        = mode_inline if mode_inline in ("full", "incremental") else None

    # Resolve etapas
    if "--steps" in args:
        idx    = args.index("--steps")
        raw    = args[idx + 1] if idx + 1 < len(args) else ""
        etapas = {e.strip() for e in raw.split(",")}
        invalidas = etapas - ETAPAS_VALIDAS
        if invalidas:
            print(f"  Erro: etapas inválidas: {invalidas}. Use: collect, process, score, sync.")
            sys.exit(1)
    else:
        steps_inline = next((a.split("=", 1)[1] for a in args if a.startswith("--steps=")), None)
        if steps_inline:
            etapas    = {e.strip() for e in steps_inline.split(",")}
            invalidas = etapas - ETAPAS_VALIDAS
            if invalidas:
                print(f"  Erro: etapas inválidas: {invalidas}.")
                sys.exit(1)
        else:
            etapas = None

    # Interatividade — só pergunta o que não veio via CLI
    if uf is None:
        uf = selecionar_uf()

    if mode is None:
        if etapas is None or "collect" in etapas:
            mode = selecionar_modo()
        else:
            mode = "incremental"

    if etapas is None:
        etapas = selecionar_etapas()

    # Garante diretórios da UF antes de qualquer etapa
    get_paths(uf)

    # Sumário
    etapas_str = " → ".join(e for e in ETAPAS_ORDEM if e in etapas)

    print()
    print("  ┌─────────────────────────────────────────────┐")
    print(f"  │  UF    : {uf:<33}│")
    print(f"  │  Modo  : {mode:<33}│")
    print(f"  │  Etapas: {etapas_str:<33}│")
    print("  └─────────────────────────────────────────────┘")
    print()
    input("  Pressione Enter para iniciar ou Ctrl+C para cancelar...")

    t0 = time.time()

    try:
        if "collect" in etapas:
            etapa_collect(mode, uf)

        if "process" in etapas:
            etapa_process(uf)

        if "score" in etapas:
            etapa_score(uf)

        if "sync" in etapas:
            etapa_sync(uf)

    except KeyboardInterrupt:
        print("\n\n  Pipeline interrompido pelo usuário.")
        sys.exit(0)

    elapsed = time.time() - t0
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print(f"║  ✅ Pipeline concluído em {elapsed/60:.1f} min"
          + " " * (27 - len(f"{elapsed/60:.1f}")) + "║")
    print("║  Dashboard: https://solvelicita.tech                ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()


if __name__ == "__main__":
    main()
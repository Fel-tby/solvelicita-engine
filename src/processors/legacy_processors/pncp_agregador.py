"""
pncp_agregador.py — Enriquece o score de solvência com dados de mercado do PNCP.
SolveLicita

Responsabilidades:
1. Ler processed/{UF}/pncp_licitacoes_{u}.csv (produzido por pncp_processor.py)
2. Filtrar para os últimos 12 meses (dataPublicacaoPncp)
3. Agregar por município: volume, valor homologado, padrão de compra, temporalidade
4. Fazer merge com outputs/{UF}/score_municipios_{u}.csv (output do solvency.py)
5. Exportar outputs/{UF}/score_municipios_{u}_pncp.csv para uso no app e no relatório

Não recalcula scores — apenas enriquece o output do solvency.py com
a dimensão de "exposição de mercado" (quanto o município compra e como).

Janela temporal: últimos 12 meses a partir da data de execução.
Todos os indicadores PNCP (n_licitacoes, valor_homologado_total, dispensa)
refletem apenas esse período.

Rodar individualmente:
    python src/processors/pncp_agregador.py --uf PB
"""

import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from utils.paths import get_paths

# Modalidades que dispensam competição (IDs fixos da Lei 14.133/2021)
MODALIDADES_SEM_LICITACAO = {8, 9}  # 8 = Dispensa, 9 = Inexigibilidade

# Janela temporal para agregação PNCP
JANELA_MESES = 12


def run(uf: str = "PB") -> pd.DataFrame:
    """
    Agrega dados PNCP dos últimos 12 meses por município e faz merge
    com score de solvência. Retorna o DataFrame enriquecido.
    """
    paths = get_paths(uf)
    u = uf.lower()

    print("=" * 65)
    print(" PNCP Aggregator — SolveLicita")
    print(" Enriquecimento do score com dados de mercado")
    print(f" UF: {uf} | Janela temporal: últimos {JANELA_MESES} meses")
    print("=" * 65)

    # ── 1. Carga ──────────────────────────────────────────────────────────────
    print("\n📂 Carregando dados...")

    pncp_path  = paths["processed"] / f"pncp_licitacoes_{u}.csv"
    score_path = paths["outputs"]   / f"score_municipios_{u}.csv"

    for path, label in [(pncp_path, "PNCP"), (score_path, "Score")]:
        if not path.exists():
            raise FileNotFoundError(f"{label} não encontrado: {path}")

    pncp  = pd.read_csv(pncp_path,  dtype={"municipio_ibge": str})
    score = pd.read_csv(score_path, dtype={"cod_ibge": str})

    pncp["municipio_ibge"] = pncp["municipio_ibge"].str.zfill(7)
    score["cod_ibge"]      = score["cod_ibge"].str.zfill(7)

    print(f"  PNCP  : {len(pncp):,} licitações | "
          f"{pncp['municipio_ibge'].nunique()} municípios (histórico completo)")
    print(f"  Score : {len(score)} municípios")

    # ── 2. Filtro temporal — últimos 12 meses ─────────────────────────────────
    corte = pd.Timestamp.today().normalize() - pd.DateOffset(months=JANELA_MESES)
    pncp["dataPublicacaoPncp"] = pd.to_datetime(
        pncp["dataPublicacaoPncp"], errors="coerce"
    )

    antes  = len(pncp)
    pncp   = pncp[pncp["dataPublicacaoPncp"] >= corte].copy()
    depois = len(pncp)

    print(f"\n⏱ Filtro {JANELA_MESES} meses (>= {corte.date()}):")
    print(f"  Antes : {antes:,} licitações")
    print(f"  Depois: {depois:,} licitações ({antes - depois:,} removidas)")
    print(f"  Municípios restantes: {pncp['municipio_ibge'].nunique()}")

    # ── 3. Flags auxiliares ───────────────────────────────────────────────────
    pncp["eh_dispensa"] = pncp["modalidadeId"].isin(MODALIDADES_SEM_LICITACAO)

    pncp["valor_hom_dispensa"] = pncp["valorTotalHomologado"].where(
        pncp["eh_dispensa"], 0
    ).fillna(0)

    pncp["valorTotalHomologado"] = pncp["valorTotalHomologado"].fillna(0)

    # ── 4. Agregação por município ────────────────────────────────────────────
    print("\n🔄 Agregando por município...")

    agg = pncp.groupby("municipio_ibge").agg(
        n_licitacoes          = ("numeroControlePNCP",  "count"),
        valor_homologado_total = ("valorTotalHomologado", "sum"),
        n_dispensa            = ("eh_dispensa",          "sum"),
        valor_hom_dispensa    = ("valor_hom_dispensa",   "sum"),
        ano_ultima_licitacao  = ("anoCompra",            "max"),
    ).reset_index().rename(columns={"municipio_ibge": "cod_ibge"})

    agg["pct_dispensa"] = (
        agg["valor_hom_dispensa"] /
        agg["valor_homologado_total"].replace(0, np.nan)
    ).round(4)

    agg["alerta_dispensa"] = (agg["pct_dispensa"] > 0.30)

    print(f"  Municípios com dados PNCP : {len(agg)}")
    print(f"  Sem dados PNCP (12 meses) : {len(score) - len(agg)}")
    print(f"  Total licitações          : {agg['n_licitacoes'].sum():,.0f}")
    print(f"  Valor homologado total    : "
          f"R$ {agg['valor_homologado_total'].sum():,.0f}")

    # ── 5. Merge com score ────────────────────────────────────────────────────
    merged = score.merge(agg, on="cod_ibge", how="left")

    # ── 6. Diagnóstico de cruzamentos para o relatório ────────────────────────
    print("\n📊 Cruzamentos para o relatório:")

    risco_baixo = merged[merged["classificacao"] == "🟢 Risco Baixo"]
    print(f"\n  🟢 Risco Baixo ({len(risco_baixo)} municípios):")
    print(f"     Valor homologado : R$ {risco_baixo['valor_homologado_total'].sum():,.0f}")
    print(f"     Licitações       : {risco_baixo['n_licitacoes'].sum():,.0f}")

    lliq_neg = merged[merged["lliq_raw"].fillna(0) < 0]
    print(f"\n  🔴 Lliq negativo ({len(lliq_neg)} municípios):")
    print(f"     Valor homologado : R$ {lliq_neg['valor_homologado_total'].sum():,.0f}")
    print(f"     Licitações       : {lliq_neg['n_licitacoes'].sum():,.0f}")

    sem_dados = merged[
        (merged["classificacao"] == "⚫ Sem Dados") &
        (merged["n_licitacoes"].notna())
    ]
    print(f"\n  ⚫ Sem Dados com licitações ({len(sem_dados)} municípios):")
    print(f"     Valor homologado : R$ {sem_dados['valor_homologado_total'].sum():,.0f}")

    alerta = merged[
        merged["alerta_dispensa"].fillna(False).infer_objects(copy=False) &
        merged["classificacao"].isin(["🔴 Risco Alto", "⛔ Crítico"])
    ]
    print(f"\n  ⚠️  Risco Alto/Crítico + >30% dispensa: {len(alerta)} municípios")
    if len(alerta):
        print(f"  {alerta[['ente', 'score', 'pct_dispensa']].to_string(index=False)}")

    # ── 7. Exportação ─────────────────────────────────────────────────────────
    out_path = paths["outputs"] / f"score_municipios_{u}_pncp.csv"
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n✅ Exportado : {out_path.name}")
    print(f"   {len(merged)} municípios | {len(merged.columns)} colunas")
    print(f"   UF: {uf} | Referência PNCP: últimos {JANELA_MESES} meses")
    print("=" * 65)

    return merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="PB")
    args = parser.parse_args()
    run(uf=args.uf)
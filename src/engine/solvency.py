"""
engine/solvency.py — v7.1.0
source="csv"      → lê CSVs locais (legado, default durante transição)
source="bigquery" → lê mart.mart_indicadores_municipios
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
pd.set_option("future.no_silent_downcasting", True)

from utils.paths import get_paths
from scorers import config as cfg_module
from scorers.config import N_ANOS_CRONICOS_CAP_MEDIO, N_ANOS
from scorers.lliq_scorer    import calcular as calcular_lliq,  pontuar_lliq
from scorers.eorcam_scorer  import calcular as calcular_eorcam, pontuar_eorcam
from scorers.qsiconfi_scorer import calcular as calcular_qsiconfi
from scorers.cauc_scorer    import calcular as calcular_cauc
from scorers.autonomia_scorer import carregar_dca as calcular_autonomia, pontuar_autonomia
from scorers.rproc_scorer   import calcular as calcular_rproc, pontuar_rproc_cronico
from engine.classifier      import classificar, ORDEM_SORT

VERSION = "v7.1.0"


# Carga CSV (legado)

def _carregar_csv(uf: str) -> pd.DataFrame:
    paths = get_paths(uf)
    u = uf.lower()

    siconfi_path = paths["processed"] / f"siconfi_indicadores_{u}.csv"
    cauc_path    = paths["processed"] / f"cauc_situacao_{u}.csv"
    mu_path      = paths["processed"] / f"municipios_{u}_tabela.csv"

    for path, label in [(siconfi_path, "SICONFI"), (cauc_path, "CAUC"), (mu_path, "Municípios")]:
        if not path.exists():
            raise FileNotFoundError(f"{label} não encontrado: {path}")

    df_si = pd.read_csv(siconfi_path, dtype={"cod_ibge": str})
    df_ca = pd.read_csv(cauc_path,    dtype={"cod_ibge": str})
    df_mu = pd.read_csv(mu_path,      dtype={"cod_ibge": str})

    df_si["entregou_rreo"] = df_si["entregou_rreo"].astype(str).str.lower() == "true"
    df_si["lliq_parcial"]  = df_si["lliq_parcial"].astype(str).str.lower()  == "true"

    print(f"  SICONFI : {df_si['cod_ibge'].nunique()} municípios × {df_si['ano'].nunique()} anos")
    print(f"  CAUC    : {len(df_ca)} municípios")

    df_eorcam    = calcular_eorcam(df_si, uf=uf)
    df_qsiconfi  = calcular_qsiconfi(df_si, uf=uf)
    df_cauc      = calcular_cauc(df_ca, uf=uf)
    df_lliq      = calcular_lliq(df_si, df_mu, uf=uf)
    df_rproc     = calcular_rproc(df_si, uf=uf)
    df_autonomia = calcular_autonomia(df_mu, uf=uf)

    df_rpnp = (
        df_si[df_si["entregou_rreo"] & df_si["rrestos_nproc_pct"].notna()]
        .sort_values(["cod_ibge", "ano"], ascending=[True, False])
        .groupby("cod_ibge").first().reset_index()
        [["cod_ibge", "rrestos_nproc_pct"]]
    )

    df = df_mu[["cod_ibge", "ente", "populacao"]].copy()
    for bloco in [df_eorcam, df_qsiconfi, df_cauc, df_autonomia, df_lliq, df_rpnp, df_rproc]:
        df = df.merge(bloco, on="cod_ibge", how="left")

    df["qsiconfi"]        = df["qsiconfi"].fillna(0)
    df["anos_entregues"]  = df["anos_entregues"].fillna(0).astype(int)
    df["ccauc"]           = df["ccauc"].fillna(1.0)
    df["lliq_parcial"]    = df["lliq_parcial"].fillna(False).infer_objects(copy=False)
    df["n_anos_cronicos"] = df["n_anos_cronicos"].fillna(0).astype(int)
    df["contrib_lliq"]      = df["contrib_lliq"].fillna(0)
    df["contrib_autonomia"] = df["contrib_autonomia"].fillna(0)
    df["contrib_rproc"]     = df["contrib_rproc"].fillna(0)

    return df


# Carga BigQuery (novo)

def _carregar_bq(uf: str) -> pd.DataFrame:
    from utils.bigquery_loader import read_mart, read_intermediate

    pesos = cfg_module.get_pesos(uf)

    print(f"  Lendo mart.mart_indicadores_municipios (uf={uf})...")
    df = read_mart("mart_indicadores_municipios", uf=uf)
    df["cod_ibge"] = df["cod_ibge"].astype(str).str.zfill(7)

    # Limpa colunas que possam existir por herança (caso dbt não tenha rodado limpo)
    # Evita sufixos _x e _y no merge.
    legacy_cols = [
        "eorcam_raw", "lliq_raw", "lliq_parcial", "dias_atraso", "decay_fator",
        "dado_suspeito_lliq", "dado_defasado", "autonomia_media", "autonomia_critica",
        "n_licitacoes", "valor_homologado_total", "n_dispensa", "valor_hom_dispensa",
        "pct_dispensa", "ano_ultima_licitacao", "alerta_dispensa"
    ]
    df = df.drop(columns=[c for c in legacy_cols if c in df.columns])

    # Merge PNCP
    print(f"  Lendo mart_pncp_municipios (uf={uf})...")
    try:
        df_pncp = read_mart("mart_pncp_municipios", uf=uf)
        if not df_pncp.empty:
            df_pncp["cod_ibge"] = df_pncp["cod_ibge"].astype(str).str.zfill(7)
            pncp_cols = ["cod_ibge", "n_licitacoes", "valor_homologado_total", "n_dispensa", "valor_hom_dispensa", "pct_dispensa", "ano_ultima_licitacao", "alerta_dispensa"]
            df_pncp = df_pncp[[c for c in pncp_cols if c in df_pncp.columns]]
            df = df.merge(df_pncp, on="cod_ibge", how="left")
    except Exception as e:
        print(f"  ⚠️ Erro ao carregar mart_pncp_municipios: {e}")

    # Merge Postprocessors (SICONFI e DCA) que agora vivem em tabelas separadas
    print(f"  Lendo int_siconfi_postprocessed e int_dca_postprocessed (uf={uf})...")
    try:
        df_siconfi = read_intermediate("int_siconfi_postprocessed", uf=uf)
        if not df_siconfi.empty:
            df_siconfi["cod_ibge"] = df_siconfi["cod_ibge"].astype(str).str.zfill(7)
            siconfi_cols = ["cod_ibge", "eorcam_raw", "lliq_raw", "lliq_parcial", "dias_atraso", "decay_fator", "dado_suspeito_lliq", "dado_defasado"]
            df_siconfi = df_siconfi[[c for c in siconfi_cols if c in df_siconfi.columns]]
            df = df.merge(df_siconfi, on="cod_ibge", how="left")
    except Exception as e:
        print(f"  ⚠️ Erro ao carregar int_siconfi_postprocessed: {e}")

    try:
        df_dca = read_intermediate("int_dca_postprocessed", uf=uf)
        if not df_dca.empty:
            df_dca["cod_ibge"] = df_dca["cod_ibge"].astype(str).str.zfill(7)
            dca_cols = ["cod_ibge", "autonomia_media", "autonomia_critica"]
            df_dca = df_dca[[c for c in dca_cols if c in df_dca.columns]]
            df = df.merge(df_dca, on="cod_ibge", how="left")
    except Exception as e:
        print(f"  ⚠️ Erro ao carregar int_dca_postprocessed: {e}")

    print(f"  {len(df)} municípios base carregados e cruzados")

    # Exportação Local (Audit) — salva mart carregado do BQ para conferência local
    paths = get_paths(uf)
    csv_mart = paths["processed"] / f"mart_indicadores_{uf.lower()}.csv"
    df.to_csv(csv_mart, index=False)
    print(f"  💾 Mart exportado local: {csv_mart.name}")

    if "ccauc" in df.columns:
        csv_cauc = paths["processed"] / f"cauc_situacao_{uf.lower()}.csv"
        df[["cod_ibge", "ccauc"]].to_csv(csv_cauc, index=False)
        print(f"  💾 CAUC exportado local: {csv_cauc.name}")

    # Tipos — BQ retorna correto mas colunas com NULL viram object no pandas
    for col in ["eorcam_raw", "lliq_raw", "autonomia_media",
                "decay_fator", "ccauc", "dias_atraso"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["anos_entregues", "n_anos_cronicos"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    for col in ["lliq_parcial", "dado_suspeito_lliq", "dado_defasado", "autonomia_critica"]:
        if col in df.columns:
            df[col] = df[col].map(lambda v: bool(v) if pd.notnull(v) else False)

    # Norms — to_numeric garante float64 mesmo quando pontuar_* retorna None
    if "eorcam_raw" in df.columns:
        df["eorcam_norm"]    = pd.to_numeric(df["eorcam_raw"].apply(pontuar_eorcam),    errors="coerce")
        df["contrib_eorcam"] = (pesos["eorcam"] * df["eorcam_norm"].fillna(0)).round(4)
    else:
        df["contrib_eorcam"] = 0

    if "lliq_raw" in df.columns:
        df["lliq_norm"]    = pd.to_numeric(df["lliq_raw"].apply(pontuar_lliq),        errors="coerce")
        df["contrib_lliq"] = (
            pesos["lliq"] * df["lliq_norm"].fillna(0) * df.get("decay_fator", pd.Series(1.0, index=df.index)).fillna(1.0)
        ).round(4)
    else:
        df["contrib_lliq"] = 0

    if "anos_entregues" in df.columns:
        df["qsiconfi"]         = df["anos_entregues"] / N_ANOS
        df["contrib_qsiconfi"] = (pesos["qsiconfi"] * df["qsiconfi"]).round(4)
    else:
        df["contrib_qsiconfi"] = 0

    if "ccauc" in df.columns:
        df["contrib_ccauc"] = (pesos["ccauc"] * (1 - df["ccauc"].fillna(1.0))).round(4)
    else:
        df["contrib_ccauc"] = 0

    if "autonomia_media" in df.columns:
        df["autonomia_norm"] = pd.to_numeric(
            df.apply(lambda r: pontuar_autonomia(r["autonomia_media"], r["populacao"], uf), axis=1),
            errors="coerce"
        )
        df["contrib_autonomia"] = (pesos["autonomia"] * df["autonomia_norm"].fillna(0)).round(4)
    else:
        df["contrib_autonomia"] = 0

    if "n_anos_cronicos" in df.columns:
        df["rproc_norm"]    = pd.to_numeric(df["n_anos_cronicos"].apply(pontuar_rproc_cronico), errors="coerce")
        df["contrib_rproc"] = (pesos["rproc"] * df["rproc_norm"].fillna(0)).round(4)
    else:
        df["contrib_rproc"] = 0

    return df

# Orquestrador principal

def run(uf: str = "PB", source: str = "csv") -> pd.DataFrame:
    pesos = cfg_module.get_pesos(uf)

    print("=" * 65)
    print(f" Score de Solvência — SolveLicita {VERSION}")
    print(f" UF: {uf} | Fonte: {source}")
    print(f" Pesos: Lliq={pesos['lliq']} | Ccauc={pesos['ccauc']} | "
          f"Eorcam={pesos['eorcam']} | Qsi={pesos['qsiconfi']} | "
          f"Aut={pesos['autonomia']} | RPproc={pesos['rproc']}")
    print("=" * 65)

    print(f"\n📂 Carregando dados (source={source})...")
    df = _carregar_bq(uf) if source == "bigquery" else _carregar_csv(uf)

    # score
    df["score_base"] = (
        df["contrib_lliq"] + df["contrib_eorcam"] + df["contrib_qsiconfi"] +
        df["contrib_ccauc"] + df["contrib_autonomia"] + df["contrib_rproc"]
    )
    
    if "lliq_parcial" in df.columns:
        df["pen_lliq_parcial"] = df["lliq_parcial"].apply(lambda x: -5.0 if x else 0.0)
    else:
        df["pen_lliq_parcial"] = 0.0
        
    df["pen_situacional"]  = df[["pen_lliq_parcial"]].sum(axis=1).clip(lower=-10.0)
    df["score_bruto"]      = (df["score_base"] + df["pen_situacional"]).clip(lower=0)
    df["score"]            = df["score_bruto"].round(1)
    
    if "eorcam_raw" in df.columns:
        df.loc[df["eorcam_raw"].isna(), "score"] = None
    else:
        df["score"] = None

    df["dado_suspeito"] = df.get("dado_suspeito_lliq", pd.Series(False, index=df.index)).fillna(False)
    if "autonomia_critica" not in df.columns:
        df["autonomia_critica"] = df["autonomia_media"].notna() & (df["autonomia_media"] < 0.08)

    df["classificacao"] = df.apply(
        lambda r: classificar(r["score"], r["anos_entregues"], r["n_anos_cronicos"]), axis=1
    )

    # diagnóstico
    stats = df["score"].dropna()
    print("\n🔍 Distribuição de risco:")
    print(df["classificacao"].value_counts().to_string())
    print(f"\n  Score médio   : {stats.mean():.1f}")
    print(f"  Score mediano : {stats.median():.1f}")
    print(f"  Score mínimo  : {stats.min():.1f}")
    print(f"  Score máximo  : {stats.max():.1f}")
    n_cap_rproc = (df["n_anos_cronicos"] >= N_ANOS_CRONICOS_CAP_MEDIO).sum()
    print(f"  Cap RPcrônico : {n_cap_rproc} municípios")
    print(f"  Pen lliq parc : {(df['pen_lliq_parcial'] < 0).sum()} (−5 pts)")

    # exportação
    OUT_COLS = [
        "cod_ibge", "ente", "populacao", "score", "classificacao",
        "anos_entregues", "eorcam_raw", "lliq_raw", "rrestos_nproc_pct",
        "n_anos_cronicos", "qsiconfi", "ccauc", "autonomia_media",
        "eorcam_norm", "lliq_norm", "rproc_norm", "autonomia_norm",
        "contrib_eorcam", "contrib_lliq", "contrib_qsiconfi",
        "contrib_ccauc", "contrib_autonomia", "contrib_rproc",
        "pen_lliq_parcial", "pen_situacional", "score_base", "score_bruto",
        "dias_atraso", "decay_fator",
        "dado_suspeito", "dado_suspeito_lliq", "dado_defasado",
        "lliq_parcial", "autonomia_critica",
        "n_licitacoes", "valor_homologado_total", "n_dispensa",
        "valor_hom_dispensa", "pct_dispensa", "ano_ultima_licitacao",
        "alerta_dispensa",
    ]
    df_out = df[[c for c in OUT_COLS if c in df.columns]].copy()
    df_out["_ordem"] = df_out["classificacao"].map(ORDEM_SORT)
    df_out = (
        df_out
        .sort_values(["_ordem", "score"], ascending=[True, False], na_position="last")
        .drop(columns="_ordem")
    )

    paths   = get_paths(uf)
    outfile = paths["outputs"] / f"score_municipios_{uf.lower()}_pncp.csv"
    df_out.to_csv(outfile, index=False, encoding="utf-8-sig")

    print(f"\n✅ Score calculado : {df_out['score'].notna().sum()} municípios")
    print(f"   Versão          : {VERSION}")
    print(f"   Salvo em        : {outfile}")
    print("=" * 65)

    return df_out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf",     default="PB")
    parser.add_argument("--source", default="csv", choices=["csv", "bigquery"])
    args = parser.parse_args()
    run(uf=args.uf, source=args.source)
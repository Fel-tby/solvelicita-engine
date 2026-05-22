"""
engine/solvency.py — v7.0
source="csv"      → lê CSVs locais (legado, default durante transição)
source="bigquery" → lê mart.mart_indicadores_municipios
"""

import sys
from pathlib import Path
import json
import unicodedata

import pandas as pd
import numpy as np
pd.set_option("future.no_silent_downcasting", True)

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.paths import get_artifact_path
from src.scorers import config as cfg_module
from src.scorers.config import (
    ICF_FATOR_SEM_REGISTRO,
    N_ANOS,
    N_ANOS_CRONICOS_CAP_MEDIO,
    get_limiar_autonomia_crit,
)
from src.scorers.lliq_scorer import calcular as calcular_lliq, pontuar_lliq
from src.scorers.eorcam_scorer import calcular as calcular_eorcam, pontuar_eorcam
from src.scorers.qsiconfi_scorer import calcular as calcular_qsiconfi
from src.scorers.cauc_scorer import calcular as calcular_cauc
from src.scorers.autonomia_scorer import carregar_dca as calcular_autonomia, pontuar_autonomia
from src.scorers.rproc_scorer import calcular as calcular_rproc, pontuar_rproc_cronico
from src.engine.classifier import classificar, ORDEM_SORT

VERSION = "v8.0"

# PNCP e usado como enriquecimento de mercado, sem alterar o score fiscal.
# Dispensa preserva o nome historico, mas representa apenas modalidade 8.
# Inexigibilidade (modalidade 9) segue separada para auditoria e decisao futura.
PNCP_COLS = [
    "cod_ibge",
    "n_licitacoes",
    "n_com_valor_homologado",
    "n_sem_valor_homologado",
    "valor_homologado_total",
    "n_dispensa",
    "valor_hom_dispensa",
    "pct_dispensa",
    "n_inexigibilidade",
    "valor_hom_inexigibilidade",
    "pct_inexigibilidade",
    "n_contratacao_direta",
    "valor_hom_contratacao_direta",
    "pct_contratacao_direta",
    "ano_ultima_licitacao",
    "alerta_dispensa",
]

SICONFI_POST_COLS = [
    "cod_ibge",
    "eorcam_raw",
    "eorcam_icf_fator",
    "eorcam_icf_previo",
    "eorcam_icf_defasado",
    "eorcam_icf_sem_registro",
    "lliq_ano",
    "lliq_raw",
    "lliq_parcial",
    "dias_atraso",
    "decay_fator",
    "dado_suspeito_lliq",
    "dado_defasado",
    "lliq_icf_fator",
    "lliq_icf_exercicio",
    "lliq_icf_status",
    "lliq_icf_conceito",
    "lliq_icf_previo",
    "lliq_icf_defasado",
    "lliq_icf_sem_registro",
    "rproc_icf_fator",
    "rproc_icf_previo",
    "rproc_icf_defasado",
    "rproc_icf_sem_registro",
]

DCA_POST_COLS = [
    "cod_ibge",
    "autonomia_media",
    "autonomia_critica",
    "autonomia_icf_fator",
    "autonomia_icf_previo",
    "autonomia_icf_defasado",
    "autonomia_icf_sem_registro",
]


def _ascii_console(text: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(text))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.split())


def _build_rproc_historico(df_si: pd.DataFrame) -> pd.DataFrame:
    required = {"cod_ibge", "ano", "entregou_rreo", "rproc_pct"}
    if not required.issubset(df_si.columns):
        return pd.DataFrame(columns=["cod_ibge", "rproc_historico_json"])

    df_hist = df_si[
        df_si["ano"].isin(cfg_module.ANOS_REF)
        & df_si["entregou_rreo"]
        & df_si["rproc_pct"].notna()
    ].copy()

    if df_hist.empty:
        return pd.DataFrame(columns=["cod_ibge", "rproc_historico_json"])

    numeric_cols = ["ano", "rproc_pct", "rrestos_processados", "receita_realizada"]
    for col in numeric_cols:
        if col in df_hist.columns:
            df_hist[col] = pd.to_numeric(df_hist[col], errors="coerce")

    def build_payload(group: pd.DataFrame) -> str:
        payload = []
        for _, row in group.sort_values("ano").iterrows():
            if pd.isna(row["ano"]) or pd.isna(row["rproc_pct"]):
                continue

            rproc_pct = float(row["rproc_pct"])
            item = {
                "ano": int(row["ano"]),
                "rproc_pct": round(rproc_pct, 2),
                "cronico": bool(rproc_pct > cfg_module.LIMIAR_RPROC_CRONICO),
            }

            for col in ["rrestos_processados", "receita_realizada"]:
                if col in group.columns and pd.notna(row.get(col)):
                    item[col] = round(float(row[col]), 2)

            payload.append(item)

        return json.dumps(payload, ensure_ascii=False)

    return pd.DataFrame(
        [
            {"cod_ibge": cod_ibge, "rproc_historico_json": build_payload(group)}
            for cod_ibge, group in df_hist.groupby("cod_ibge")
        ]
    )


# Carga CSV (legado)

def _carregar_csv(uf: str) -> pd.DataFrame:
    siconfi_path = get_artifact_path(uf, "siconfi_indicadores")
    cauc_path = get_artifact_path(uf, "cauc_situacao")
    mu_path = get_artifact_path(uf, "municipios_tabela")

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

    df_rproc_atual = (
        df_si[df_si["entregou_rreo"] & df_si["rproc_pct"].notna()]
        .sort_values(["cod_ibge", "ano"], ascending=[True, False])
        .groupby("cod_ibge").first().reset_index()
        [["cod_ibge", "rproc_pct"]]
        .rename(columns={"rproc_pct": "rproc_pct_atual"})
    )
    df_rproc_historico = _build_rproc_historico(df_si)

    df = df_mu[["cod_ibge", "ente", "populacao"]].copy()
    for bloco in [
        df_eorcam,
        df_qsiconfi,
        df_cauc,
        df_autonomia,
        df_lliq,
        df_rproc_atual,
        df_rproc_historico,
        df_rproc,
    ]:
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

def _carregar_bq(uf: str, *, strict_bigquery: bool = False) -> pd.DataFrame:
    from src.utils.bigquery_loader import read_mart, read_intermediate

    pesos = cfg_module.get_pesos(uf)

    print(f"  Lendo mart.mart_indicadores_municipios (uf={uf})...")
    df = read_mart("mart_indicadores_municipios", uf=uf, strict=strict_bigquery)
    df["cod_ibge"] = df["cod_ibge"].astype(str).str.zfill(7)

    # Limpa colunas que possam existir por herança (caso dbt não tenha rodado limpo)
    # Evita sufixos _x e _y no merge.
    legacy_cols = [
        "eorcam_raw", "lliq_raw", "lliq_parcial", "dias_atraso", "decay_fator",
        "dado_suspeito_lliq", "dado_defasado", "autonomia_media", "autonomia_critica",
        *[col for col in SICONFI_POST_COLS if col != "cod_ibge"],
        *[col for col in DCA_POST_COLS if col != "cod_ibge"],
        *[col for col in PNCP_COLS if col != "cod_ibge"],
    ]
    df = df.drop(columns=[c for c in legacy_cols if c in df.columns])

    # Merge PNCP
    print(f"  Lendo mart_pncp_municipios (uf={uf})...")
    if strict_bigquery:
        df_pncp = read_mart("mart_pncp_municipios", uf=uf, strict=True)
        if not df_pncp.empty:
            df_pncp["cod_ibge"] = df_pncp["cod_ibge"].astype(str).str.zfill(7)
            df_pncp = df_pncp[[c for c in PNCP_COLS if c in df_pncp.columns]]
            df = df.merge(df_pncp, on="cod_ibge", how="left")
    else:
        try:
            df_pncp = read_mart("mart_pncp_municipios", uf=uf, strict=False)
            if not df_pncp.empty:
                df_pncp["cod_ibge"] = df_pncp["cod_ibge"].astype(str).str.zfill(7)
                df_pncp = df_pncp[[c for c in PNCP_COLS if c in df_pncp.columns]]
                df = df.merge(df_pncp, on="cod_ibge", how="left")
        except Exception as e:
            print(f"  ⚠️ Erro ao carregar mart_pncp_municipios: {e}")

    # Merge Postprocessors (SICONFI e DCA) que agora vivem em tabelas separadas
    print(f"  Lendo int_siconfi_postprocessed e int_dca_postprocessed (uf={uf})...")
    if strict_bigquery:
        df_siconfi = read_intermediate("int_siconfi_postprocessed", uf=uf, strict=True)
        if not df_siconfi.empty:
            df_siconfi["cod_ibge"] = df_siconfi["cod_ibge"].astype(str).str.zfill(7)
            df_siconfi = df_siconfi[[c for c in SICONFI_POST_COLS if c in df_siconfi.columns]]
            df = df.merge(df_siconfi, on="cod_ibge", how="left")

        df_dca = read_intermediate("int_dca_postprocessed", uf=uf, strict=True)
        if not df_dca.empty:
            df_dca["cod_ibge"] = df_dca["cod_ibge"].astype(str).str.zfill(7)
            df_dca = df_dca[[c for c in DCA_POST_COLS if c in df_dca.columns]]
            df = df.merge(df_dca, on="cod_ibge", how="left")
    else:
        try:
            df_siconfi = read_intermediate("int_siconfi_postprocessed", uf=uf, strict=False)
            if not df_siconfi.empty:
                df_siconfi["cod_ibge"] = df_siconfi["cod_ibge"].astype(str).str.zfill(7)
                df_siconfi = df_siconfi[[c for c in SICONFI_POST_COLS if c in df_siconfi.columns]]
                df = df.merge(df_siconfi, on="cod_ibge", how="left")
        except Exception as e:
            print(f"  ⚠️ Erro ao carregar int_siconfi_postprocessed: {e}")

        try:
            df_dca = read_intermediate("int_dca_postprocessed", uf=uf, strict=False)
            if not df_dca.empty:
                df_dca["cod_ibge"] = df_dca["cod_ibge"].astype(str).str.zfill(7)
                df_dca = df_dca[[c for c in DCA_POST_COLS if c in df_dca.columns]]
                df = df.merge(df_dca, on="cod_ibge", how="left")
        except Exception as e:
            print(f"  ⚠️ Erro ao carregar int_dca_postprocessed: {e}")

    print(f"  {len(df)} municípios base carregados e cruzados")

    # Exportacao local de auditoria do mart carregado do BQ.
    csv_mart = get_artifact_path(uf, "mart_indicadores")
    df.to_csv(csv_mart, index=False)
    print(f"  Mart exportado local: {csv_mart.name}")

    if "ccauc" in df.columns:
        csv_cauc = get_artifact_path(uf, "cauc_situacao")
        df[["cod_ibge", "ccauc"]].to_csv(csv_cauc, index=False)
        print(f"  CAUC exportado local: {csv_cauc.name}")

    # Tipos — BQ retorna correto mas colunas com NULL viram object no pandas
    for col in [
        "eorcam_raw",
        "lliq_raw",
        "autonomia_media",
        "rproc_pct_atual",
        "decay_fator",
        "ccauc",
        "dias_atraso",
        "eorcam_icf_fator",
        "lliq_icf_fator",
        "rproc_icf_fator",
        "autonomia_icf_fator",
        "lliq_icf_exercicio",
        "lliq_ano",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["anos_entregues", "n_anos_cronicos", "n_graves", "n_moderadas", "n_leves"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    for col in [
        "lliq_parcial",
        "dado_suspeito_lliq",
        "dado_defasado",
        "autonomia_critica",
        "eorcam_icf_previo",
        "eorcam_icf_defasado",
        "eorcam_icf_sem_registro",
        "lliq_icf_previo",
        "lliq_icf_defasado",
        "lliq_icf_sem_registro",
        "rproc_icf_previo",
        "rproc_icf_defasado",
        "rproc_icf_sem_registro",
        "autonomia_icf_previo",
        "autonomia_icf_defasado",
        "autonomia_icf_sem_registro",
    ]:
        if col in df.columns:
            df[col] = df[col].map(lambda v: bool(v) if pd.notnull(v) else False)

    for col in [
        "eorcam_icf_fator",
        "lliq_icf_fator",
        "rproc_icf_fator",
        "autonomia_icf_fator",
    ]:
        if col not in df.columns:
            df[col] = ICF_FATOR_SEM_REGISTRO
        df[col] = (
            pd.to_numeric(df[col], errors="coerce")
            .fillna(ICF_FATOR_SEM_REGISTRO)
            .clip(lower=ICF_FATOR_SEM_REGISTRO, upper=1.0)
        )

    # Norms — to_numeric garante float64 mesmo quando pontuar_* retorna None
    if "eorcam_raw" in df.columns:
        df["eorcam_norm"]    = pd.to_numeric(df["eorcam_raw"].apply(pontuar_eorcam),    errors="coerce")
        df["contrib_eorcam_base"] = (pesos["eorcam"] * df["eorcam_norm"].fillna(0)).round(4)
        df["contrib_eorcam"] = (
            df["contrib_eorcam_base"] * df["eorcam_icf_fator"]
        ).round(4)
    else:
        df["contrib_eorcam_base"] = 0
        df["contrib_eorcam"] = 0

    if "lliq_raw" in df.columns:
        df["lliq_norm"]    = pd.to_numeric(df["lliq_raw"].apply(pontuar_lliq),        errors="coerce")
        df["contrib_lliq_base"] = (
            pesos["lliq"] * df["lliq_norm"].fillna(0) * df.get("decay_fator", pd.Series(1.0, index=df.index)).fillna(1.0)
        ).round(4)
        df["contrib_lliq"] = (df["contrib_lliq_base"] * df["lliq_icf_fator"]).round(4)
    else:
        df["contrib_lliq_base"] = 0
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
        df["contrib_autonomia_base"] = (
            pesos["autonomia"] * df["autonomia_norm"].fillna(0)
        ).round(4)
        df["contrib_autonomia"] = (
            df["contrib_autonomia_base"] * df["autonomia_icf_fator"]
        ).round(4)
    else:
        df["contrib_autonomia_base"] = 0
        df["contrib_autonomia"] = 0

    if "n_anos_cronicos" in df.columns:
        df["rproc_norm"]    = pd.to_numeric(df["n_anos_cronicos"].apply(pontuar_rproc_cronico), errors="coerce")
        df["contrib_rproc_base"] = (pesos["rproc"] * df["rproc_norm"].fillna(0)).round(4)
        df["contrib_rproc"] = (df["contrib_rproc_base"] * df["rproc_icf_fator"]).round(4)
    else:
        df["contrib_rproc_base"] = 0
        df["contrib_rproc"] = 0

    total_peso_icf = pesos["lliq"] + pesos["eorcam"] + pesos["autonomia"] + pesos["rproc"]
    if total_peso_icf > 0:
        df["icf_fator_medio"] = (
            df["lliq_icf_fator"] * pesos["lliq"]
            + df["eorcam_icf_fator"] * pesos["eorcam"]
            + df["autonomia_icf_fator"] * pesos["autonomia"]
            + df["rproc_icf_fator"] * pesos["rproc"]
        ) / total_peso_icf
        df["icf_fator_medio"] = df["icf_fator_medio"].round(6)
    else:
        df["icf_fator_medio"] = 1.0

    return df

# Orquestrador principal

def run(
    uf: str = "PB",
    source: str = "csv",
    *,
    strict_bigquery: bool = False,
    publish_snapshot: bool = False,
    run_type: str = "manual",
    pipeline_mode: str | None = None,
    pipeline_version: str | None = None,
    snapshot_notes: str | None = None,
) -> pd.DataFrame:
    pesos = cfg_module.get_pesos(uf)
    source_label = source
    if source == "bigquery":
        source_label = "bigquery (strict)" if strict_bigquery else "bigquery (fallback permitido)"

    print("=" * 65)
    print(f" Score de Solvência — SolveLicita {VERSION}")
    print(f" UF: {uf} | Fonte: {source_label}")
    print(f" Pesos: Lliq={pesos['lliq']} | Ccauc={pesos['ccauc']} | "
          f"Eorcam={pesos['eorcam']} | Qsi={pesos['qsiconfi']} | "
          f"Aut={pesos['autonomia']} | RPproc={pesos['rproc']}")
    print("=" * 65)

    print(f"\nCarregando dados (source={source_label})...")
    df = _carregar_bq(uf, strict_bigquery=strict_bigquery) if source == "bigquery" else _carregar_csv(uf)

    if "rproc_historico_json" not in df.columns:
        df["rproc_historico_json"] = "[]"
    else:
        df["rproc_historico_json"] = df["rproc_historico_json"].fillna("[]")

    for col in [
        "contrib_lliq",
        "contrib_eorcam",
        "contrib_qsiconfi",
        "contrib_ccauc",
        "contrib_autonomia",
        "contrib_rproc",
    ]:
        if col not in df.columns:
            df[col] = 0.0

    for base_col, final_col in [
        ("contrib_lliq_base", "contrib_lliq"),
        ("contrib_eorcam_base", "contrib_eorcam"),
        ("contrib_autonomia_base", "contrib_autonomia"),
        ("contrib_rproc_base", "contrib_rproc"),
    ]:
        if base_col not in df.columns:
            df[base_col] = df[final_col]

    if "icf_fator_medio" not in df.columns:
        df["icf_fator_medio"] = 1.0

    # score
    df["score_base_pre_icf"] = (
        df["contrib_lliq_base"] + df["contrib_eorcam_base"] + df["contrib_qsiconfi"] +
        df["contrib_ccauc"] + df["contrib_autonomia_base"] + df["contrib_rproc_base"]
    )
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
        if "autonomia_media" in df.columns:
            limiar_autonomia = get_limiar_autonomia_crit(uf)
            df["autonomia_critica"] = (
                df["autonomia_media"].notna() &
                (df["autonomia_media"] < limiar_autonomia)
            )
        else:
            df["autonomia_critica"] = False

    df["classificacao"] = df.apply(
        lambda r: classificar(r["score"], r["anos_entregues"], r["n_anos_cronicos"]), axis=1
    )

    # diagnóstico
    stats = df["score"].dropna()
    print("\nDistribuicao de risco:")
    classif_counts = df["classificacao"].value_counts()
    classif_counts.index = [_ascii_console(idx) for idx in classif_counts.index]
    print(classif_counts.to_string())
    print(f"\n  Score médio   : {stats.mean():.1f}")
    print(f"  Score mediano : {stats.median():.1f}")
    print(f"  Score mínimo  : {stats.min():.1f}")
    print(f"  Score máximo  : {stats.max():.1f}")
    n_cap_rproc = (df["n_anos_cronicos"] >= N_ANOS_CRONICOS_CAP_MEDIO).sum()
    print(f"  Cap RPcrônico : {n_cap_rproc} municípios")
    print(f"  Pen lliq parc : {(df['pen_lliq_parcial'] < 0).sum()} (-5 pts)")

    # exportação
    OUT_COLS = [
        "cod_ibge", "ente", "populacao", "score", "classificacao",
        "anos_entregues", "eorcam_raw", "lliq_raw", "rproc_pct_atual",
        "rproc_historico_json", "n_anos_cronicos", "qsiconfi", "ccauc", "autonomia_media",
        "n_graves", "n_moderadas", "n_leves", "pendencias", "pendencias_cauc_json",
        "eorcam_norm", "lliq_norm", "rproc_norm", "autonomia_norm",
        "icf_fator_medio",
        "contrib_eorcam", "contrib_lliq", "contrib_qsiconfi",
        "contrib_ccauc", "contrib_autonomia", "contrib_rproc",
        "contrib_eorcam_base", "contrib_lliq_base",
        "contrib_autonomia_base", "contrib_rproc_base",
        "pen_lliq_parcial", "pen_situacional", "score_base_pre_icf",
        "score_base", "score_bruto",
        "dias_atraso", "decay_fator",
        "eorcam_icf_fator", "eorcam_icf_previo", "eorcam_icf_defasado",
        "eorcam_icf_sem_registro",
        "lliq_ano", "lliq_icf_exercicio", "lliq_icf_status",
        "lliq_icf_conceito", "lliq_icf_fator", "lliq_icf_previo",
        "lliq_icf_defasado", "lliq_icf_sem_registro",
        "rproc_icf_fator", "rproc_icf_previo", "rproc_icf_defasado",
        "rproc_icf_sem_registro",
        "autonomia_icf_fator", "autonomia_icf_previo",
        "autonomia_icf_defasado", "autonomia_icf_sem_registro",
        "dado_suspeito", "dado_suspeito_lliq", "dado_defasado",
        "lliq_parcial", "autonomia_critica",
        "n_licitacoes", "n_com_valor_homologado", "n_sem_valor_homologado",
        "valor_homologado_total",
        "n_dispensa", "valor_hom_dispensa", "pct_dispensa",
        "n_inexigibilidade", "valor_hom_inexigibilidade", "pct_inexigibilidade",
        "n_contratacao_direta", "valor_hom_contratacao_direta",
        "pct_contratacao_direta",
        "ano_ultima_licitacao", "alerta_dispensa",
    ]
    df_out = df[[c for c in OUT_COLS if c in df.columns]].copy()
    df_out["_ordem"] = df_out["classificacao"].map(ORDEM_SORT)
    df_out = (
        df_out
        .sort_values(["_ordem", "score"], ascending=[True, False], na_position="last")
        .drop(columns="_ordem")
    )

    outfile = get_artifact_path(uf, "score_municipios_pncp")
    df_out.to_csv(outfile, index=False, encoding="utf-8-sig")

    print(f"\nScore calculado : {df_out['score'].notna().sum()} municipios")
    print(f"   Versão          : {VERSION}")
    print(f"   Salvo em        : {outfile}")

    if publish_snapshot:
        try:
            from src.utils.snapshot_publisher import publish_snapshot as publish_snapshot_fn

            publish_snapshot_fn(
                df_out,
                uf=uf,
                methodology_version=VERSION,
                run_type=run_type,
                pipeline_mode=pipeline_mode,
                source_mode=source,
                pipeline_version=pipeline_version,
                notes=snapshot_notes,
            )
        except Exception as exc:
            print(f"  [SNAPSHOT] ⚠️ Falha ao publicar snapshot histórico: {exc}")

    print("=" * 65)

    return df_out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf",     default="PB")
    parser.add_argument("--source", default="csv", choices=["csv", "bigquery"])
    parser.add_argument("--strict-bigquery", action="store_true")
    args = parser.parse_args()
    run(uf=args.uf, source=args.source, strict_bigquery=args.strict_bigquery)

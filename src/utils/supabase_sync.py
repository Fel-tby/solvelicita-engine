"""
src/utils/supabase_sync.py — v2.0
"""

import json
import math
import sys
from pathlib import Path

import pandas as pd
from supabase import create_client, Client

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config.settings import get_supabase_settings
from src.utils.paths import get_artifact_path

COLUNAS = {
    "cod_ibge": "cod_ibge", "ente": "ente", "populacao": "populacao",
    "score": "score", "classificacao": "classificacao",
    "contrib_lliq": "contrib_lliq", "contrib_ccauc": "contrib_ccauc",
    "contrib_eorcam": "contrib_eorcam", "contrib_qsiconfi": "contrib_qsiconfi",
    "contrib_autonomia": "contrib_autonomia", "contrib_rproc": "contrib_rproc",
    "lliq_raw": "lliq_raw", "eorcam_raw": "eorcam_raw",
    "rproc_pct_atual": "rproc_pct_atual",
    "rproc_historico_json": "rproc_historico_json",
    "qsiconfi": "qsiconfi", "ccauc": "ccauc", "autonomia_media": "autonomia_media",
    "n_graves": "n_graves", "n_moderadas": "n_moderadas", "n_leves": "n_leves",
    "pendencias": "pendencias", "pendencias_cauc_json": "pendencias_cauc_json",
    "lliq_norm": "lliq_norm", "eorcam_norm": "eorcam_norm",
    "rproc_norm": "rproc_norm", "autonomia_norm": "autonomia_norm",
    "score_base": "score_base", "score_bruto": "score_bruto",
    "pen_lliq_parcial": "pen_lliq_parcial", "pen_situacional": "pen_situacional",
    "n_anos_cronicos": "n_anos_cronicos", "anos_entregues": "anos_entregues",
    "lliq_parcial": "lliq_parcial", "dado_defasado": "dado_defasado",
    "dado_suspeito": "dado_suspeito", "dado_suspeito_lliq": "dado_suspeito_lliq",
    "autonomia_critica": "autonomia_critica",
    "dias_atraso": "dias_atraso", "decay_fator": "decay_fator",
    # Campos PNCP. "dispensa" foi mantido para compatibilidade com producao,
    # mas agora significa apenas modalidade 8. Modalidade 9 segue separada
    # como inexigibilidade; 8 + 9 e exposto como contratacao direta.
    "n_licitacoes": "n_licitacoes", "valor_homologado_total": "valor_homologado_total",
    "n_com_valor_homologado": "n_com_valor_homologado",
    "n_sem_valor_homologado": "n_sem_valor_homologado",
    "n_dispensa": "n_dispensa", "valor_hom_dispensa": "valor_hom_dispensa",
    "n_inexigibilidade": "n_inexigibilidade",
    "valor_hom_inexigibilidade": "valor_hom_inexigibilidade",
    "pct_inexigibilidade": "pct_inexigibilidade",
    "n_contratacao_direta": "n_contratacao_direta",
    "valor_hom_contratacao_direta": "valor_hom_contratacao_direta",
    "pct_contratacao_direta": "pct_contratacao_direta",
    "ano_ultima_licitacao": "ano_ultima_licitacao",
    "pct_dispensa": "pct_dispensa", "alerta_dispensa": "alerta_dispensa",

    # SICONFI ICF Quality columns
    "icf_fator_medio": "icf_fator_medio",
    "contrib_eorcam_base": "contrib_eorcam_base",
    "contrib_lliq_base": "contrib_lliq_base",
    "contrib_autonomia_base": "contrib_autonomia_base",
    "contrib_rproc_base": "contrib_rproc_base",
    "score_base_pre_icf": "score_base_pre_icf",
    
    "eorcam_icf_fator": "eorcam_icf_fator",
    "eorcam_icf_previo": "eorcam_icf_previo",
    "eorcam_icf_defasado": "eorcam_icf_defasado",
    "eorcam_icf_sem_registro": "eorcam_icf_sem_registro",
    
    "lliq_ano": "lliq_ano",
    "lliq_icf_exercicio": "lliq_icf_exercicio",
    "lliq_icf_status": "lliq_icf_status",
    "lliq_icf_conceito": "lliq_icf_conceito",
    "lliq_icf_fator": "lliq_icf_fator",
    "lliq_icf_previo": "lliq_icf_previo",
    "lliq_icf_defasado": "lliq_icf_defasado",
    "lliq_icf_sem_registro": "lliq_icf_sem_registro",
    
    "rproc_icf_fator": "rproc_icf_fator",
    "rproc_icf_previo": "rproc_icf_previo",
    "rproc_icf_defasado": "rproc_icf_defasado",
    "rproc_icf_sem_registro": "rproc_icf_sem_registro",
    
    "autonomia_icf_fator": "autonomia_icf_fator",
    "autonomia_icf_previo": "autonomia_icf_previo",
    "autonomia_icf_defasado": "autonomia_icf_defasado",
    "autonomia_icf_sem_registro": "autonomia_icf_sem_registro",
}

COLUNAS_INTEGER = {
    "n_licitacoes", "n_com_valor_homologado", "n_sem_valor_homologado",
    "n_dispensa", "n_inexigibilidade", "n_contratacao_direta",
    "ano_ultima_licitacao",
    "n_anos_cronicos", "anos_entregues", "populacao", "dias_atraso",
    "n_graves", "n_moderadas", "n_leves",
    "lliq_ano", "lliq_icf_exercicio",
}
COLUNAS_BOOLEAN = {
    "lliq_parcial", "dado_defasado", "dado_suspeito",
    "dado_suspeito_lliq", "autonomia_critica", "alerta_dispensa",
    "eorcam_icf_previo", "eorcam_icf_defasado", "eorcam_icf_sem_registro",
    "lliq_icf_previo", "lliq_icf_defasado", "lliq_icf_sem_registro",
    "rproc_icf_previo", "rproc_icf_defasado", "rproc_icf_sem_registro",
    "autonomia_icf_previo", "autonomia_icf_defasado", "autonomia_icf_sem_registro",
}
COLUNAS_JSON = {"rproc_historico_json"}

def _conectar() -> Client:
    cfg = get_supabase_settings()
    if not cfg.is_configured:
        raise EnvironmentError("SUPABASE_URL e SUPABASE_KEY precisam estar configurados no ambiente.")
    return create_client(cfg.url, cfg.key)

def _sanitizar_json(value):
    if value is None:
        return []
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return []
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"NaN", "nan", "None", "none", "inf", "-inf"}:
            return []
        return json.loads(text)
    return value

def _sanitizar(rec: dict) -> dict:
    NAN_STRINGS = {"NaN", "nan", "None", "none", "inf", "-inf"}
    resultado = {}
    for k, v in rec.items():
        if k in COLUNAS_JSON:
            resultado[k] = _sanitizar_json(v)
        elif v is None:
            resultado[k] = None
        elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            resultado[k] = None
        elif isinstance(v, str) and v in NAN_STRINGS:
            resultado[k] = None
        elif k in COLUNAS_INTEGER and isinstance(v, float):
            resultado[k] = int(v)
        else:
            resultado[k] = v
    return resultado

def _preparar_registros(csv_path: Path, uf: str) -> list:
    df = pd.read_csv(csv_path, dtype={"cod_ibge": str})

    colunas_presentes = {k: v for k, v in COLUNAS.items() if k in df.columns}
    ausentes = set(COLUNAS.keys()) - set(colunas_presentes.keys())
    if ausentes:
        print(f"  [AVISO] Colunas ausentes (ignoradas): {sorted(ausentes)}")

    df = df[list(colunas_presentes.keys())].rename(columns=colunas_presentes)
    df["uf"] = uf.upper()  # ← chave composta

    for col in COLUNAS_BOOLEAN:
        if col in df.columns:
            df[col] = df[col].map(lambda v: bool(v) if pd.notnull(v) else None)

    registros = json.loads(
        df.to_json(orient="records", force_ascii=False, date_format="iso")
    )
    return [_sanitizar(r) for r in registros]

def run(uf: str = "PB") -> None:
    csv_path = get_artifact_path(uf, "score_municipios_pncp")


    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV não encontrado: {csv_path}\n"
            "Execute primeiro: python src/engine/solvency.py"
        )

    print(f"Conectando ao Supabase...")
    supabase = _conectar()

    print(f"Lendo {csv_path.name}...")
    registros = _preparar_registros(csv_path, uf)

    import time
    print(f"Enviando {len(registros)} municípios (uf={uf})...")
    LOTE = 30
    total = 0
    for i in range(0, len(registros), LOTE):
        lote = registros[i: i + LOTE]
        response = (
            supabase.table("municipios")
            .upsert(lote, on_conflict="cod_ibge,uf")  # ← chave composta
            .execute()
        )
        n = len(response.data) if response.data else 0
        total += n
        print(f"  Lote {i // LOTE + 1}: {n} registros")
        time.sleep(0.1)

    print(f"[OK] Supabase sincronizado — {total} registros.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", default="PB")
    args = parser.parse_args()
    run(uf=args.uf)

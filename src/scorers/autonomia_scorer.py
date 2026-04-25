"""
autonomia_scorer.py — Pontuação de Autonomia Fiscal (peso 10%)
Fonte: FINBRA/DCA

Nota: scaixa foi incorporado ao Lliq via RGF Anexo 05 — não calculado aqui.
"""
import pandas as pd
import numpy as np
from src.utils.paths import get_artifact_path
from src.scorers import config as cfg_module


def _porte(pop: int) -> str:
    if pop < 10_000:  return "micro"
    if pop < 50_000:  return "pequeno"
    if pop < 200_000: return "médio"
    return "grande"


def pontuar_autonomia(x, pop: int, uf: str = "PB"):
    """
    Receita tributária própria / Receita Corrente Total → [0.0, 1.0].
    Sigmoid regionalizada por porte — parâmetros lidos do config por UF.
    """
    if pd.isna(x) or pd.isna(pop):
        return None
    mu, k = cfg_module.get_sigmoid_autonomia(uf, _porte(int(pop)))
    return round(float(1.0 / (1.0 + np.exp(-k * (x - mu)))), 4)


def carregar_dca(municipios: pd.DataFrame, uf: str = "PB") -> pd.DataFrame:
    """
    Carrega dca_indicadores_{uf}.csv e calcula contribuição de Autonomia.

    Parâmetros
    ----------
    municipios : DataFrame mestre com colunas [cod_ibge, ente, populacao]
    uf         : sigla do estado

    Retorna
    -------
    DataFrame com colunas:
        cod_ibge, autonomia_media, autonomia_norm, contrib_autonomia
    """
    pesos = cfg_module.get_pesos(uf)
    caminho = get_artifact_path(uf, "dca_indicadores")

    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho.name} nao encontrado em {caminho.parent}.\n"
            "Execute src/collectors/dca.py primeiro."
        )

    dca = pd.read_csv(caminho, dtype={"cod_ibge": str})
    dca = dca.merge(municipios[["cod_ibge", "populacao"]], on="cod_ibge", how="left")

    dca["autonomia_norm"]    = dca.apply(
        lambda r: pontuar_autonomia(r["autonomia_media"], r["populacao"], uf), axis=1
    )
    dca["contrib_autonomia"] = (pesos["autonomia"] * dca["autonomia_norm"]).round(4)

    return dca[["cod_ibge", "autonomia_media", "autonomia_norm", "contrib_autonomia"]]

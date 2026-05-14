import pandas as pd
from src.scorers import config as cfg_module
from src.scorers.config import ANOS_REF, N_ANOS


def calcular(df_si: pd.DataFrame, uf: str = "PB") -> pd.DataFrame:
    """
    Conta anos com RREO entregue na janela ANOS_REF e normaliza para [0, 1].
    Cap duro de classificação é aplicado no engine/classifier.py.

    Entrada : df_si com colunas [cod_ibge, ano, entregou_rreo]
    Saída   : DataFrame [cod_ibge, anos_entregues, qsiconfi, contrib_qsiconfi]
    """
    pesos = cfg_module.get_pesos(uf)

    df_qsi = (
        df_si[df_si["ano"].isin(ANOS_REF)]
        .groupby("cod_ibge")["entregou_rreo"]
        .agg(anos_entregues="sum")
        .reset_index()
    )
    df_qsi["qsiconfi"]         = df_qsi["anos_entregues"] / N_ANOS
    df_qsi["contrib_qsiconfi"] = (pesos["qsiconfi"] * df_qsi["qsiconfi"]).round(4)
    return df_qsi[["cod_ibge", "anos_entregues", "qsiconfi", "contrib_qsiconfi"]]

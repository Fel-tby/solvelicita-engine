"""
Coletor de tabela base de municipios por UF (backbone geografico).
Consulta a API do SICONFI e salva o cadastro oficial de municipios.
Pre-requisito para todos os demais coletores.

Rodar individualmente:
    python src/collectors/municipios.py
    python src/collectors/municipios.py --uf CE
"""

import sys
from pathlib import Path

import httpx
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.bigquery_loader import publish_raw_merge
from src.utils.paths import get_paths


REQUIRED_COLUMNS = ["cod_ibge", "uf", "ente", "populacao"]
MUNICIPIOS_API_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes"


def _preparar_lote_municipios(items: list[dict], uf: str) -> pd.DataFrame:
    """Valida e normaliza o lote bruto antes de publicar no BigQuery."""
    df = pd.DataFrame(items).copy()
    if df.empty:
        raise ValueError(f"Nenhum municipio da UF {uf} foi retornado pela API.")

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            "Resposta da API de municipios sem colunas obrigatorias: "
            f"{', '.join(missing)}"
        )

    df["uf"] = df["uf"].astype(str).str.upper().str.strip()
    if set(df["uf"].dropna()) != {uf}:
        raise ValueError(
            f"Lote de municipios contem UFs divergentes do esperado '{uf}'."
        )

    df["cod_ibge"] = (
        df["cod_ibge"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(7)
    )
    invalid_cod = df["cod_ibge"].isna() | df["cod_ibge"].eq("")
    if invalid_cod.any():
        raise ValueError("Lote de municipios contem cod_ibge nulo ou vazio.")

    before = len(df)
    df = (
        df.drop_duplicates(subset=["uf", "cod_ibge"], keep="last")
        .sort_values(["uf", "cod_ibge"])
        .reset_index(drop=True)
    )
    removed = before - len(df)
    if removed:
        print(f"  [municipios] dedupe local: {removed} duplicatas removidas")

    return df


def _baixar_municipios_api(uf: str) -> pd.DataFrame:
    print(f"Buscando municipios de {uf} no SICONFI...")
    response = httpx.get(MUNICIPIOS_API_URL, timeout=30)
    response.raise_for_status()
    todos = response.json().get("items", [])

    items_uf = [
        item for item in todos
        if item.get("uf") == uf and item.get("esfera") == "M"
    ]
    return _preparar_lote_municipios(items_uf, uf)


def carregar_municipios(
    uf: str = "PB",
    *,
    prefer_local: bool = True,
    persist_local: bool = False,
) -> pd.DataFrame:
    """
    Carrega a base municipal da UF.

    Preferencialmente reutiliza o CSV local quando existir; caso contrario,
    busca direto na API do SICONFI e opcionalmente persiste o artefato local.
    """
    uf = uf.upper()
    paths = get_paths(uf)
    out = paths["processed"] / f"municipios_{uf.lower()}_tabela.csv"

    if prefer_local and out.exists():
        df_local = pd.read_csv(out, dtype={"cod_ibge": str})
        return _preparar_lote_municipios(df_local.to_dict("records"), uf)

    df = _baixar_municipios_api(uf)
    if persist_local:
        df.to_csv(out, index=False, encoding="utf-8")
        print(f"OK {len(df)} municipios salvos em {out}")
    return df


def run(uf: str = "PB") -> pd.DataFrame:
    """
    Busca municipios da UF informada no SICONFI e salva CSV de referencia.
    Retorna DataFrame com colunas: cod_ibge, ente, cnpj, populacao, ...
    """
    uf = uf.upper()
    df = carregar_municipios(uf, prefer_local=False, persist_local=True)
    print(df[["cod_ibge", "ente", "cnpj", "populacao"]].head())

    publish_raw_merge(
        df,
        table="dim_municipios",
        uf=uf,
        key_cols=["uf", "cod_ibge"],
    )
    return df


if __name__ == "__main__":
    uf_arg = "PB"
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--uf" and i + 1 < len(args):
            uf_arg = args[i + 1]
        elif arg.startswith("--uf="):
            uf_arg = arg.split("=", 1)[1]
    run(uf=uf_arg)

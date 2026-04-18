"""
Coletor CAUC — CKAN Tesouro Transparente.
Responsabilidade: baixar o relatório nacional, filtrar para municípios da
UF informada e publicar os dados brutos no BigQuery (sem classificacao de
pendencias).

A classificação de pendências por gravidade é feita por:
    src/processors/cauc_processor.py

Rodar individualmente:
    python src/collectors/cauc.py
    python src/collectors/cauc.py --uf CE
"""

import sys
import io
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.collectors.municipios import carregar_municipios
from src.utils.bigquery_loader import publish_raw_merge

URL_CAUC_BULK = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "72b5f371-0c35-4613-8076-c99c821a6410/resource/"
    "07af297a-5e59-494a-a88a-55ddfd2f4b01/download/"
    "relatorio-situacao-de-varios-entes---municipios---uf-todas---abrangencia-1.csv"
)

# Configuracao de download resiliente do CSV nacional.
CAUC_DOWNLOAD_MAX_ATTEMPTS = 4
CAUC_DOWNLOAD_BACKOFF_SECONDS = 5.0
CAUC_RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class CaucBulkCsv:
    texto: str
    df_raw: pd.DataFrame
    data_pesquisa: str
    col_ibge: str


# Mapeamento dos codigos de requisito CAUC para nomes semanticos no BigQuery.
# O CSV em disco mantem os codigos originais ("1.1", "1.2" etc.) para que o
# cauc_processor.py legado continue funcionando sem alteracao.
# O rename e aplicado apenas no DataFrame enviado ao BQ.
CAUC_COL_MAP = {
    # Metadados
    "UF":                    "uf",
    "Nome do Ente Federado": "municipio",
    "Código IBGE":           "cod_ibge",
    "Código SIAFI":          "cod_siafi",
    "Região":                "regiao",
    "População":             "populacao",
    "Fonte":                 "fonte",
    # Requisitos
    "1.1":   "req_previdenciaria_rpps",
    "1.2":   "req_fiscal_rfb",
    "1.3":   "req_pgfn",
    "1.4":   "req_fgts",
    "1.5":   "req_trabalhista_tst",
    "2.1.1": "req_lrf_pessoal_exec",
    "2.1.2": "req_lrf_pessoal_leg",
    "3.1.1": "req_siops",
    "3.1.2": "req_siops_demo",
    "3.2.1": "req_siope",
    "3.2.2": "req_siope_demo",
    "3.2.3": "req_siope_compl",
    "3.2.4": "req_siope_obs",
    "3.3":   "req_siga",
    "3.4.1": "req_siconv_pc",
    "3.4.2": "req_siconv_debitos",
    "3.5":   "req_cadin",
    "3.6":   "req_tcu",
    "3.7":   "req_cgu",
    "4.1":   "req_sistn_divida",
    "4.2":   "req_sistn_garantias",
    "5.1":   "req_siconfi_rreo",
    "5.2":   "req_siconfi_rgf",
    "5.3":   "req_siconfi_balanco",
    "5.4":   "req_siconfi_dca",
    "5.5":   "req_siconfi_pcasp",
    "5.6":   "req_siconfi_dcasp",
    "5.7":   "req_siconfi_mcasp",
}


def _decode_cauc_csv(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("iso-8859-1")


def _parse_cauc_bulk_csv(texto: str) -> CaucBulkCsv:
    df_raw = pd.read_csv(
        io.StringIO(texto), sep=";", skiprows=3, dtype=str, na_filter=False
    )

    linhas = texto.split("\n")
    data_pesquisa = linhas[0].strip().replace('"', '').replace("Data da Pesquisa: ", "")

    col_ibge = next((c for c in df_raw.columns if "ibge" in c.lower()), None)
    if not col_ibge:
        raise ValueError(f"Coluna IBGE nao encontrada. Colunas: {list(df_raw.columns)}")

    return CaucBulkCsv(
        texto=texto,
        df_raw=df_raw,
        data_pesquisa=data_pesquisa,
        col_ibge=col_ibge,
    )


def _is_retriable_download_error(exc: Exception) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True

    if isinstance(exc, requests.HTTPError):
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        return status_code in CAUC_RETRIABLE_STATUS_CODES

    return False


def _download_cauc_bulk_content(
    *,
    max_attempts: int = CAUC_DOWNLOAD_MAX_ATTEMPTS,
    backoff_seconds: float = CAUC_DOWNLOAD_BACKOFF_SECONDS,
) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(
                URL_CAUC_BULK,
                headers=headers,
                verify=False,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= max_attempts or not _is_retriable_download_error(exc):
                raise

            wait_seconds = backoff_seconds * (2 ** (attempt - 1))
            print(
                "  Aviso: falha temporaria ao baixar CAUC "
                f"(tentativa {attempt}/{max_attempts}): {exc}"
            )
            print(f"  Nova tentativa em {wait_seconds:.0f}s...")
            time.sleep(wait_seconds)

    if last_error:
        raise last_error
    raise RuntimeError("Falha ao baixar CSV nacional do CAUC.")


def download_cauc_bulk_csv(
    *,
    max_attempts: int = CAUC_DOWNLOAD_MAX_ATTEMPTS,
    backoff_seconds: float = CAUC_DOWNLOAD_BACKOFF_SECONDS,
) -> CaucBulkCsv:
    print(f"\n  Baixando CSV nacional do CKAN...")
    content = _download_cauc_bulk_content(
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
    )
    bulk_csv = _parse_cauc_bulk_csv(_decode_cauc_csv(content))
    print(f"  OK {len(bulk_csv.df_raw)} municipios no Brasil")
    print(f"  Data da pesquisa: {bulk_csv.data_pesquisa}")
    return bulk_csv


def run(uf: str = "PB", bulk_csv: CaucBulkCsv | None = None) -> pd.DataFrame:
    """
    Baixa o CSV nacional do CAUC, filtra municípios da UF e publica no BQ.

    Retorna o DataFrame bruto filtrado (com colunas originais do CKAN).
    """
    uf    = uf.upper()
    hoje  = date.today().strftime("%Y-%m-%d")

    print("=" * 70)
    print(f"  Coletor CAUC — CKAN Tesouro Transparente")
    print(f"  UF: {uf} | Execução: {hoje}")
    print("=" * 70)

    municipios_df = carregar_municipios(uf=uf, prefer_local=True, persist_local=True)
    ibges_uf      = set(municipios_df["cod_ibge"].tolist())

    if bulk_csv is None:
        bulk_csv = download_cauc_bulk_csv()

    df_raw = bulk_csv.df_raw
    cod_ibge = df_raw[bulk_csv.col_ibge].astype(str)
    df_uf = df_raw[cod_ibge.isin(ibges_uf)].copy()
    df_uf["data_pesquisa"] = bulk_csv.data_pesquisa
    df_uf["data_coleta"]   = hoje

    print(f"  Municípios {uf} encontrados: {len(df_uf)}")

    print("=" * 70)

    # Publicacao segura no BigQuery com nomes semanticos.
    df_bq = df_uf.rename(columns=CAUC_COL_MAP)
    publish_raw_merge(
        df_bq,
        table="cauc",
        uf=uf,
        key_cols=["uf", "cod_ibge", "data_coleta", "data_pesquisa"],
    )

    return df_uf   # retorna com colunas originais do CKAN


if __name__ == "__main__":
    args   = sys.argv[1:]
    uf_arg = "PB"
    for i, arg in enumerate(args):
        if arg == "--uf" and i + 1 < len(args):
            uf_arg = args[i + 1]
        elif arg.startswith("--uf="):
            uf_arg = arg.split("=", 1)[1]
    run(uf=uf_arg)

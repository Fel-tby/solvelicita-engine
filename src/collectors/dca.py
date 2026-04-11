"""
Coletor DCA (Declaracao de Contas Anuais) - SolveLicita
Responsabilidade: buscar Balanço Patrimonial (Anexo I-AB) e Balanço de
Receitas (Anexo I-C) para os municipios da UF e publicar dados brutos no BQ.

O cálculo de Scaixa e Autonomia é feito por:
    src/processors/dca_processor.py

2025 excluído do ANOS_FULL: prazo de envio da DCA é abril/2026.
Atualizar ANOS_FULL para incluir 2025 a partir de maio/2026.
ANOS_INCREMENTAL é dinâmico — a API retorna vazio para anos sem dados.

Rodar individualmente:
    python src/collectors/dca.py
    python src/collectors/dca.py --mode incremental --uf CE
"""

import sys
import logging
import time
import httpx
import pandas as pd
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.paths import get_paths
from utils.bigquery_loader import publish_raw_merge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

API_BASE = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca"

ANOS_FULL = [2020, 2021, 2022, 2023, 2024]

# Dinâmico: tenta os dois últimos exercícios. A API retorna [] para anos sem dados.
_ano_ref         = date.today().year
ANOS_INCREMENTAL = [_ano_ref - 1, _ano_ref]

ANEXO_BP  = "DCA-Anexo I-AB"
ANEXO_REC = "DCA-Anexo I-C"
DELAY     = 0.4
MAX_RETRY = 3

CONTA_ATIVO_FIN      = "Ativo Financeiro"
CONTA_PASSIVO_FIN    = "Passivo Financeiro"
CONTA_REC_TRIBUTARIA = "1.1.0.0.00.0.0 - Impostos, Taxas e Contribuições de Melhoria"
CONTA_REC_CORRENTE   = "RECEITAS (EXCETO INTRA-ORÇAMENTÁRIAS) (I)"
COLUNA_REALIZADO     = "Receitas Realizadas"


def fetch_dca(id_ente: str, ano: int, anexo: str, client: httpx.Client) -> list[dict]:
    params = {"an_exercicio": ano, "no_anexo": anexo, "id_ente": id_ente}
    for tentativa in range(1, MAX_RETRY + 1):
        try:
            r = client.get(API_BASE, params=params, timeout=30)
            r.raise_for_status()
            return r.json().get("items", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            log.warning(f"  HTTP {e.response.status_code} | {id_ente} {ano} | tentativa {tentativa}")
        except Exception as e:
            log.warning(f"  Erro: {e} | {id_ente} {ano} | tentativa {tentativa}")
        time.sleep(DELAY * tentativa)
    return []


def explorar_campos(id_ente: str, ano: int, anexo: str, client: httpx.Client) -> None:
    """Revalida mapeamento de campos após atualizações da API. Uso pontual."""
    items = fetch_dca(id_ente, ano, anexo, client)
    if not items:
        log.warning(f"Nenhum dado: {id_ente} {ano} {anexo}")
        return
    log.info(f"\n{'='*60}")
    log.info(f"EXPLORAÇÃO: {anexo} | ente {id_ente} | ano {ano}")
    log.info(f"Campos: {list(items[0].keys())}")
    log.info(f"Valores únicos de 'coluna': {sorted({i.get('coluna','') for i in items})}")
    log.info("Contas únicas:")
    for c in sorted({i.get('conta', '') for i in items}):
        log.info(f"  {c}")
    log.info(f"{'='*60}\n")


def extrair_bp(items: list[dict], nome_conta: str) -> float | None:
    nome_lower = nome_conta.lower().strip()
    for item in items:
        if str(item.get("conta", "")).lower().strip() == nome_lower:
            try:
                return float(item.get("valor") or 0)
            except (ValueError, TypeError):
                return None
    return None


def extrair_receita(items: list[dict], nome_conta: str) -> float | None:
    nome_lower = nome_conta.lower().strip()
    for item in items:
        conta_ok  = str(item.get("conta", "")).lower().strip() == nome_lower
        coluna_ok = str(item.get("coluna", "")).strip() == COLUNA_REALIZADO
        if conta_ok and coluna_ok:
            try:
                return float(item.get("valor") or 0)
            except (ValueError, TypeError):
                return None
    for item in items:
        if str(item.get("conta", "")).lower().strip() == nome_lower:
            try:
                return float(item.get("valor") or 0)
            except (ValueError, TypeError):
                return None
    return None


def coletar_dca(
    municipios: pd.DataFrame,
    anos:       list[int],
    explorar:   bool = False,
) -> pd.DataFrame:
    """
    Coleta DCA para os municípios e anos informados.
    Retorna DataFrame com valores brutos — sem cálculo de indicadores.
    """
    registros    = []
    n_registros  = len(municipios) * len(anos)
    processados  = 0

    with httpx.Client(follow_redirects=True) as client:
        if explorar:
            explorar_campos("2504009", 2024, ANEXO_BP,  client)
            explorar_campos("2504009", 2024, ANEXO_REC, client)
            return pd.DataFrame()

        for _, mun in municipios.iterrows():
            cod  = str(mun["cod_ibge"])
            nome = mun["ente"]
            pop  = mun.get("populacao", 0)

            for ano in anos:
                processados += 1
                log.info(f"[{processados:4d}/{n_registros}] {nome} ({cod}) — {ano}")

                items_bp  = fetch_dca(cod, ano, ANEXO_BP, client)
                time.sleep(DELAY)

                ativo_fin = passivo_fin = None
                if items_bp:
                    ativo_fin   = extrair_bp(items_bp, CONTA_ATIVO_FIN)
                    passivo_fin = extrair_bp(items_bp, CONTA_PASSIVO_FIN)

                items_rec = fetch_dca(cod, ano, ANEXO_REC, client)
                time.sleep(DELAY)

                rec_trib = rec_corr = None
                if items_rec:
                    rec_trib = extrair_receita(items_rec, CONTA_REC_TRIBUTARIA)
                    rec_corr = extrair_receita(items_rec, CONTA_REC_CORRENTE)

                registros.append({
                    "cod_ibge"          : cod,
                    "ente"              : nome,
                    "populacao"         : pop,
                    "ano"               : ano,
                    "ativo_financeiro"  : ativo_fin,
                    "passivo_financeiro": passivo_fin,
                    "rec_tributaria"    : rec_trib,
                    "rec_corrente"      : rec_corr,
                    "bp_disponivel"     : bool(items_bp),
                    "rec_disponivel"    : bool(items_rec),
                })

    return pd.DataFrame(registros)


def run(
    mode:       str                  = "full",
    uf:         str                  = "PB",
    municipios: pd.DataFrame | None  = None,
) -> pd.DataFrame:
    """
    Executa a coleta DCA e publica o bruto diretamente no BigQuery.

    Parâmetros
    ----------
    mode       : "full" — coleta ANOS_FULL completo
                 "incremental" — coleta ANOS_INCREMENTAL e merge no raw existente
    uf         : sigla do estado (default "PB")
    municipios : DataFrame de municípios. Se None, lê do CSV processado da UF.

    Retorna o DataFrame bruto coletado na execucao.
    """
    uf    = uf.upper()
    paths = get_paths(uf)

    if municipios is None:
        path_mun = paths["processed"] / f"municipios_{uf.lower()}_tabela.csv"
        if not path_mun.exists():
            raise FileNotFoundError(
                f"Tabela de municípios não encontrada: {path_mun}\n"
                f"Execute primeiro: python src/collectors/municipios.py --uf {uf}"
            )
        municipios = pd.read_csv(path_mun, dtype={"cod_ibge": str})
        log.info(f"  {len(municipios)} municípios carregados ({uf})")

    anos = ANOS_FULL if mode == "full" else ANOS_INCREMENTAL
    log.info(f"  Modo DCA: {mode.upper()} | Anos: {anos} | UF: {uf}")

    n_reg = len(municipios) * len(anos)
    log.info(
        f"\nIniciando coleta DCA "
        f"({n_reg} registros | {n_reg * 2} requisições | "
        f"~{n_reg * 2 * DELAY / 60:.0f} min)..."
    )

    df_novo = coletar_dca(municipios, anos)

    log.info(
        f"  ✅ Coleta concluida: {len(df_novo)} linhas "
        f"({df_novo['ano'].nunique()} anos)"
    )

    publish_raw_merge(
        df_novo,
        table="dca",
        uf=uf,
        key_cols=["uf", "cod_ibge", "ano"],
    )
    return df_novo


if __name__ == "__main__":
    args      = sys.argv[1:]
    mode_arg  = "full"
    uf_arg    = "PB"
    for i, arg in enumerate(args):
        if arg == "--mode" and i + 1 < len(args):
            mode_arg = args[i + 1]
        elif arg.startswith("--mode="):
            mode_arg = arg.split("=", 1)[1]
        elif arg == "--uf" and i + 1 < len(args):
            uf_arg = args[i + 1]
        elif arg.startswith("--uf="):
            uf_arg = arg.split("=", 1)[1]
    run(mode=mode_arg, uf=uf_arg)

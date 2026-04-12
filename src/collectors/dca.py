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
CONTA_ATIVO_FIN_KEY = CONTA_ATIVO_FIN.lower().strip()
CONTA_PASSIVO_FIN_KEY = CONTA_PASSIVO_FIN.lower().strip()


class Progresso:
    """Contador simples com exibicao em linha unica para a coleta DCA."""

    def __init__(self, total: int, label: str = ""):
        self.total = total
        self.label = label
        self.feitas = 0
        self.erros = 0
        self.vazias = 0
        self.registros = 0
        self._inicio = time.time()

    def tick(self, n_registros: int = 0, erro: bool = False, vazia: bool = False) -> None:
        self.feitas += 1
        self.registros += n_registros
        if erro:
            self.erros += 1
        if vazia:
            self.vazias += 1
        self._render()

    def _render(self) -> None:
        elapsed = time.time() - self._inicio
        pct = self.feitas / self.total * 100 if self.total else 100
        bar_len = 30
        filled = int(bar_len * self.feitas / self.total) if self.total else bar_len
        bar = "=" * filled + "-" * (bar_len - filled)
        eta = (elapsed / self.feitas * (self.total - self.feitas)) if self.feitas else 0
        eta_str = f"{eta/60:.0f}min" if eta >= 60 else f"{eta:.0f}s"
        line = (
            f"\r  {self.label} [{bar}] "
            f"{self.feitas:,}/{self.total:,} ({pct:.1f}%) | "
            f"regs: {self.registros:,} | "
            f"erros: {self.erros} | "
            f"ETA: {eta_str} "
        )
        sys.stdout.write(line)
        sys.stdout.flush()

    def finalizar(self) -> None:
        elapsed = time.time() - self._inicio
        sys.stdout.write("\n")
        sys.stdout.flush()
        print(f"  ✅ {self.label}: {self.registros:,} registros em {elapsed/60:.1f} min")


def _normalizar_texto(valor: object) -> str:
    return str(valor or "").strip().lower()


def _to_float(valor: object) -> float | None:
    try:
        return float(valor or 0)
    except (ValueError, TypeError):
        return None


def fetch_dca(id_ente: str, ano: int, anexo: str, client: httpx.Client) -> tuple[list[dict], bool]:
    params = {"an_exercicio": ano, "no_anexo": anexo, "id_ente": id_ente}
    for tentativa in range(1, MAX_RETRY + 1):
        try:
            r = client.get(API_BASE, params=params, timeout=30)
            r.raise_for_status()
            return r.json().get("items", []), True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return [], True
            log.warning(f"  HTTP {e.response.status_code} | {id_ente} {ano} | tentativa {tentativa}")
        except Exception as e:
            log.warning(f"  Erro: {e} | {id_ente} {ano} | tentativa {tentativa}")
        time.sleep(DELAY * tentativa)
    return [], False


def explorar_campos(id_ente: str, ano: int, anexo: str, client: httpx.Client) -> None:
    """Revalida mapeamento de campos após atualizações da API. Uso pontual."""
    items, sucesso = fetch_dca(id_ente, ano, anexo, client)
    if not sucesso:
        log.warning(f"Falha ao consultar: {id_ente} {ano} {anexo}")
        return
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
    nome_lower = _normalizar_texto(nome_conta)
    for item in items:
        if _normalizar_texto(item.get("conta", "")) == nome_lower:
            return _to_float(item.get("valor"))
    return None


def extrair_receita(items: list[dict], nome_conta: str) -> float | None:
    nome_lower = _normalizar_texto(nome_conta)
    fallback = None
    for item in items:
        conta_ok = _normalizar_texto(item.get("conta", "")) == nome_lower
        coluna_ok = str(item.get("coluna", "")).strip() == COLUNA_REALIZADO
        if not conta_ok:
            continue
        valor = _to_float(item.get("valor"))
        if coluna_ok:
            return valor
        if fallback is None:
            fallback = valor
    return fallback


def extrair_metricas_bp(items: list[dict]) -> tuple[float | None, float | None]:
    ativo_fin = None
    passivo_fin = None

    for item in items:
        conta = _normalizar_texto(item.get("conta", ""))
        valor = _to_float(item.get("valor"))
        if conta == CONTA_ATIVO_FIN_KEY:
            ativo_fin = valor
        elif conta == CONTA_PASSIVO_FIN_KEY:
            passivo_fin = valor

    return ativo_fin, passivo_fin


def extrair_metricas_receita(items: list[dict]) -> tuple[float | None, float | None]:
    rec_trib = extrair_receita(items, CONTA_REC_TRIBUTARIA)
    rec_corr = extrair_receita(items, CONTA_REC_CORRENTE)
    return rec_trib, rec_corr


def coletar_dca(
    municipios: pd.DataFrame,
    anos:       list[int],
    explorar:   bool = False,
) -> pd.DataFrame:
    """
    Coleta DCA para os municípios e anos informados.
    Retorna DataFrame com valores brutos — sem cálculo de indicadores.
    """
    registros = []
    n_registros = len(municipios) * len(anos)
    progresso = Progresso(n_registros, "DCA")

    with httpx.Client(follow_redirects=True) as client:
        if explorar:
            explorar_campos("2504009", 2024, ANEXO_BP,  client)
            explorar_campos("2504009", 2024, ANEXO_REC, client)
            return pd.DataFrame()

        for mun in municipios.itertuples(index=False):
            cod = str(mun.cod_ibge)
            nome = mun.ente
            pop = getattr(mun, "populacao", 0)

            for ano in anos:
                items_bp, ok_bp = fetch_dca(cod, ano, ANEXO_BP, client)

                ativo_fin = passivo_fin = None
                if items_bp:
                    ativo_fin, passivo_fin = extrair_metricas_bp(items_bp)

                items_rec, ok_rec = fetch_dca(cod, ano, ANEXO_REC, client)

                rec_trib = rec_corr = None
                if items_rec:
                    rec_trib, rec_corr = extrair_metricas_receita(items_rec)

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

                progresso.tick(
                    n_registros=int(bool(items_bp or items_rec)),
                    erro=(not ok_bp) or (not ok_rec),
                    vazia=(not items_bp) and (not items_rec) and ok_bp and ok_rec,
                )

    progresso.finalizar()
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

    anos = ANOS_FULL if mode == "full" else ANOS_INCREMENTAL
    n_reg = len(municipios) * len(anos)

    print("\n" + "=" * 55)
    print(f"  Coletor DCA - Municipios de {uf}")
    print(f"  Modo: {mode.upper()} | Anos: {anos}")
    print("=" * 55)
    print()
    print(f"  Municipios carregados: {len(municipios)}")
    print(f"  Malha montada       : {n_reg:,} municipio-ano")
    print(f"  Requisicoes         : {n_reg * 2:,}")
    print()

    df_novo = coletar_dca(municipios, anos)

    print()
    print(
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

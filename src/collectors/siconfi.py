"""
Crawler assíncrono para extração de relatórios contábeis do SICONFI.
Gerencia requisições concorrentes aos endpoints RREO e RGF, implementando
semáforos de controle de tráfego e resiliência contra rate limits (429).

Os dados brutos sao publicados diretamente nas tabelas raw do BigQuery.

Rodar individualmente:
    python src/collectors/siconfi.py                    # full PB (2020–hoje)
    python src/collectors/siconfi.py --mode incremental # apenas anos recentes
    python src/collectors/siconfi.py --uf CE            # outro estado, full
    python src/collectors/siconfi.py --mode incremental --uf CE
"""

import asyncio
import httpx
import logging
import pandas as pd
import re
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.paths import get_paths
from src.utils.bigquery_loader import publish_raw_merge
from src.collectors.municipios import carregar_municipios

BASE_URL_SICONFI = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
MAX_CONCORRENCIA = 10
POP_LIMITE_RGF_SEMESTRAL = 50000
BATCH_PUBLICACAO_LINHAS = 100000
DF_QUERY_ID_ENTE = "53"
DF_OUTPUT_COD_IBGE = "5300108"
DF_ENTITY_NAME = "Governo do Distrito Federal"
DF_SCOPE_ESFERA = "E"

ANOS_FULL        = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
ANOS_INCREMENTAL = [date.today().year - 1, date.today().year]

ANEXOS_RREO = ["RREO-Anexo 01", "RREO-Anexo 07"]
ANEXOS_RGF  = ["RGF-Anexo 05"]
DEMONSTRATIVO_RREO = "RREO"
DEMONSTRATIVO_RREO_SIMPLIFICADO = "RREO Simplificado"
DEMONSTRATIVO_RGF = "RGF"
DEMONSTRATIVO_RGF_SIMPLIFICADO = "RGF Simplificado"

_RREO_NOME_MAP = [
    ("relatorio resumido de execucao orcamentaria simplificado", DEMONSTRATIVO_RREO_SIMPLIFICADO),
    ("rreo simplificado", DEMONSTRATIVO_RREO_SIMPLIFICADO),
    ("relatorio resumido de execucao orcamentaria", DEMONSTRATIVO_RREO),
    ("rreo", DEMONSTRATIVO_RREO),
]

_RGF_NOME_MAP = [
    ("relatorio de gestao fiscal simplificado", DEMONSTRATIVO_RGF_SIMPLIFICADO),
    ("rgf simplificado", DEMONSTRATIVO_RGF_SIMPLIFICADO),
    ("relatorio de gestao fiscal", DEMONSTRATIVO_RGF),
    ("rgf", DEMONSTRATIVO_RGF),
]

CHAVE_RREO = [
    "uf", "cod_ibge", "exercicio", "periodo", "anexo",
    "cod_conta", "coluna", "conta", "esfera",
]
CHAVE_RGF  = [
    "uf", "cod_ibge", "exercicio", "periodo", "periodicidade", "anexo",
    "cod_conta", "coluna", "conta", "esfera",
]


def _norm_text(value: str | None) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def _extrato_demonstrativo(item: dict) -> str:
    return str(
        item.get("entregavel")
        or item.get("tipo_relatorio")
        or item.get("demonstrativo")
        or ""
    )


def _identificar_demonstrativo(nome_normalizado: str, mapa: list[tuple[str, str]]) -> str | None:
    for keyword, demonstrativo in mapa:
        if keyword in nome_normalizado:
            return demonstrativo
    return None


def _resolver_demonstrativos_rreo(extrato_items: list[dict]) -> list[str]:
    demos = []
    for item in extrato_items:
        nome = _norm_text(_extrato_demonstrativo(item))
        demonstrativo = _identificar_demonstrativo(nome, _RREO_NOME_MAP)
        if demonstrativo:
            demos.append(demonstrativo)

    ordenados = list(dict.fromkeys(demos))
    return ordenados or [DEMONSTRATIVO_RREO]


def _resolver_planos_rgf(extrato_items: list[dict]) -> list[tuple[str, str]]:
    planos = []
    for item in extrato_items:
        nome = _norm_text(_extrato_demonstrativo(item))
        periodicidade = str(item.get("periodicidade") or "").upper().strip()

        demo = _identificar_demonstrativo(nome, _RGF_NOME_MAP)
        if demo is None:
            continue

        if periodicidade in {"Q", "S"}:
            planos.append((demo, periodicidade))
            continue

        if demo == DEMONSTRATIVO_RGF_SIMPLIFICADO:
            planos.append((demo, "S"))
        else:
            planos.extend([(demo, "Q"), (demo, "S")])

    ordenados = list(dict.fromkeys(planos))
    return ordenados or [(DEMONSTRATIVO_RGF, "Q"), (DEMONSTRATIVO_RGF, "S")]


def _priorizar_demonstrativos_rreo(
    extrato_items: list[dict],
    *,
    populacao: int | None = None,
) -> list[str]:
    encontrados = _resolver_demonstrativos_rreo(extrato_items)
    preferencia = (
        [DEMONSTRATIVO_RREO_SIMPLIFICADO, DEMONSTRATIVO_RREO]
        if populacao is not None and populacao <= POP_LIMITE_RGF_SEMESTRAL
        else [DEMONSTRATIVO_RREO, DEMONSTRATIVO_RREO_SIMPLIFICADO]
    )
    ordenados = [demo for demo in preferencia if demo in encontrados]
    ordenados.extend(demo for demo in encontrados if demo not in ordenados)
    return ordenados or preferencia


def _priorizar_planos_rgf(
    extrato_items: list[dict],
    *,
    populacao: int | None = None,
) -> list[tuple[str, str]]:
    encontrados = _resolver_planos_rgf(extrato_items)
    if populacao is not None and populacao <= POP_LIMITE_RGF_SEMESTRAL:
        preferencia = [
            (DEMONSTRATIVO_RGF_SIMPLIFICADO, "S"),
            (DEMONSTRATIVO_RGF, "S"),
            (DEMONSTRATIVO_RGF_SIMPLIFICADO, "Q"),
            (DEMONSTRATIVO_RGF, "Q"),
        ]
    else:
        preferencia = [
            (DEMONSTRATIVO_RGF, "Q"),
            (DEMONSTRATIVO_RGF_SIMPLIFICADO, "Q"),
            (DEMONSTRATIVO_RGF, "S"),
            (DEMONSTRATIVO_RGF_SIMPLIFICADO, "S"),
        ]

    ordenados = [plano for plano in preferencia if plano in encontrados]
    ordenados.extend(plano for plano in encontrados if plano not in ordenados)
    return ordenados or preferencia


def _periodos_rgf(periodicidade: str) -> range:
    return range(1, 4) if periodicidade == "Q" else range(1, 3)


def _build_entidade_planos(uf: str, df_municipios: pd.DataFrame) -> list[dict]:
    if df_municipios.empty:
        return []

    if uf.upper() == "DF":
        row = df_municipios.iloc[0]
        return [
            {
                "query_id": DF_QUERY_ID_ENTE,
                "output_cod_ibge": DF_OUTPUT_COD_IBGE,
                "populacao": _coerce_populacao(row.get("populacao")),
                "esfera": DF_SCOPE_ESFERA,
                "instituicao_filtro": DF_ENTITY_NAME,
            }
        ]

    planos = []
    for _, row in df_municipios.iterrows():
        cod_ibge = str(row["cod_ibge"]).zfill(7)
        planos.append(
            {
                "query_id": cod_ibge,
                "output_cod_ibge": cod_ibge,
                "populacao": _coerce_populacao(row.get("populacao")),
                "esfera": None,
                "instituicao_filtro": None,
            }
        )
    return planos


def _filtrar_extrato_entidade(
    extrato_items: list[dict],
    instituicao_filtro: str | None,
) -> list[dict]:
    if not instituicao_filtro:
        return extrato_items

    filtrados = [
        item for item in extrato_items
        if str(item.get("instituicao") or "").strip() == instituicao_filtro
    ]
    return filtrados


def _normalizar_registros_entidade(
    registros: list[dict],
    *,
    output_cod_ibge: str,
    populacao: int | None,
) -> list[dict]:
    if not registros:
        return registros

    normalizados = []
    for item in registros:
        row = dict(item)
        row["cod_ibge"] = output_cod_ibge
        if populacao is not None:
            row["populacao"] = populacao
        normalizados.append(row)
    return normalizados


def _montar_tarefas_rreo(
    ano: int,
    id_ente: str,
    extrato_items: list[dict],
    *,
    populacao: int | None = None,
) -> list[tuple]:
    tarefas = []
    for demonstrativo in _priorizar_demonstrativos_rreo(extrato_items, populacao=populacao):
        for periodo in range(6, 0, -1):
            for anexo in ANEXOS_RREO:
                tarefas.append((ano, periodo, id_ente, anexo, None, None, demonstrativo))
    return tarefas


def _montar_tarefas_rgf(
    ano: int,
    id_ente: str,
    extrato_items: list[dict],
    *,
    populacao: int | None = None,
) -> list[tuple]:
    tarefas = []
    for demonstrativo, periodicidade in _priorizar_planos_rgf(extrato_items, populacao=populacao):
        for periodo in reversed(list(_periodos_rgf(periodicidade))):
            for anexo in ANEXOS_RGF:
                tarefas.append((ano, periodo, id_ente, anexo, "E", periodicidade, demonstrativo))
    return tarefas


class Progresso:
    """Contador thread-safe com exibição em linha única."""

    def __init__(self, total: int, label: str = ""):
        self.total     = total
        self.label     = label
        self.feitas    = 0
        self.erros     = 0
        self.vazias    = 0
        self.registros = 0
        self._lock     = asyncio.Lock()
        self._inicio   = time.time()

    async def tick(self, n_registros: int = 0, erro: bool = False, vazia: bool = False):
        async with self._lock:
            self.feitas    += 1
            self.registros += n_registros
            if erro:
                self.erros  += 1
            if vazia:
                self.vazias += 1
            self._render()

    def _render(self):
        elapsed  = time.time() - self._inicio
        pct      = self.feitas / self.total * 100
        bar_len  = 30
        filled   = int(bar_len * self.feitas / self.total)
        bar      = "#" * filled + "-" * (bar_len - filled)
        eta      = (elapsed / self.feitas * (self.total - self.feitas)) if self.feitas else 0
        eta_str  = f"{eta/60:.0f}min" if eta >= 60 else f"{eta:.0f}s"
        line = (
            f"\r  {self.label} [{bar}] "
            f"{self.feitas:,}/{self.total:,} ({pct:.1f}%) | "
            f"registros: {self.registros:,} | "
            f"erros: {self.erros} | "
            f"ETA: {eta_str} "
        )
        sys.stdout.write(line)
        sys.stdout.flush()

    def finalizar(self):
        elapsed = time.time() - self._inicio
        sys.stdout.write("\n")
        sys.stdout.flush()
        print(f"  OK {self.label}: {self.registros:,} registros em {elapsed/60:.1f} min")


def carregar_base_municipios(uf: str) -> pd.DataFrame:
    print(f"  Carregando municípios de {uf.upper()}...", end=" ")
    try:
        df = carregar_municipios(uf.upper(), prefer_local=True, persist_local=False)
        print(f"{len(df)} encontrados.")
        return df
    except Exception as exc:
        print(f"\n  Erro ao carregar base municipal: {exc}")
        return pd.DataFrame(columns=["cod_ibge", "populacao"])


def _coerce_populacao(value) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


async def fetch_com_retry(
    client:       httpx.AsyncClient,
    url:          str,
    params:       dict,
    pausa_global: asyncio.Event,
    tentativas:   int = 3,
) -> dict | None:
    for tentativa in range(tentativas):
        await pausa_global.wait()
        try:
            resposta = await client.get(url, params=params)
            if resposta.status_code == 429:
                pausa_global.clear()
                await asyncio.sleep(2 ** tentativa)
                pausa_global.set()
                continue
            resposta.raise_for_status()
            return resposta.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (400, 404):
                return None
            await asyncio.sleep(2 ** tentativa)
        except httpx.RequestError:
            await asyncio.sleep(2 ** tentativa)
    return None


async def extrair_assincrono(
    client:       httpx.AsyncClient,
    endpoint:     str,
    ano:          int,
    periodo:      int,
    id_ente:      str,
    anexo:        str,
    semaforo:     asyncio.Semaphore,
    pausa_global: asyncio.Event,
    progresso:    Progresso | None = None,
    poder:        str = None,
    periodicidade: str = None,
    tipo_demonstrativo: str | None = None,
    esfera: str | None = None,
) -> list:
    url    = f"{BASE_URL_SICONFI}/{endpoint}"
    params = {
        "an_exercicio"          : ano,
        "nr_periodo"            : periodo,
        "co_tipo_demonstrativo" : tipo_demonstrativo or endpoint.upper(),
        "no_anexo"              : anexo,
        "id_ente"               : id_ente,
        "offset"                : 0,
        "limit"                 : 5000,
    }
    if poder and endpoint == "rgf":
        params["co_poder"] = poder
    if periodicidade:
        params["in_periodicidade"] = periodicidade
    if esfera:
        params["co_esfera"] = esfera

    todos_registros = []
    offset          = 0
    erro            = False

    async with semaforo:
        while True:
            params["offset"] = offset
            dados = await fetch_com_retry(client, url, params, pausa_global)
            if dados is None:
                erro = True
                break
            if "items" not in dados:
                break
            todos_registros.extend(dados.get("items", []))
            if not dados.get("hasMore", False):
                break
            offset += 5000

    if progresso is not None:
        await progresso.tick(
            n_registros=len(todos_registros),
            erro=erro,
            vazia=(len(todos_registros) == 0 and not erro),
        )
    return todos_registros


async def extrair_extrato_entregas(
    client:       httpx.AsyncClient,
    ano:          int,
    id_ente:      str,
    semaforo:     asyncio.Semaphore,
    pausa_global: asyncio.Event,
    progresso:    Progresso,
) -> list:
    url = f"{BASE_URL_SICONFI}/extrato_entregas"
    params = {
        "id_ente": id_ente,
        "an_referencia": ano,
        "offset": 0,
        "limit": 5000,
    }

    todos_registros = []
    offset = 0
    erro = False

    async with semaforo:
        while True:
            params["offset"] = offset
            dados = await fetch_com_retry(client, url, params, pausa_global)
            if dados is None:
                erro = True
                break
            if "items" not in dados:
                break
            todos_registros.extend(dados.get("items", []))
            if not dados.get("hasMore", False):
                break
            offset += 5000

    if progresso is not None:
        await progresso.tick(
            n_registros=len(todos_registros),
            erro=erro,
            vazia=(len(todos_registros) == 0 and not erro),
        )
    return todos_registros


async def _coletar_rreo_municipio_ano(
    client: httpx.AsyncClient,
    *,
    ano: int,
    id_ente: str,
    extrato_items: list[dict],
    populacao: int | None,
    output_cod_ibge: str,
    esfera: str | None,
    semaforo: asyncio.Semaphore,
    pausa_global: asyncio.Event,
) -> list[dict]:
    tarefas = _montar_tarefas_rreo(ano, id_ente, extrato_items, populacao=populacao)
    atual = None
    registros_periodo: list[dict] = []

    for ano_t, periodo, id_ente_t, anexo, _, __, demonstrativo in tarefas:
        chave = (demonstrativo, periodo)
        if atual is not None and chave != atual:
            if registros_periodo:
                return _normalizar_registros_entidade(
                    registros_periodo,
                    output_cod_ibge=output_cod_ibge,
                    populacao=populacao,
                )
            registros_periodo = []
        atual = chave
        registros = await extrair_assincrono(
            client,
            "rreo",
            ano_t,
            periodo,
            id_ente_t,
            anexo,
            semaforo,
            pausa_global,
            progresso=None,
            tipo_demonstrativo=demonstrativo,
            esfera=esfera,
        )
        if registros:
            registros_periodo.extend(registros)

    return _normalizar_registros_entidade(
        registros_periodo,
        output_cod_ibge=output_cod_ibge,
        populacao=populacao,
    )


async def _coletar_rgf_municipio_ano(
    client: httpx.AsyncClient,
    *,
    ano: int,
    id_ente: str,
    extrato_items: list[dict],
    populacao: int | None,
    output_cod_ibge: str,
    esfera: str | None,
    semaforo: asyncio.Semaphore,
    pausa_global: asyncio.Event,
) -> list[dict]:
    tarefas = _montar_tarefas_rgf(ano, id_ente, extrato_items, populacao=populacao)
    atual = None

    for ano_t, periodo, id_ente_t, anexo, poder, periodicidade, demonstrativo in tarefas:
        chave = (demonstrativo, periodicidade)
        if atual is not None and chave != atual:
            atual = chave
        elif atual is None:
            atual = chave
        registros = await extrair_assincrono(
            client,
            "rgf",
            ano_t,
            periodo,
            id_ente_t,
            anexo,
            semaforo,
            pausa_global,
            progresso=None,
            poder=poder,
            periodicidade=periodicidade,
            tipo_demonstrativo=demonstrativo,
            esfera=esfera,
        )
        if registros:
            return _normalizar_registros_entidade(
                registros,
                output_cod_ibge=output_cod_ibge,
                populacao=populacao,
            )
        atual = chave

    return []


async def _coletar_pacote_municipio_ano(
    client: httpx.AsyncClient,
    *,
    ano: int,
    query_id: str,
    extrato_items: list[dict],
    populacao: int | None,
    output_cod_ibge: str,
    esfera: str | None,
    semaforo: asyncio.Semaphore,
    pausa_global: asyncio.Event,
) -> tuple[list[dict], list[dict]]:
    rreo = await _coletar_rreo_municipio_ano(
        client,
        ano=ano,
        id_ente=query_id,
        extrato_items=extrato_items,
        populacao=populacao,
        output_cod_ibge=output_cod_ibge,
        esfera=esfera,
        semaforo=semaforo,
        pausa_global=pausa_global,
    )
    rgf = await _coletar_rgf_municipio_ano(
        client,
        ano=ano,
        id_ente=query_id,
        extrato_items=extrato_items,
        populacao=populacao,
        output_cod_ibge=output_cod_ibge,
        esfera=esfera,
        semaforo=semaforo,
        pausa_global=pausa_global,
    )
    return rreo, rgf


def _flush_registros_lote(
    registros: list[dict],
    *,
    table: str,
    uf: str,
    key_cols: list[str],
) -> None:
    if not registros:
        return

    df = pd.DataFrame(registros)
    publish_raw_merge(
        df,
        table=table,
        uf=uf,
        key_cols=key_cols,
    )
    registros.clear()


async def orquestrar_coleta(anos: list[int], uf: str) -> None:
    uf_upper     = uf.upper()
    semaforo     = asyncio.Semaphore(MAX_CONCORRENCIA)
    pausa_global = asyncio.Event()
    pausa_global.set()

    inicio = time.time()
    df_municipios = carregar_base_municipios(uf_upper)
    entidades_uf = _build_entidade_planos(uf_upper, df_municipios)
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=15)

    tarefas_extrato_params = [
        (ano, entidade)
        for ano in anos
        for entidade in entidades_uf
    ]
    total_extrato = len(tarefas_extrato_params)

    print(f"\n  Malha montada:")
    print(f"  Extrato              : {total_extrato:,} consultas")

    prog_extrato = Progresso(total_extrato, "EXTRATO")

    async with httpx.AsyncClient(timeout=45.0, limits=limits) as client:
        tarefas_extrato = [
            extrair_extrato_entregas(
                client, ano, entidade["query_id"], semaforo, pausa_global, prog_extrato,
            )
            for (ano, entidade) in tarefas_extrato_params
        ]
        resultados_extrato = await asyncio.gather(*tarefas_extrato)

        planos_coleta = []
        total_rreo_tentativas = 0
        total_rgf_tentativas = 0
        for (ano, entidade), extrato_items in zip(tarefas_extrato_params, resultados_extrato):
            query_id = entidade["query_id"]
            output_cod_ibge = entidade["output_cod_ibge"]
            populacao = entidade["populacao"]
            esfera = entidade["esfera"]
            extrato_filtrado = _filtrar_extrato_entidade(
                extrato_items,
                entidade["instituicao_filtro"],
            )
            tentativas_rreo = _montar_tarefas_rreo(
                ano, query_id, extrato_filtrado, populacao=populacao
            )
            tentativas_rgf = _montar_tarefas_rgf(
                ano, query_id, extrato_filtrado, populacao=populacao
            )
            total_rreo_tentativas += len(tentativas_rreo)
            total_rgf_tentativas += len(tentativas_rgf)
            planos_coleta.append(
                (ano, query_id, output_cod_ibge, extrato_filtrado, populacao, esfera)
            )

        total_planos = len(planos_coleta)
        print(f"  RREO (max tentativas): {total_rreo_tentativas:,}")
        print(f"  RGF  (max tentativas): {total_rgf_tentativas:,}")
        print(f"  Alvos municipio-ano  : {total_planos:,}\n")

        prog_rreo = Progresso(total_planos, "RREO")
        prog_rgf  = Progresso(total_planos, "RGF ")
        buffer_rreo: list[dict] = []
        buffer_rgf: list[dict] = []

        tarefas_coleta = [
            _coletar_pacote_municipio_ano(
                client,
                ano=ano,
                query_id=query_id,
                extrato_items=extrato_items,
                populacao=populacao,
                output_cod_ibge=output_cod_ibge,
                esfera=esfera,
                semaforo=semaforo,
                pausa_global=pausa_global,
            )
            for (ano, query_id, output_cod_ibge, extrato_items, populacao, esfera) in planos_coleta
        ]

        for tarefa in asyncio.as_completed(tarefas_coleta):
            registros_rreo, registros_rgf = await tarefa
            await prog_rreo.tick(
                n_registros=len(registros_rreo),
                erro=False,
                vazia=len(registros_rreo) == 0,
            )
            await prog_rgf.tick(
                n_registros=len(registros_rgf),
                erro=False,
                vazia=len(registros_rgf) == 0,
            )

            if registros_rreo:
                buffer_rreo.extend(registros_rreo)
                if len(buffer_rreo) >= BATCH_PUBLICACAO_LINHAS:
                    _flush_registros_lote(
                        buffer_rreo,
                        table="siconfi_rreo",
                        uf=uf_upper,
                        key_cols=CHAVE_RREO,
                    )

            if registros_rgf:
                buffer_rgf.extend(registros_rgf)
                if len(buffer_rgf) >= BATCH_PUBLICACAO_LINHAS:
                    _flush_registros_lote(
                        buffer_rgf,
                        table="siconfi_rgf",
                        uf=uf_upper,
                        key_cols=CHAVE_RGF,
                    )

    prog_extrato.finalizar()
    prog_rreo.finalizar()
    prog_rgf.finalizar()
    print()

    if buffer_rreo:
        _flush_registros_lote(
            buffer_rreo,
            table="siconfi_rreo",
            uf=uf_upper,
            key_cols=CHAVE_RREO,
        )
    else:
        print("  [WARN] RREO: nenhum dado retornado.")

    if buffer_rgf:
        _flush_registros_lote(
            buffer_rgf,
            table="siconfi_rgf",
            uf=uf_upper,
            key_cols=CHAVE_RGF,
        )
    else:
        print("  [WARN] RGF: nenhum dado retornado.")

    print(f"\n  Total: {(time.time() - inicio) / 60:.1f} minutos.")


def run(mode: str = "full", uf: str = "PB") -> None:
    anos = ANOS_FULL if mode == "full" else ANOS_INCREMENTAL
    print(f"\n{'='*55}")
    print(f"  Crawler SICONFI — Municípios de {uf.upper()}")
    print(f"  Modo: {mode.upper()} | Anos: {anos}")
    print(f"{'='*55}")
    asyncio.run(orquestrar_coleta(anos, uf=uf))


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

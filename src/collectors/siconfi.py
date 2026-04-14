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
import sys
import time
from datetime import date
from pathlib import Path

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.paths import get_paths
from src.utils.bigquery_loader import publish_raw_merge

BASE_URL_SICONFI = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
MAX_CONCORRENCIA = 10

ANOS_FULL        = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
ANOS_INCREMENTAL = [date.today().year - 1, date.today().year]

ANEXOS_RREO = ["RREO-Anexo 01", "RREO-Anexo 07"]
ANEXOS_RGF  = ["RGF-Anexo 05"]

CHAVE_RREO = [
    "uf", "cod_ibge", "exercicio", "periodo", "anexo",
    "cod_conta", "coluna", "conta", "esfera",
]
CHAVE_RGF  = [
    "uf", "cod_ibge", "exercicio", "periodo", "periodicidade", "anexo",
    "cod_conta", "coluna", "conta", "esfera",
]


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
        bar      = "█" * filled + "░" * (bar_len - filled)
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
        print(f"  ✅ {self.label}: {self.registros:,} registros em {elapsed/60:.1f} min")


def obter_municipios(uf: str) -> list:
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf.upper()}/municipios"
    print(f"  Buscando municípios de {uf.upper()} no IBGE...", end=" ")
    try:
        resposta   = httpx.get(url, timeout=15)
        resposta.raise_for_status()
        municipios = [str(mun["id"]) for mun in resposta.json()]
        print(f"{len(municipios)} encontrados.")
        return municipios
    except Exception as e:
        print(f"\n  Erro ao buscar IBGE: {e}")
        return []


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
    progresso:    Progresso,
    poder:        str = None,
    periodicidade: str = None,
) -> list:
    url    = f"{BASE_URL_SICONFI}/{endpoint}"
    params = {
        "an_exercicio"          : ano,
        "nr_periodo"            : periodo,
        "co_tipo_demonstrativo" : endpoint.upper(),
        "no_anexo"              : anexo,
        "id_ente"               : id_ente,
        "offset"                : 0,
        "limit"                 : 5000,
    }
    if poder and endpoint == "rgf":
        params["co_poder"] = poder
    if periodicidade:
        params["in_periodicidade"] = periodicidade

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

    await progresso.tick(
        n_registros=len(todos_registros),
        erro=erro,
        vazia=(len(todos_registros) == 0 and not erro),
    )
    return todos_registros


async def orquestrar_coleta(anos: list[int], uf: str) -> None:
    uf_upper     = uf.upper()
    uf_lower     = uf.lower()
    semaforo     = asyncio.Semaphore(MAX_CONCORRENCIA)
    pausa_global = asyncio.Event()
    pausa_global.set()

    inicio        = time.time()
    municipios_uf = obter_municipios(uf_upper)
    limits        = httpx.Limits(max_keepalive_connections=10, max_connections=15)

    tarefas_rreo_params = []
    tarefas_rgf_params  = []

    for ano in anos:
        for id_ente in municipios_uf:
            for periodo in range(1, 7):
                for anexo in ANEXOS_RREO:
                    tarefas_rreo_params.append((ano, periodo, id_ente, anexo, None, None))
            for periodo in range(1, 4):
                for anexo in ANEXOS_RGF:
                    tarefas_rgf_params.append((ano, periodo, id_ente, anexo, "E", "Q"))
            for periodo in range(1, 3):
                for anexo in ANEXOS_RGF:
                    tarefas_rgf_params.append((ano, periodo, id_ente, anexo, "E", "S"))

    total_rreo = len(tarefas_rreo_params)
    total_rgf  = len(tarefas_rgf_params)

    print(f"\n  Malha montada:")
    print(f"  RREO : {total_rreo:,} requisições")
    print(f"  RGF  : {total_rgf:,} requisições")
    print(f"  Total: {total_rreo + total_rgf:,} requisições\n")

    prog_rreo = Progresso(total_rreo, "RREO")
    prog_rgf  = Progresso(total_rgf,  "RGF ")

    async with httpx.AsyncClient(timeout=45.0, limits=limits) as client:
        tarefas_rreo = [
            extrair_assincrono(
                client, "rreo", ano, periodo, id_ente, anexo,
                semaforo, pausa_global, prog_rreo,
            )
            for (ano, periodo, id_ente, anexo, _, __) in tarefas_rreo_params
        ]
        tarefas_rgf = [
            extrair_assincrono(
                client, "rgf", ano, periodo, id_ente, anexo,
                semaforo, pausa_global, prog_rgf,
                poder=poder, periodicidade=periodicidade,
            )
            for (ano, periodo, id_ente, anexo, poder, periodicidade) in tarefas_rgf_params
        ]
        resultados_rreo, resultados_rgf = await asyncio.gather(
            asyncio.gather(*tarefas_rreo),
            asyncio.gather(*tarefas_rgf),
        )

    prog_rreo.finalizar()
    prog_rgf.finalizar()
    print()

    registros_rreo = [item for sub in resultados_rreo if sub for item in sub]
    registros_rgf  = [item for sub in resultados_rgf  if sub for item in sub]

    if registros_rreo:
        df_rreo = pd.DataFrame(registros_rreo)
        publish_raw_merge(
            df_rreo,
            table="siconfi_rreo",
            uf=uf_upper,
            key_cols=CHAVE_RREO,
        )
    else:
        print("  [WARN] RREO: nenhum dado retornado.")

    if registros_rgf:
        df_rgf = pd.DataFrame(registros_rgf)
        publish_raw_merge(
            df_rgf,
            table="siconfi_rgf",
            uf=uf_upper,
            key_cols=CHAVE_RGF,
        )
    else:
        print("  [WARN] RGF: nenhum dado retornado.")

    print(f"\n  ⏱  Total: {(time.time() - inicio) / 60:.1f} minutos.")


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

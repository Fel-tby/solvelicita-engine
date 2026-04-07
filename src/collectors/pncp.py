"""
Coletor PNCP — Licitações por UF (Lei 14.133/2021).
Responsabilidade: coletar registros paginados por modalidade/mês e
salvar o JSONL de checkpoint incremental de forma assíncrona.

A consolidação do JSONL para carga bruta no BigQuery é feita ao final
da coleta, preservando o contrato consumido por dbt/models/staging/stg_pncp.sql.

Rodar individualmente:
    python src/collectors/pncp.py                      # full (desde 2025-01-01)
    python src/collectors/pncp.py --mode incremental   # apenas últimos 2 meses
    python src/collectors/pncp.py --uf CE              # outro estado, full
    python src/collectors/pncp.py --mode incremental --uf CE
"""

import sys
import json
import time
import asyncio
import httpx
import logging
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
from calendar import monthrange

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.paths import get_paths
from utils.bigquery_loader import upload_raw

BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

# Reduzido para 2025-01-01 para maior performance
DATA_INICIO_FULL       = date(2025, 1, 1)
JANELA_INCREMENTAL_DIAS = 60

MODALIDADES = {
    1 : "Leilão Eletrônico",
    2 : "Diálogo Competitivo",
    3 : "Concurso",
    4 : "Concorrência Eletrônica",
    5 : "Concorrência Presencial",
    6 : "Pregão Eletrônico",
    7 : "Pregão Presencial",
    8 : "Dispensa de Licitação",
    9 : "Inexigibilidade",
    10: "Manifestação de Interesse",
    11: "Pré-qualificação",
    12: "Credenciamento",
    13: "Leilão Presencial",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept"    : "application/json",
}

TAMANHO_PAGINA    = 50
MAX_CONCORRENCIA  = 5
BACKOFF_429       = 60
MAX_RETRIES       = 6


class Progresso:
    def __init__(self, total: int):
        self.total     = total
        self.feitas    = 0
        self.erros     = 0
        self.vazios    = 0
        self.registros = 0
        self._lock     = asyncio.Lock()
        self._inicio   = time.time()

    async def tick(self, n_registros: int = 0, erro: bool = False, vazio: bool = False):
        async with self._lock:
            self.feitas    += 1
            self.registros += n_registros
            if erro:
                self.erros  += 1
            if vazio:
                self.vazios += 1
            self._render()

    def _render(self):
        elapsed  = time.time() - self._inicio
        pct      = self.feitas / self.total * 100
        bar_len  = 30
        filled   = int(bar_len * self.feitas / self.total)
        bar      = "=" * filled + "-" * (bar_len - filled)
        eta      = (elapsed / self.feitas * (self.total - self.feitas)) if self.feitas else 0
        eta_str  = f"{eta/60:.0f}min" if eta >= 60 else f"{eta:.0f}s"
        line = (
            f"\r  [{bar}] "
            f"{self.feitas:,}/{self.total:,} ({pct:.1f}%) | "
            f"regs: {self.registros:,} | "
            f"erros: {self.erros} | "
            f"ETA: {eta_str} "
        )
        sys.stdout.write(line)
        sys.stdout.flush()

    def finalizar(self):
        elapsed = time.time() - self._inicio
        sys.stdout.write("\n")
        sys.stdout.flush()
        print(f"  ✅ Concluído: {self.registros:,} registros em {elapsed/60:.1f} min")


def gerar_meses(inicio: date, fim: date) -> list[tuple[date, date]]:
    meses = []
    ano, mes = inicio.year, inicio.month
    while date(ano, mes, 1) <= fim:
        ultimo_dia = monthrange(ano, mes)[1]
        fim_mes    = min(date(ano, mes, ultimo_dia), fim)
        meses.append((date(ano, mes, 1), fim_mes))
        mes += 1
        if mes > 12:
            mes  = 1
            ano += 1
    return meses


async def fetch_com_backoff(
    client: httpx.AsyncClient,
    params: dict,
    pausa_global: asyncio.Event
) -> dict | None:
    for t in range(1, MAX_RETRIES + 1):
        await pausa_global.wait()
        try:
            r = await client.get(BASE_URL, params=params)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 204:
                return {"data": [], "totalRegistros": 0, "totalPaginas": 0, "empty": True}
            if r.status_code == 429:
                pausa_global.clear()
                espera = BACKOFF_429 * t
                print(f"\n  [WARNING] 429 Rate Limit. Pausando por {espera}s...")
                await asyncio.sleep(espera)
                pausa_global.set()
                continue
            if r.status_code in (500, 502, 503, 504):
                await asyncio.sleep(15 * t)
                continue
            print(f"\n  [ERROR] HTTP {r.status_code}: {r.text[:120]}")
            return None
        except httpx.TimeoutException:
            await asyncio.sleep(10 * t)
        except httpx.RequestError:
            await asyncio.sleep(20 * t)
    return None


async def coletar_bloco_async(
    client:       httpx.AsyncClient,
    modalidade:   int,
    data_ini:     date,
    data_fim:     date,
    uf:           str,
    semaforo:     asyncio.Semaphore,
    pausa_global: asyncio.Event,
) -> tuple[list, bool]:
    params_base = {
        "dataInicial"                  : data_ini.strftime("%Y%m%d"),
        "dataFinal"                    : data_fim.strftime("%Y%m%d"),
        "codigoModalidadeContratacao"  : modalidade,
        "uf"                           : uf.upper(),
        "tamanhoPagina"                : TAMANHO_PAGINA,
        "pagina"                       : 1,
    }
    
    async with semaforo:
        resp = await fetch_com_backoff(client, params_base, pausa_global)
        if resp is None:
            return [], False
        if resp.get("empty") or not resp.get("data"):
            return [], True

        registros   = list(resp["data"])
        total_pags  = resp.get("totalPaginas", 1)

        for pag in range(2, total_pags + 1):
            # Pequeno delay para não sobrecarregar em paginações profundas
            await asyncio.sleep(0.5)
            resp_pag = await fetch_com_backoff(client, {**params_base, "pagina": pag}, pausa_global)
            if resp_pag and resp_pag.get("data"):
                registros.extend(resp_pag["data"])

        return registros, True


async def worker_bloco(
    client:       httpx.AsyncClient,
    cod_mod:      int,
    nome_mod:     str,
    data_ini:     date,
    data_fim:     date,
    uf:           str,
    semaforo:     asyncio.Semaphore,
    pausa_global: asyncio.Event,
    progresso:    Progresso,
    file_lock:    asyncio.Lock,
    json_path:    Path
) -> None:
    chave = f"{cod_mod}_{data_ini.strftime('%Y-%m')}"
    meta = {
        "_chave"          : chave,
        "_modalidade"     : cod_mod,
        "_modalidade_nome": nome_mod,
        "_mes"            : data_ini.strftime("%Y-%m"),
        "_uf"             : uf,
    }

    registros, sucesso = await coletar_bloco_async(
        client, cod_mod, data_ini, data_fim, uf, semaforo, pausa_global
    )

    if not sucesso:
        await progresso.tick(erro=True)
        return

    linhas = []
    if registros:
        for rec in registros:
            rec.update(meta)
            linhas.append(json.dumps(rec, ensure_ascii=False) + "\n")
    else:
        linhas.append(json.dumps({**meta, "_sem_dados": True}, ensure_ascii=False) + "\n")

    # Salva no arquivo de forma thread/coroutine-safe
    async with file_lock:
        with open(json_path, "a", encoding="utf-8") as fj:
            fj.writelines(linhas)

    await progresso.tick(n_registros=len(registros), vazio=not registros)


async def orquestrar_coleta(
    uf: str,
    meses: list[tuple[date, date]],
    json_path: Path,
    chaves_feitas: set[str]
) -> None:
    semaforo     = asyncio.Semaphore(MAX_CONCORRENCIA)
    pausa_global = asyncio.Event()
    pausa_global.set()
    file_lock    = asyncio.Lock()
    limits       = httpx.Limits(max_keepalive_connections=10, max_connections=MAX_CONCORRENCIA + 5)

    tarefas_params = []
    for cod_mod, nome_mod in MODALIDADES.items():
        for data_ini, data_fim_bloco in meses:
            chave = f"{cod_mod}_{data_ini.strftime('%Y-%m')}"
            if chave not in chaves_feitas:
                tarefas_params.append((cod_mod, nome_mod, data_ini, data_fim_bloco))

    total_blocos = len(tarefas_params)
    if total_blocos == 0:
        print("  Todos os blocos já foram coletados!")
        return

    print(f"  Iniciando extração assíncrona de {total_blocos} blocos pendentes...\n")
    progresso = Progresso(total_blocos)

    async with httpx.AsyncClient(headers=HEADERS, timeout=45.0, limits=limits) as client:
        tarefas = [
            worker_bloco(
                client, cod_mod, nome_mod, data_ini, data_fim, uf,
                semaforo, pausa_global, progresso, file_lock, json_path
            )
            for (cod_mod, nome_mod, data_ini, data_fim) in tarefas_params
        ]
        await asyncio.gather(*tarefas)

    progresso.finalizar()


def _consolidar_jsonl_para_raw(json_path: Path, uf: str) -> pd.DataFrame:
    """
    Consolida o JSONL do PNCP em DataFrame pronto para upload na camada raw.

    O objetivo aqui e preservar o payload consumido por stg_pncp, ajustando
    apenas uf e mes para o formato esperado no BigQuery.
    """
    if not json_path.exists():
        return pd.DataFrame()

    linhas = []
    with open(json_path, "r", encoding="utf-8") as fj:
        for linha in fj:
            try:
                obj = json.loads(linha)
            except Exception:
                continue
            if obj.get("_sem_dados"):
                continue
            linhas.append(obj)

    if not linhas:
        return pd.DataFrame()

    df = pd.DataFrame(linhas)

    if "_uf" in df.columns:
        df["uf"] = df["_uf"].fillna(uf.upper())
        df.drop(columns=["_uf"], inplace=True)
    else:
        df["uf"] = uf.upper()

    if "_mes" in df.columns:
        df["mes"] = (
            pd.to_datetime(df["_mes"].astype(str) + "-01", errors="coerce")
            .dt.month
            .astype("Int64")
        )
        df.drop(columns=["_mes"], inplace=True)
    elif "dataPublicacaoPncp" in df.columns:
        df["mes"] = (
            pd.to_datetime(df["dataPublicacaoPncp"], errors="coerce")
            .dt.month
            .astype("Int64")
        )

    if "dataAtualizacaoGlobal" not in df.columns and "dataAtualizacao" in df.columns:
        df["dataAtualizacaoGlobal"] = df["dataAtualizacao"]

    return df


def _upload_jsonl_para_bq(json_path: Path, uf: str) -> None:
    df = _consolidar_jsonl_para_raw(json_path, uf)
    if df.empty:
        print("  [BQ] Aviso: nenhum registro PNCP valido para upload.")
        return

    upload_raw(df, table="pncp", uf=uf, write_mode="append")


def run(mode: str = "full", uf: str = "PB") -> None:
    """
    Executa a coleta PNCP e salva o JSONL de checkpoint.

    Parâmetros
    ----------
    mode : "full"        — coleta desde DATA_INICIO_FULL (2025-01-01).
                           Se o JSONL já existir, apaga e reinicia do zero.
           "incremental" — coleta apenas os últimos JANELA_INCREMENTAL_DIAS dias.
                           Usa o checkpoint JSONL existente (pula blocos já feitos).
    uf   : sigla do estado (default "PB")
    """
    uf    = uf.upper()
    hoje  = date.today()
    paths = get_paths(uf)

    # Primário — nova estrutura UF subfolder
    snap_jsonl_novo = paths["raw_pncp"] / f"pncp_parcial_{uf.lower()}.jsonl"

    if mode == "full":
        data_inicio = DATA_INICIO_FULL
        if snap_jsonl_novo.exists():
            snap_jsonl_novo.unlink()
            print(f"  [INFO] {snap_jsonl_novo.name} removido — coleta full reiniciada.")
    else:
        data_inicio = hoje - timedelta(days=JANELA_INCREMENTAL_DIAS)

    t0    = time.time()
    meses = gerar_meses(data_inicio, hoje)

    print("=" * 65)
    print(f"  PNCP Collector Async - Licitacoes {uf} (Lei 14.133/2021)")
    print(f"  Modo   : {mode.upper()}")
    print(f"  Range  : {data_inicio} -> {hoje}")
    print(f"  Janela : {len(meses)} meses x {len(MODALIDADES)} modalidades")
    print("=" * 65)

    # Checkpoint: blocos já coletados (lê do primário)
    chaves_feitas: set[str] = set()
    if snap_jsonl_novo.exists():
        with open(snap_jsonl_novo, "r", encoding="utf-8") as fj:
            for linha in fj:
                try:
                    obj = json.loads(linha)
                    if obj.get("_chave"):
                        chaves_feitas.add(obj["_chave"])
                except Exception:
                    pass
        if chaves_feitas:
            print(f"  [INFO] {len(chaves_feitas)} blocos já no JSONL — serão ignorados.")

    # Executa loop assíncrono
    asyncio.run(orquestrar_coleta(uf, meses, snap_jsonl_novo, chaves_feitas))

    elapsed = time.time() - t0
    print("  [BQ] Consolidando JSONL e enviando para raw.pncp...")
    _upload_jsonl_para_bq(snap_jsonl_novo, uf)
    print(f"\n[SUCCESS] Coleta concluída em {elapsed / 60:.1f} min")
    print(f"  JSONL primário  : {snap_jsonl_novo.name}")
    print(f"  Próximo passo   : python pipeline.py --steps dbt,process,score")
    print("=" * 65)


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

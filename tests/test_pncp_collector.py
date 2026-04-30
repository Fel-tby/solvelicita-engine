from datetime import date
import asyncio

from src.collectors import pncp


def test_subtrair_meses_preserva_dia_quando_possivel():
    assert pncp.subtrair_meses(date(2026, 4, 28), 6) == date(2025, 10, 28)


def test_subtrair_meses_ajusta_fim_de_mes():
    assert pncp.subtrair_meses(date(2026, 8, 31), 6) == date(2026, 2, 28)


def test_gerar_meses_preserva_inicio_parcial_da_janela():
    meses = pncp.gerar_meses(date(2025, 10, 28), date(2026, 4, 28))

    assert meses[0] == (date(2025, 10, 28), date(2025, 10, 31))
    assert meses[-1] == (date(2026, 4, 1), date(2026, 4, 28))
    assert len(meses) == 7


def test_deve_resetar_checkpoint_default_false(monkeypatch):
    monkeypatch.delenv(pncp.RESET_CHECKPOINT_ENV, raising=False)

    assert pncp.deve_resetar_checkpoint() is False


def test_deve_resetar_checkpoint_true(monkeypatch):
    monkeypatch.setenv(pncp.RESET_CHECKPOINT_ENV, "sim")

    assert pncp.deve_resetar_checkpoint() is True


def test_params_tem_janela_valida():
    assert pncp._params_tem_janela_valida(
        {"dataInicial": "20251201", "dataFinal": "20251231"}
    )


def test_params_tem_janela_valida_rejeita_range_invertido():
    assert not pncp._params_tem_janela_valida(
        {"dataInicial": "20251231", "dataFinal": "20251201"}
    )


def test_params_tem_janela_valida_rejeita_range_acima_de_365_dias():
    assert not pncp._params_tem_janela_valida(
        {"dataInicial": "20250101", "dataFinal": "20260102"}
    )


def test_coletar_paginas_restantes_preserva_ordem(monkeypatch):
    async def fake_fetch(client, params, pausa_global):
        pagina = params["pagina"]
        return {"data": [{"pagina": pagina}], "totalPaginas": 4}

    monkeypatch.setattr(pncp, "fetch_com_backoff", fake_fetch)

    pausa_global = asyncio.Event()
    pausa_global.set()
    registros, sucesso = asyncio.run(
        pncp._coletar_paginas_restantes(
            client=object(),
            params_base={"pagina": 1},
            total_pags=4,
            pausa_global=pausa_global,
        )
    )

    assert sucesso is True
    assert [row["pagina"] for row in registros] == [2, 3, 4]


def test_coletar_paginas_restantes_reprocessa_paginas_pendentes(monkeypatch):
    chamadas = []

    async def fake_fetch(client, params, pausa_global):
        pagina = params["pagina"]
        chamadas.append(pagina)
        if pagina == 3 and chamadas.count(3) == 1:
            return None
        return {"data": [{"pagina": pagina}], "totalPaginas": 4}

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr(pncp, "fetch_com_backoff", fake_fetch)
    monkeypatch.setattr(pncp.asyncio, "sleep", fake_sleep)

    pausa_global = asyncio.Event()
    pausa_global.set()
    registros, sucesso = asyncio.run(
        pncp._coletar_paginas_restantes(
            client=object(),
            params_base={"pagina": 1},
            total_pags=4,
            pausa_global=pausa_global,
        )
    )

    assert sucesso is True
    assert chamadas.count(3) == 2
    assert [row["pagina"] for row in registros] == [2, 3, 4]

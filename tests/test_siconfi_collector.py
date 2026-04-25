import asyncio
import pandas as pd

from src.collectors import siconfi


def test_resolver_demonstrativos_rreo_usa_simplificado_quando_extrato_indica():
    itens = [
        {"entregavel": "MSC Agregada"},
        {"entregavel": "Relatório Resumido de Execução Orçamentária Simplificado"},
    ]

    assert siconfi._resolver_demonstrativos_rreo(itens) == ["RREO Simplificado"]


def test_priorizar_demonstrativos_rreo_prefere_simplificado_para_municipio_pequeno():
    itens = [
        {"entregavel": "Relatório Resumido de Execução Orçamentária"},
        {"entregavel": "Relatório Resumido de Execução Orçamentária Simplificado"},
    ]

    assert siconfi._priorizar_demonstrativos_rreo(itens, populacao=12000) == [
        "RREO Simplificado",
        "RREO",
    ]


def test_priorizar_demonstrativos_rreo_prefere_normal_para_municipio_grande():
    itens = [
        {"entregavel": "Relatório Resumido de Execução Orçamentária Simplificado"},
        {"entregavel": "Relatório Resumido de Execução Orçamentária"},
    ]

    assert siconfi._priorizar_demonstrativos_rreo(itens, populacao=120000) == [
        "RREO",
        "RREO Simplificado",
    ]


def test_resolver_planos_rgf_usa_simplificado_semestral_quando_extrato_indica():
    itens = [
        {"entregavel": "Relatório de Gestão Fiscal Simplificado", "periodicidade": "S"},
    ]

    assert siconfi._resolver_planos_rgf(itens) == [("RGF Simplificado", "S")]


def test_resolver_planos_rgf_preserva_caminho_normal_quadrimestral():
    itens = [
        {"entregavel": "Relatório de Gestão Fiscal", "periodicidade": "Q"},
    ]

    assert siconfi._resolver_planos_rgf(itens) == [("RGF", "Q")]


def test_priorizar_planos_rgf_prefere_simplificado_semestral_para_municipio_pequeno():
    itens = [
        {"entregavel": "Relatório de Gestão Fiscal", "periodicidade": "Q"},
        {"entregavel": "Relatório de Gestão Fiscal Simplificado", "periodicidade": "S"},
    ]

    assert siconfi._priorizar_planos_rgf(itens, populacao=15000)[:2] == [
        ("RGF Simplificado", "S"),
        ("RGF", "Q"),
    ]


def test_priorizar_planos_rgf_prefere_normal_quadrimestral_para_municipio_grande():
    itens = [
        {"entregavel": "Relatório de Gestão Fiscal Simplificado", "periodicidade": "S"},
        {"entregavel": "Relatório de Gestão Fiscal", "periodicidade": "Q"},
    ]

    assert siconfi._priorizar_planos_rgf(itens, populacao=150000)[:2] == [
        ("RGF", "Q"),
        ("RGF Simplificado", "S"),
    ]


def test_resolver_demonstrativos_rreo_aceita_nome_curto_legado():
    itens = [
        {"entregavel": "RREO Simplificado"},
    ]

    assert siconfi._resolver_demonstrativos_rreo(itens) == ["RREO Simplificado"]


def test_resolver_planos_rgf_aceita_nome_curto_legado():
    itens = [
        {"entregavel": "RGF Simplificado", "periodicidade": "S"},
    ]

    assert siconfi._resolver_planos_rgf(itens) == [("RGF Simplificado", "S")]


def test_resolver_planos_rgf_faz_fallback_legado_sem_extrato():
    assert siconfi._resolver_planos_rgf([]) == [("RGF", "Q"), ("RGF", "S")]


def test_montar_tarefas_rreo_gera_um_caminho_prioritario_em_ordem_decrescente():
    tarefas = siconfi._montar_tarefas_rreo(
        2024,
        "3100104",
        [
            {"entregavel": "Relatório Resumido de Execução Orçamentária"},
            {"entregavel": "Relatório Resumido de Execução Orçamentária Simplificado"},
        ],
        populacao=10000,
    )

    assert len(tarefas) == 24
    assert all(tarefa[-1] == "RREO Simplificado" for tarefa in tarefas[:12])
    assert all(tarefa[-1] == "RREO" for tarefa in tarefas[12:])
    assert [tarefa[1] for tarefa in tarefas[:4]] == [6, 6, 5, 5]
    assert {tarefa[3] for tarefa in tarefas} == {"RREO-Anexo 01", "RREO-Anexo 07"}


def test_montar_tarefas_rgf_limita_primeiro_plano_ao_caminho_prioritario():
    tarefas = siconfi._montar_tarefas_rgf(
        2024,
        "3100104",
        [
            {"entregavel": "Relatório de Gestão Fiscal", "periodicidade": "Q"},
            {"entregavel": "Relatório de Gestão Fiscal Simplificado", "periodicidade": "S"},
        ],
        populacao=10000,
    )

    assert tarefas[0][-1] == "RGF Simplificado"
    assert tarefas[0][5] == "S"
    assert tarefas[:2][0][1] == 2


def test_build_entidade_planos_trata_df_com_ente_estadual_e_mapeia_saida():
    df = pd.DataFrame(
        [
            {
                "cod_ibge": "5300108",
                "ente": "Brasília",
                "populacao": 2996899,
            }
        ]
    )

    planos = siconfi._build_entidade_planos("DF", df)

    assert planos == [
        {
            "query_id": siconfi.DF_QUERY_ID_ENTE,
            "output_cod_ibge": siconfi.DF_OUTPUT_COD_IBGE,
            "populacao": 2996899,
            "esfera": siconfi.DF_SCOPE_ESFERA,
            "instituicao_filtro": siconfi.DF_ENTITY_NAME,
        }
    ]


def test_extrair_assincrono_aceita_tipo_demonstrativo_custom(monkeypatch):
    chamadas = []
    pausa_global = asyncio.Event()
    pausa_global.set()

    async def fake_fetch(client, url, params, pausa_global):
        chamadas.append(params.copy())
        return {"items": [{"ok": True}], "hasMore": False}

    monkeypatch.setattr(siconfi, "fetch_com_retry", fake_fetch)

    resultado = asyncio.run(
        siconfi.extrair_assincrono(
            client=object(),
            endpoint="rreo",
            ano=2024,
            periodo=6,
            id_ente="3100104",
            anexo="RREO-Anexo 01",
            semaforo=asyncio.Semaphore(1),
            pausa_global=pausa_global,
            progresso=siconfi.Progresso(1, "TEST"),
            tipo_demonstrativo="RREO Simplificado",
        )
    )

    assert resultado == [{"ok": True}]
    assert chamadas[0]["co_tipo_demonstrativo"] == "RREO Simplificado"


def test_extrair_assincrono_aceita_progresso_none(monkeypatch):
    pausa_global = asyncio.Event()
    pausa_global.set()

    async def fake_fetch(client, url, params, pausa_global):
        return {"items": [{"ok": True}], "hasMore": False}

    monkeypatch.setattr(siconfi, "fetch_com_retry", fake_fetch)

    resultado = asyncio.run(
        siconfi.extrair_assincrono(
            client=object(),
            endpoint="rgf",
            ano=2024,
            periodo=2,
            id_ente="3100104",
            anexo="RGF-Anexo 05",
            semaforo=asyncio.Semaphore(1),
            pausa_global=pausa_global,
            progresso=None,
            poder="E",
            periodicidade="S",
            tipo_demonstrativo="RGF Simplificado",
        )
    )

    assert resultado == [{"ok": True}]

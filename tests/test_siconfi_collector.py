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


def test_validar_buffer_publicacao_permite_ate_limite(monkeypatch):
    monkeypatch.setattr(siconfi, "MAX_BUFFER_PUBLICACAO_LINHAS", 2)

    siconfi._validar_buffer_publicacao(
        [{"a": 1}, {"a": 2}],
        table="siconfi_rreo",
        uf="PB",
    )


def test_validar_buffer_publicacao_falha_acima_do_limite(monkeypatch):
    monkeypatch.setattr(siconfi, "MAX_BUFFER_PUBLICACAO_LINHAS", 1)

    try:
        siconfi._validar_buffer_publicacao(
            [{"a": 1}, {"a": 2}],
            table="siconfi_rreo",
            uf="PB",
        )
    except RuntimeError as exc:
        assert "Buffer SICONFI excedeu" in str(exc)
        assert "siconfi_rreo" in str(exc)
    else:
        raise AssertionError("Esperava RuntimeError para buffer acima do limite")


def test_adicionar_registros_por_exercicio_separa_buffers(monkeypatch):
    monkeypatch.setattr(siconfi, "MAX_BUFFER_PUBLICACAO_LINHAS", 2)
    buffers = {}

    siconfi._adicionar_registros_por_exercicio(
        buffers,
        [
            {"exercicio": 2025, "valor": 1},
            {"exercicio": "2026", "valor": 2},
            {"exercicio": 2025, "valor": 3},
        ],
        table="siconfi_rreo",
        uf="PB",
    )

    assert sorted(buffers) == ["2025", "2026"]
    assert [registro["valor"] for registro in buffers["2025"]] == [1, 3]
    assert [registro["valor"] for registro in buffers["2026"]] == [2]


def test_adicionar_registros_por_exercicio_valida_limite_por_ano(monkeypatch):
    monkeypatch.setattr(siconfi, "MAX_BUFFER_PUBLICACAO_LINHAS", 1)

    try:
        siconfi._adicionar_registros_por_exercicio(
            {},
            [{"exercicio": 2025}, {"exercicio": 2025}],
            table="siconfi_rreo",
            uf="PB",
        )
    except RuntimeError as exc:
        assert "Buffer SICONFI excedeu" in str(exc)
    else:
        raise AssertionError("Esperava RuntimeError para bucket anual acima do limite")


def test_flush_registros_por_exercicio_publica_um_lote_por_ano(monkeypatch):
    chamadas = []

    def fake_flush(registros, *, table, uf, key_cols, publish_mode="replace"):
        chamadas.append(
            {
                "exercicio": registros[0]["exercicio"],
                "linhas": len(registros),
                "table": table,
                "uf": uf,
                "key_cols": key_cols,
            }
        )
        registros.clear()

    monkeypatch.setattr(siconfi, "_flush_registros_lote", fake_flush)
    buffers = {
        "2026": [{"exercicio": 2026}],
        "2025": [{"exercicio": 2025}, {"exercicio": 2025}],
    }

    siconfi._flush_registros_por_exercicio(
        buffers,
        table="siconfi_rreo",
        uf="PB",
        key_cols=siconfi.CHAVE_RREO,
    )

    assert chamadas == [
        {
            "exercicio": 2025,
            "linhas": 2,
            "table": "siconfi_rreo",
            "uf": "PB",
            "key_cols": siconfi.CHAVE_RREO,
        },
        {
            "exercicio": 2026,
            "linhas": 1,
            "table": "siconfi_rreo",
            "uf": "PB",
            "key_cols": siconfi.CHAVE_RREO,
        },
    ]


def test_normalizar_publish_mode_usa_env(monkeypatch):
    monkeypatch.setenv(siconfi.SICONFI_PUBLISH_MODE_ENV, "append")

    assert siconfi._normalizar_publish_mode() == "append"


def test_normalizar_publish_mode_rejeita_valor_invalido():
    try:
        siconfi._normalizar_publish_mode("merge")
    except ValueError as exc:
        assert "append" in str(exc)
        assert "replace" in str(exc)
    else:
        raise AssertionError("Esperava ValueError para publish_mode invalido")


def test_flush_registros_lote_publica_replace_slice_sem_criar_destino(monkeypatch):
    chamadas = []

    def fake_publish(df, table, uf, key_cols, slice_cols, ensure_target=True):
        chamadas.append(
            {
                "linhas": len(df),
                "table": table,
                "uf": uf,
                "key_cols": key_cols,
                "slice_cols": slice_cols,
                "ensure_target": ensure_target,
            }
        )

    monkeypatch.delenv(siconfi.SICONFI_TABLE_SUFFIX_ENV, raising=False)
    monkeypatch.setattr(siconfi, "publish_raw_replace_slice", fake_publish)
    registros = [
        {
            "uf": "PB",
            "cod_ibge": "2500106",
            "exercicio": 2025,
            "periodo": 6,
            "anexo": "RREO-Anexo 01",
            "cod_conta": "1",
            "coluna": "valor",
            "conta": "Receita",
            "esfera": "M",
        }
    ]

    siconfi._flush_registros_lote(
        registros,
        table="siconfi_rreo",
        uf="PB",
        key_cols=siconfi.CHAVE_RREO,
    )

    assert chamadas == [
        {
            "linhas": 1,
            "table": "siconfi_rreo",
            "uf": "PB",
            "key_cols": siconfi.CHAVE_RREO,
            "slice_cols": ["exercicio"],
            "ensure_target": False,
        }
    ]
    assert registros == []


def test_flush_registros_lote_publica_append_quando_solicitado(monkeypatch):
    chamadas = []

    def fake_append(df, table, uf, key_cols, slice_cols):
        chamadas.append(
            {
                "linhas": len(df),
                "table": table,
                "uf": uf,
                "key_cols": key_cols,
                "slice_cols": slice_cols,
            }
        )

    monkeypatch.delenv(siconfi.SICONFI_TABLE_SUFFIX_ENV, raising=False)
    monkeypatch.setattr(siconfi, "publish_raw_append_slice", fake_append)
    registros = [{"uf": "PB", "cod_ibge": "2500106", "exercicio": 2025}]

    siconfi._flush_registros_lote(
        registros,
        table="siconfi_rreo",
        uf="PB",
        key_cols=siconfi.CHAVE_RREO,
        publish_mode="append",
    )

    assert chamadas == [
        {
            "linhas": 1,
            "table": "siconfi_rreo",
            "uf": "PB",
            "key_cols": siconfi.CHAVE_RREO,
            "slice_cols": ["exercicio"],
        }
    ]
    assert registros == []


def test_flush_registros_lote_respeita_sufixo_de_destino(monkeypatch):
    chamadas = []

    def fake_publish(df, table, uf, key_cols, slice_cols, ensure_target=True):
        chamadas.append({"table": table, "ensure_target": ensure_target})

    monkeypatch.setenv(siconfi.SICONFI_TABLE_SUFFIX_ENV, "_v2")
    monkeypatch.setattr(siconfi, "publish_raw_replace_slice", fake_publish)

    siconfi._flush_registros_lote(
        [{"uf": "PB", "cod_ibge": "2500106", "exercicio": 2025}],
        table="siconfi_rreo",
        uf="PB",
        key_cols=siconfi.CHAVE_RREO,
    )

    assert chamadas == [{"table": "siconfi_rreo_v2", "ensure_target": False}]


def test_siconfi_destination_table_rejeita_sufixo_sem_underscore(monkeypatch):
    monkeypatch.setenv(siconfi.SICONFI_TABLE_SUFFIX_ENV, "v2")

    try:
        siconfi._siconfi_destination_table("siconfi_rreo")
    except ValueError as exc:
        assert siconfi.SICONFI_TABLE_SUFFIX_ENV in str(exc)
        assert "_v2" in str(exc)
    else:
        raise AssertionError("Esperava ValueError para sufixo SICONFI invalido")

from src.collectors import dca


def test_extrair_metricas_bp_mapeia_contas_em_uma_passada():
    items = [
        {"conta": "Ativo Financeiro", "valor": "10"},
        {"conta": "Passivo Financeiro", "valor": "4"},
        {"conta": "Outra Conta", "valor": "999"},
    ]

    ativo, passivo = dca.extrair_metricas_bp(items)

    assert ativo == 10.0
    assert passivo == 4.0


def test_extrair_metricas_receita_prefere_coluna_realizada():
    items = [
        {"conta": dca.CONTA_REC_TRIBUTARIA, "coluna": "Previsao Atualizada", "valor": "15"},
        {"conta": dca.CONTA_REC_TRIBUTARIA, "coluna": dca.COLUNA_REALIZADO, "valor": "11"},
        {"conta": dca.CONTA_REC_CORRENTE, "coluna": dca.COLUNA_REALIZADO, "valor": "80"},
    ]

    rec_trib, rec_corr = dca.extrair_metricas_receita(items)

    assert rec_trib == 11.0
    assert rec_corr == 80.0


def test_extrair_receita_faz_fallback_quando_nao_ha_coluna_realizada():
    items = [
        {"conta": dca.CONTA_REC_CORRENTE, "coluna": "Alguma Outra", "valor": "42"},
    ]

    assert dca.extrair_receita(items, dca.CONTA_REC_CORRENTE) == 42.0

SELECT
    cod_ibge,
    ano,
    periodicidade_rgf,
    periodo_rgf,
    dcl_apos_rp_total,
    dcl_apos_rp_rpps,
    dcl_pre_rp_total,
    dcl_pre_rp_rpps,
    receita_realizada
FROM {{ ref('int_siconfi_base_anual') }}
WHERE has_rgf_regime_prioritario
-- Janela SICONFI parametrizavel. Default: 2021 ate o ano corrente.
  AND ano BETWEEN {{ var('siconfi_ano_inicio', '2021') }}
              AND {{ var('siconfi_ano_fim', 'EXTRACT(YEAR FROM CURRENT_DATE())') }}

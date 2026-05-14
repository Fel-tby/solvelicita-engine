SELECT
    cod_ibge,
    ano,
    receita_realizada,
    receita_prevista,
    receita_prevista IS NOT NULL AS entregou_rreo,
    CASE
        WHEN receita_prevista IS NOT NULL AND receita_prevista > 0
        THEN ROUND(receita_realizada / receita_prevista * 100, 6)
    END AS eorcam_raw
FROM {{ ref('int_siconfi_base_anual') }}
-- Janela SICONFI parametrizavel. Default: 2021 ate o ano corrente.
WHERE has_rreo_ultimo_periodo
  AND ano BETWEEN {{ var('siconfi_ano_inicio', '2021') }}
              AND {{ var('siconfi_ano_fim', 'EXTRACT(YEAR FROM CURRENT_DATE())') }}

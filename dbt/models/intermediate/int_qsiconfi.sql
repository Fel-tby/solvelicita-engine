WITH contagem AS (
    SELECT
        cod_ibge,
        COUNTIF(receita_prevista IS NOT NULL) AS anos_entregues
    FROM {{ ref('int_siconfi_base_anual') }}
    WHERE has_rreo_ultimo_periodo
      -- Janela SICONFI parametrizavel. Default: 2021 ate o ano corrente.
      AND ano BETWEEN {{ var('siconfi_ano_inicio', '2021') }}
                  AND {{ var('siconfi_ano_fim', 'EXTRACT(YEAR FROM CURRENT_DATE())') }}
    GROUP BY cod_ibge
),
spine AS (
SELECT DISTINCT cod_ibge FROM {{ ref('stg_municipios') }}
)
SELECT
    s.cod_ibge,
    COALESCE(c.anos_entregues, 0) AS anos_entregues
FROM spine s
LEFT JOIN contagem c ON s.cod_ibge = c.cod_ibge

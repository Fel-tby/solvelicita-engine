WITH contagem AS (
    SELECT
        cod_ibge,
        COUNTIF(receita_prevista IS NOT NULL) AS anos_entregues
    FROM {{ ref('int_siconfi_base_anual') }}
    WHERE has_rreo_ultimo_periodo
      -- Dinamico: sempre cobre os ultimos 6 anos completos. Em 2026 = 2020 AND 2025.
      AND ano BETWEEN EXTRACT(YEAR FROM CURRENT_DATE()) - 6
                  AND EXTRACT(YEAR FROM CURRENT_DATE()) - 1
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

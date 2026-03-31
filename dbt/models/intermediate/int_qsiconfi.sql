WITH ultimo_periodo AS (
    SELECT cod_ibge, ano, MAX(periodo) AS max_periodo
    FROM {{ ref('stg_siconfi_rreo') }}
    WHERE ano BETWEEN 2020 AND 2025
    GROUP BY cod_ibge, ano
),
entregues AS (
    SELECT
        r.cod_ibge,
        r.ano,
        MAX(CASE
            WHEN r.anexo     = 'RREO-Anexo 01'
             AND r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
             AND r.coluna    = 'PREVISÃO ATUALIZADA (a)'
            THEN 1
        END) AS entregou_rreo
    FROM {{ ref('stg_siconfi_rreo') }} r
    INNER JOIN ultimo_periodo up
        ON  r.cod_ibge = up.cod_ibge
        AND r.ano      = up.ano
        AND r.periodo  = up.max_periodo
    GROUP BY r.cod_ibge, r.ano
),
contagem AS (
    SELECT cod_ibge, COUNTIF(entregou_rreo = 1) AS anos_entregues
    FROM entregues
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
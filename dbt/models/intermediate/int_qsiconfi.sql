WITH ultimo_periodo AS (
SELECT cod_ibge, ano, MAX(periodo) AS max_periodo
FROM {{ ref('stg_siconfi_rreo') }}
-- Dinamico: sempre cobre os ultimos 6 anos completos. Em 2026 = 2020 AND 2025.
WHERE ano BETWEEN EXTRACT(YEAR FROM CURRENT_DATE()) - 6
               AND EXTRACT(YEAR FROM CURRENT_DATE()) - 1
GROUP BY cod_ibge, ano
),
entregues AS (
SELECT
    r.cod_ibge,
    r.ano,
    MAX(CASE
        WHEN r.anexo LIKE 'RREO-Anexo 01%'
        AND r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
        AND REGEXP_CONTAINS(LOWER(r.coluna), r'^previs.o atualizada \(a\)$')
        THEN 1
    END) AS entregou_rreo
FROM {{ ref('stg_siconfi_rreo') }} r
INNER JOIN ultimo_periodo up
    ON r.cod_ibge = up.cod_ibge
    AND r.ano     = up.ano
    AND r.periodo = up.max_periodo
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

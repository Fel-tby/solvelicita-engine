WITH ultimo_periodo AS (
    SELECT cod_ibge, ano, MAX(periodo) AS max_periodo
    FROM {{ ref('stg_siconfi_rreo') }}
    -- Dinamico: sempre cobre os ultimos 6 anos completos. Em 2026 = 2020 AND 2025.
    WHERE ano BETWEEN EXTRACT(YEAR FROM CURRENT_DATE()) - 6
                   AND EXTRACT(YEAR FROM CURRENT_DATE()) - 1
    GROUP BY cod_ibge, ano
),
pivot AS (
    SELECT
        r.cod_ibge,
        r.ano,
        MAX(CASE
            WHEN r.anexo     LIKE 'RREO-Anexo 01%'
             AND r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
             AND REGEXP_CONTAINS(LOWER(r.coluna), r'^at. o bimestre \(c\)$')
            THEN r.valor
        END) AS receita_realizada,
        MAX(CASE
            WHEN r.anexo     LIKE 'RREO-Anexo 01%'
             AND r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
             AND REGEXP_CONTAINS(LOWER(r.coluna), r'^previs.o atualizada \(a\)$')
            THEN r.valor
        END) AS receita_prevista
    FROM {{ ref('stg_siconfi_rreo') }} r
    INNER JOIN ultimo_periodo up
        ON  r.cod_ibge = up.cod_ibge
        AND r.ano      = up.ano
        AND r.periodo  = up.max_periodo
    GROUP BY r.cod_ibge, r.ano
)
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
FROM pivot

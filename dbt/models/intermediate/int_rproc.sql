WITH ultimo_periodo AS (
    SELECT cod_ibge, ano, MAX(periodo) AS max_periodo
    FROM {{ ref('stg_siconfi_rreo') }}
    WHERE ano BETWEEN 2020 AND 2025
    GROUP BY cod_ibge, ano
),
pivot AS (
    SELECT
        r.cod_ibge,
        r.ano,
        MAX(CASE
            WHEN r.anexo     = 'RREO-Anexo 01'
             AND r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
             AND r.coluna    = 'PREVISÃO ATUALIZADA (a)'
            THEN r.valor
        END) AS receita_prevista,
        MAX(CASE
            WHEN r.anexo     = 'RREO-Anexo 01'
             AND r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
             AND r.coluna    = 'Até o Bimestre (c)'
            THEN r.valor
        END) AS receita_realizada,
        MAX(CASE
            WHEN r.anexo     = 'RREO-Anexo 07'
             AND r.cod_conta = 'RestosAPagarProcessadosENaoProcessadosLiquidadosAPagar'
             AND r.coluna    = 'Saldo e = (a+ b) - (c + d)'
             AND r.conta     = 'TOTAL (III) = (I + II)'
            THEN r.valor
        END) AS rrestos_processados
    FROM {{ ref('stg_siconfi_rreo') }} r
    INNER JOIN ultimo_periodo up
        ON  r.cod_ibge = up.cod_ibge
        AND r.ano      = up.ano
        AND r.periodo  = up.max_periodo
    GROUP BY r.cod_ibge, r.ano
),
com_pct AS (
    SELECT
        cod_ibge,
        ano,
        receita_prevista IS NOT NULL AS entregou_rreo,
        CASE
            WHEN rrestos_processados IS NOT NULL
             AND receita_realizada   IS NOT NULL
             AND receita_realizada   > 0
            THEN rrestos_processados / receita_realizada * 100
        END AS rproc_pct
    FROM pivot
),
contagem AS (
    SELECT
        cod_ibge,
        COUNTIF(
            entregou_rreo
            AND rproc_pct IS NOT NULL
            AND rproc_pct > 3.0
        ) AS n_anos_cronicos
    FROM com_pct
    GROUP BY cod_ibge
),
spine AS (
    SELECT DISTINCT cod_ibge FROM {{ ref('stg_cauc') }}
)
SELECT
    s.cod_ibge,
    COALESCE(c.n_anos_cronicos, 0) AS n_anos_cronicos
FROM spine s
LEFT JOIN contagem c ON s.cod_ibge = c.cod_ibge
WITH com_pct AS (
    SELECT
        cod_ibge,
        ano,
        receita_prevista IS NOT NULL AS entregou_rreo,
        CASE
            WHEN rrestos_processados IS NOT NULL
            AND  receita_realizada   IS NOT NULL
            AND  receita_realizada   > 0
            THEN rrestos_processados / receita_realizada * 100
        END AS rproc_pct
    FROM {{ ref('int_siconfi_base_anual') }}
    WHERE has_rreo_ultimo_periodo
      -- Dinamico: sempre cobre os ultimos 6 anos completos. Em 2026 = 2020 AND 2025.
      AND ano BETWEEN EXTRACT(YEAR FROM CURRENT_DATE()) - 6
                  AND EXTRACT(YEAR FROM CURRENT_DATE()) - 1
),
mais_recente AS (
    SELECT
        cod_ibge,
        ROUND(rproc_pct, 2) AS rproc_pct_atual
    FROM (
        SELECT
            *,
            ROW_NUMBER() OVER (PARTITION BY cod_ibge ORDER BY ano DESC) AS rn
        FROM com_pct
        WHERE entregou_rreo
          AND rproc_pct IS NOT NULL
    )
    WHERE rn = 1
),
contagem AS (
    SELECT
        cod_ibge,
        COUNTIF(
            entregou_rreo
            AND rproc_pct IS NOT NULL
            AND rproc_pct > 3.0
        )                              AS n_anos_cronicos,
        COUNTIF(rproc_pct IS NOT NULL) AS n_anos_com_rproc
    FROM com_pct
    GROUP BY cod_ibge
),
spine AS (
    SELECT DISTINCT cod_ibge FROM {{ ref('stg_municipios') }}
)
SELECT
    s.cod_ibge,
    COALESCE(c.n_anos_cronicos, 0) AS n_anos_cronicos,
    mr.rproc_pct_atual
FROM spine s
LEFT JOIN contagem c ON s.cod_ibge = c.cod_ibge
LEFT JOIN mais_recente mr ON s.cod_ibge = mr.cod_ibge

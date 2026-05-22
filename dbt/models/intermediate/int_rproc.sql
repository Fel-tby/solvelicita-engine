WITH com_pct AS (
    SELECT
        cod_ibge,
        ano,
        rrestos_processados,
        receita_realizada,
        receita_prevista IS NOT NULL AS entregou_rreo,
        CASE
            WHEN rrestos_processados IS NOT NULL
            AND  receita_realizada   IS NOT NULL
            AND  receita_realizada   > 0
            THEN rrestos_processados / receita_realizada * 100
        END AS rproc_pct
    FROM {{ ref('int_siconfi_base_anual') }}
    WHERE has_rreo_ultimo_periodo
      -- Janela SICONFI parametrizavel. Default: 2021 ate o ano corrente.
      AND ano BETWEEN {{ var('siconfi_ano_inicio', '2021') }}
                  AND {{ var('siconfi_ano_fim', 'EXTRACT(YEAR FROM CURRENT_DATE())') }}
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
historico AS (
    SELECT
        cod_ibge,
        TO_JSON_STRING(
            ARRAY_AGG(
                STRUCT(
                    ano AS ano,
                    ROUND(rproc_pct, 2) AS rproc_pct,
                    ROUND(rrestos_processados, 2) AS rrestos_processados,
                    ROUND(receita_realizada, 2) AS receita_realizada,
                    rproc_pct > 3.0 AS cronico
                )
                ORDER BY ano
            )
        ) AS rproc_historico_json
    FROM com_pct
    WHERE entregou_rreo
      AND rproc_pct IS NOT NULL
    GROUP BY cod_ibge
),
spine AS (
    SELECT DISTINCT cod_ibge FROM {{ ref('stg_municipios') }}
)
SELECT
    s.cod_ibge,
    COALESCE(c.n_anos_cronicos, 0) AS n_anos_cronicos,
    mr.rproc_pct_atual,
    COALESCE(h.rproc_historico_json, '[]') AS rproc_historico_json
FROM spine s
LEFT JOIN contagem c ON s.cod_ibge = c.cod_ibge
LEFT JOIN mais_recente mr ON s.cod_ibge = mr.cod_ibge
LEFT JOIN historico h ON s.cod_ibge = h.cod_ibge

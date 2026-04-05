WITH spine AS (
    SELECT DISTINCT cod_ibge, municipio AS ente, populacao, uf
    FROM {{ ref('stg_municipios') }}
),

-- rrestos_nproc_pct: ano mais recente com entrega RREO
ultimo_periodo_rr AS (
    SELECT cod_ibge, ano, MAX(periodo) AS max_periodo
    FROM {{ ref('stg_siconfi_rreo') }}
    -- Dinamico: sempre cobre os ultimos 6 anos completos. Em 2026 = 2020 AND 2025.
    WHERE ano BETWEEN EXTRACT(YEAR FROM CURRENT_DATE()) - 6
                   AND EXTRACT(YEAR FROM CURRENT_DATE()) - 1
    GROUP BY cod_ibge, ano
),
pivot_rrestos AS (
    SELECT
        r.cod_ibge,
        r.ano,
        MAX(CASE
            WHEN r.anexo     LIKE 'RREO-Anexo 01%'
            AND  r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
            AND  REGEXP_CONTAINS(LOWER(r.coluna), r'^at. o bimestre \(c\)$')
            THEN r.valor
        END) AS receita_realizada,
        MAX(CASE
            WHEN r.anexo     LIKE 'RREO-Anexo 07%'
            AND  r.cod_conta IN ('RestosAPagarNaoProcessadosAPagar', 'RestosAPagarNaoProcessadosAPagarIntra')
            AND  REGEXP_CONTAINS(LOWER(r.coluna), r'^saldo k = \(f ?\+ ?g\) - \(i ?\+ ?j\)$')
            AND  REGEXP_CONTAINS(LOWER(r.conta), r'^total \(iii\) = \(i \+ ii\)$')
            THEN r.valor
        END) AS rrestos_nao_processados
    FROM {{ ref('stg_siconfi_rreo') }} r
    INNER JOIN ultimo_periodo_rr up
        ON r.cod_ibge = up.cod_ibge
       AND r.ano      = up.ano
       AND r.periodo  = up.max_periodo
    GROUP BY r.cod_ibge, r.ano
),
rrestos_mais_recente AS (
    SELECT cod_ibge,
        ROUND(rrestos_nao_processados / receita_realizada * 100, 2) AS rrestos_nproc_pct
    FROM (
        SELECT *,
            ROW_NUMBER() OVER (PARTITION BY cod_ibge ORDER BY ano DESC) AS rn
        FROM pivot_rrestos
        WHERE rrestos_nao_processados IS NOT NULL
          AND receita_realizada        IS NOT NULL
          AND receita_realizada        > 0
    )
    WHERE rn = 1
)

SELECT
    s.cod_ibge,
    s.uf,
    s.ente,
    s.populacao,

    rr.rrestos_nproc_pct,

    -- ── rproc
    rp.n_anos_cronicos                 AS n_anos_cronicos,

    -- ── qsiconfi
    COALESCE(qi.anos_entregues, 0)     AS anos_entregues,

    -- ── cauc
    COALESCE(cg.ccauc,       1.0)      AS ccauc,
    COALESCE(cg.n_graves,    0)        AS n_graves,
    COALESCE(cg.n_moderadas, 0)        AS n_moderadas,
    COALESCE(cg.n_leves,     0)        AS n_leves,
    COALESCE(cg.pendencias, 'REGULAR') AS pendencias,

    CURRENT_TIMESTAMP() AS updated_at

FROM spine s
LEFT JOIN {{ ref('int_rproc') }}         rp ON s.cod_ibge = rp.cod_ibge
LEFT JOIN {{ ref('int_qsiconfi') }}       qi ON s.cod_ibge = qi.cod_ibge
LEFT JOIN {{ ref('int_cauc_gravidade') }} cg ON s.cod_ibge = cg.cod_ibge
LEFT JOIN rrestos_mais_recente            rr ON s.cod_ibge = rr.cod_ibge

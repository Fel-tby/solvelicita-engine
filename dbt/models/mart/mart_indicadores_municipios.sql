WITH spine AS (
    SELECT DISTINCT cod_ibge, municipio AS ente, populacao, uf
    FROM {{ ref('stg_cauc') }}
),

-- rrestos_nproc_pct: ano mais recente com entrega RREO
ultimo_periodo_rr AS (
    SELECT cod_ibge, ano, MAX(periodo) AS max_periodo
    FROM {{ ref('stg_siconfi_rreo') }}
    WHERE ano BETWEEN 2020 AND 2025
    GROUP BY cod_ibge, ano
),
pivot_rrestos AS (
    SELECT
        r.cod_ibge,
        r.ano,
        MAX(CASE
            WHEN r.anexo     = 'RREO-Anexo 01'
            AND  r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
            AND  r.coluna    = 'Até o Bimestre (c)'
            THEN r.valor
        END) AS receita_realizada,
        MAX(CASE
            WHEN r.anexo     = 'RREO-Anexo 07'
            AND  r.cod_conta = 'RestosAPagarNaoProcessadosAPagar'
            AND  r.coluna    = 'Saldo k = (f + g) - (i + j)'
            AND  r.conta     = 'TOTAL (III) = (I + II)'
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

    -- ── siconfi (preenchido por siconfi_postprocessor.py)
    CAST(NULL AS FLOAT64)  AS eorcam_raw,
    CAST(NULL AS FLOAT64)  AS lliq_raw,
    CAST(NULL AS BOOL)     AS lliq_parcial,
    CAST(NULL AS INT64)    AS dias_atraso,
    CAST(NULL AS FLOAT64)  AS decay_fator,
    CAST(NULL AS BOOL)     AS dado_suspeito_lliq,
    CAST(NULL AS BOOL)     AS dado_defasado,
    rr.rrestos_nproc_pct,

    -- ── rproc
    rp.n_anos_cronicos               AS n_anos_cronicos,

    -- ── qsiconfi
    COALESCE(qi.anos_entregues, 0) AS anos_entregues,

    -- ── cauc
    COALESCE(cg.ccauc,       0.0)      AS ccauc,
    COALESCE(cg.n_graves,    0)        AS n_graves,
    COALESCE(cg.n_moderadas, 0)        AS n_moderadas,
    COALESCE(cg.n_leves,     0)        AS n_leves,
    COALESCE(cg.pendencias, 'REGULAR') AS pendencias,

    -- ── dca (preenchido por dca_postprocessor.py)
    CAST(NULL AS FLOAT64)  AS autonomia_media,
    CAST(NULL AS BOOL)     AS autonomia_critica,

    -- ── pncp
    pn.n_licitacoes,
    pn.valor_homologado_total,
    pn.n_dispensa,
    pn.valor_hom_dispensa,
    pn.pct_dispensa,
    pn.ano_ultima_licitacao,
    CASE WHEN COALESCE(pn.pct_dispensa, 0) > 0.30 THEN TRUE ELSE FALSE END
        AS alerta_dispensa,

    CURRENT_TIMESTAMP() AS updated_at

FROM spine s
LEFT JOIN {{ ref('int_rproc') }}         rp ON s.cod_ibge = rp.cod_ibge
LEFT JOIN {{ ref('int_qsiconfi') }}       qi ON s.cod_ibge = qi.cod_ibge
LEFT JOIN {{ ref('int_cauc_gravidade') }} cg ON s.cod_ibge = cg.cod_ibge
LEFT JOIN rrestos_mais_recente            rr ON s.cod_ibge = rr.cod_ibge
LEFT JOIN {{ ref('int_pncp_agregado') }}  pn ON s.cod_ibge = pn.cod_ibge
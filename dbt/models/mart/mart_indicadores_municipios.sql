WITH spine AS (
    SELECT DISTINCT cod_ibge, municipio AS ente, populacao, uf
    FROM {{ ref('stg_municipios') }}
)

SELECT
    s.cod_ibge,
    s.uf,
    s.ente,
    s.populacao,

    rp.rproc_pct_atual,

    -- rproc
    rp.n_anos_cronicos                 AS n_anos_cronicos,

    -- qsiconfi
    COALESCE(qi.anos_entregues, 0)     AS anos_entregues,

    -- cauc
    COALESCE(cg.ccauc,       1.0)      AS ccauc,
    COALESCE(cg.n_graves,    0)        AS n_graves,
    COALESCE(cg.n_moderadas, 0)        AS n_moderadas,
    COALESCE(cg.n_leves,     0)        AS n_leves,
    COALESCE(cg.pendencias, 'REGULAR') AS pendencias,
    COALESCE(cg.pendencias_cauc_json, '[]') AS pendencias_cauc_json,

    CURRENT_TIMESTAMP() AS updated_at

FROM spine s
LEFT JOIN {{ ref('int_rproc') }}         rp ON s.cod_ibge = rp.cod_ibge
LEFT JOIN {{ ref('int_qsiconfi') }}       qi ON s.cod_ibge = qi.cod_ibge
LEFT JOIN {{ ref('int_cauc_gravidade') }} cg ON s.cod_ibge = cg.cod_ibge

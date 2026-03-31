-- mart_pncp_municipios.sql
-- Visão consolidada de licitações por município (via int_pncp_agregado)

SELECT
    p.cod_ibge,
    s.uf,
    s.ente,
    s.populacao,
    p.n_licitacoes,
    p.valor_homologado_total,
    p.n_dispensa,
    p.valor_hom_dispensa,
    p.pct_dispensa,
    p.ano_ultima_licitacao,
    CASE
        WHEN COALESCE(p.pct_dispensa, 0) > 0.30 THEN TRUE
        ELSE FALSE
    END                             AS alerta_dispensa,
    CURRENT_TIMESTAMP()             AS updated_at
FROM {{ ref('int_pncp_agregado') }} p
LEFT JOIN (
    SELECT DISTINCT cod_ibge, uf, municipio AS ente, populacao
    FROM {{ ref('stg_cauc') }}
) s ON p.cod_ibge = s.cod_ibge
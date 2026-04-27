-- mart_pncp_municipios.sql
-- Visão consolidada de licitações por município (via int_pncp_agregado)

SELECT
    p.cod_ibge,
    s.uf,
    s.ente,
    s.populacao,
    p.n_licitacoes,
    p.n_com_valor_homologado,
    p.n_sem_valor_homologado,
    p.valor_homologado_total,
    p.n_dispensa,
    p.valor_hom_dispensa,
    p.pct_dispensa,
    p.n_inexigibilidade,
    p.valor_hom_inexigibilidade,
    p.pct_inexigibilidade,
    p.n_contratacao_direta,
    p.valor_hom_contratacao_direta,
    p.pct_contratacao_direta,
    p.ano_ultima_licitacao,
    -- O alerta historico permanece no mesmo nome, agora ligado so a
    -- dispensa real (modalidade 8), nao a inexigibilidade (modalidade 9).
    CASE
        WHEN COALESCE(p.pct_dispensa, 0) > 0.30 THEN TRUE
        ELSE FALSE
    END                             AS alerta_dispensa,
    CURRENT_TIMESTAMP()             AS updated_at
FROM {{ ref('int_pncp_agregado') }} p
LEFT JOIN (
    SELECT DISTINCT cod_ibge, uf, municipio AS ente, populacao
    FROM {{ ref('stg_municipios') }}
) s ON p.cod_ibge = s.cod_ibge

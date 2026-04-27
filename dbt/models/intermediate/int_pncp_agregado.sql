WITH janela AS (
    SELECT *
    FROM {{ ref('stg_pncp') }}
    WHERE data_publicacao_pncp >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
      AND cod_ibge IS NOT NULL
)
SELECT
    cod_ibge,
    COUNT(*)                                                          AS n_licitacoes,
    COUNTIF(valor_total_homologado IS NOT NULL)                       AS n_com_valor_homologado,
    COUNTIF(valor_total_homologado IS NULL)                           AS n_sem_valor_homologado,

    -- Valor financeiro realizado: nao substitui homologado ausente por estimado.
    -- Null aqui significa "valor homologado ainda nao informado pelo PNCP".
    SUM(valor_total_homologado)                                       AS valor_homologado_total,

    -- Mantem os nomes historicos para nao quebrar producao, mas agora
    -- "dispensa" significa apenas modalidade 8. Modalidade 9 e inexigibilidade.
    COUNTIF(modalidade_id = 8)                                        AS n_dispensa,
    SUM(CASE WHEN modalidade_id = 8 THEN valor_total_homologado END)  AS valor_hom_dispensa,
    ROUND(
        SAFE_DIVIDE(
            SUM(CASE WHEN modalidade_id = 8 THEN valor_total_homologado END),
            SUM(valor_total_homologado)
        ),
        6
    )                                                                 AS pct_dispensa,

    COUNTIF(modalidade_id = 9)                                        AS n_inexigibilidade,
    SUM(CASE WHEN modalidade_id = 9 THEN valor_total_homologado END)  AS valor_hom_inexigibilidade,
    ROUND(
        SAFE_DIVIDE(
            SUM(CASE WHEN modalidade_id = 9 THEN valor_total_homologado END),
            SUM(valor_total_homologado)
        ),
        6
    )                                                                 AS pct_inexigibilidade,

    COUNTIF(modalidade_id IN (8, 9))                                  AS n_contratacao_direta,
    SUM(CASE
        WHEN modalidade_id IN (8, 9)
        THEN valor_total_homologado
    END)                                                              AS valor_hom_contratacao_direta,
    ROUND(
        SAFE_DIVIDE(
            SUM(CASE
                WHEN modalidade_id IN (8, 9)
                THEN valor_total_homologado
            END),
            SUM(valor_total_homologado)
        ),
        6
    )                                                                 AS pct_contratacao_direta,

    MAX(ano_compra)                                                   AS ano_ultima_licitacao
FROM janela
GROUP BY cod_ibge

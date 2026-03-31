WITH janela AS (
    SELECT *
    FROM {{ ref('stg_pncp') }}
    WHERE data_publicacao_pncp >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
      AND cod_ibge IS NOT NULL
)
SELECT
    cod_ibge,
    COUNT(*)                                                          AS n_licitacoes,
    SUM(COALESCE(valor_total_homologado, 0))                          AS valor_homologado_total,
    COUNTIF(modalidade_id IN (8, 9))                                  AS n_dispensa,
    SUM(CASE
        WHEN modalidade_id IN (8, 9)
        THEN COALESCE(valor_total_homologado, 0)
        ELSE 0
    END)                                                              AS valor_hom_dispensa,
    CASE
        WHEN SUM(COALESCE(valor_total_homologado, 0)) > 0
        THEN ROUND(
            SUM(CASE WHEN modalidade_id IN (8,9)
                THEN COALESCE(valor_total_homologado,0) ELSE 0 END)
            / SUM(COALESCE(valor_total_homologado, 0)),
            6
        )
    END                                                               AS pct_dispensa,
    MAX(ano_compra)                                                   AS ano_ultima_licitacao
FROM janela
GROUP BY cod_ibge
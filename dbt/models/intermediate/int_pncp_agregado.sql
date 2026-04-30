WITH janela AS (
    SELECT
        *,
        -- Guardrail de qualidade PNCP: municipios ocasionalmente publicam
        -- valorTotalHomologado com erros de escala/casas decimais. Valores
        -- acima de R$ 8 bi sao tratados como outliers e nao entram nas somas
        -- nem nos percentuais usados pelo modelo/front.
        CASE
            WHEN valor_total_homologado > 8000000000 THEN NULL
            ELSE valor_total_homologado
        END AS valor_homologado_modelo,
        valor_total_homologado > 8000000000 AS valor_homologado_outlier
    FROM {{ ref('stg_pncp') }}
    WHERE data_publicacao_pncp >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
      AND cod_ibge IS NOT NULL
)
SELECT
    cod_ibge,
    COUNT(*)                                                          AS n_licitacoes,
    COUNTIF(valor_homologado_modelo IS NOT NULL)                      AS n_com_valor_homologado,
    COUNTIF(valor_homologado_modelo IS NULL)                          AS n_sem_valor_homologado,

    -- Valor financeiro realizado: nao substitui homologado ausente por estimado.
    -- Null aqui significa "valor homologado ainda nao informado pelo PNCP"
    -- ou outlier acima do teto operacional de R$ 8 bi.
    SUM(valor_homologado_modelo)                                      AS valor_homologado_total,

    -- Mantem os nomes historicos para nao quebrar producao, mas agora
    -- "dispensa" significa apenas modalidade 8. Modalidade 9 e inexigibilidade.
    COUNTIF(modalidade_id = 8)                                        AS n_dispensa,
    SUM(CASE WHEN modalidade_id = 8 THEN valor_homologado_modelo END) AS valor_hom_dispensa,
    ROUND(
        SAFE_DIVIDE(
            SUM(CASE WHEN modalidade_id = 8 THEN valor_homologado_modelo END),
            SUM(valor_homologado_modelo)
        ),
        6
    )                                                                 AS pct_dispensa,

    COUNTIF(modalidade_id = 9)                                        AS n_inexigibilidade,
    SUM(CASE WHEN modalidade_id = 9 THEN valor_homologado_modelo END) AS valor_hom_inexigibilidade,
    ROUND(
        SAFE_DIVIDE(
            SUM(CASE WHEN modalidade_id = 9 THEN valor_homologado_modelo END),
            SUM(valor_homologado_modelo)
        ),
        6
    )                                                                 AS pct_inexigibilidade,

    COUNTIF(modalidade_id IN (8, 9))                                  AS n_contratacao_direta,
    SUM(CASE
        WHEN modalidade_id IN (8, 9)
        THEN valor_homologado_modelo
    END)                                                              AS valor_hom_contratacao_direta,
    ROUND(
        SAFE_DIVIDE(
            SUM(CASE
                WHEN modalidade_id IN (8, 9)
                THEN valor_homologado_modelo
            END),
            SUM(valor_homologado_modelo)
        ),
        6
    )                                                                 AS pct_contratacao_direta,

    MAX(ano_compra)                                                   AS ano_ultima_licitacao
FROM janela
GROUP BY cod_ibge

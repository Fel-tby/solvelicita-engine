{{ config(
    materialized='table',
    partition_by={
      "field": "ano",
      "data_type": "int64",
      "range": {"start": 2018, "end": 2031, "interval": 1}
    },
    cluster_by=["uf", "cod_ibge"]
) }}

WITH anos_com_dados_rreo AS (
    SELECT DISTINCT
        uf,
        ano
    FROM {{ ref('stg_siconfi_rreo') }}
    WHERE cod_conta IS NOT NULL
      AND valor IS NOT NULL
),
municipios AS (
    SELECT
        uf,
        cod_ibge,
        municipio AS instituicao,
        populacao
    FROM {{ ref('stg_municipios') }}
),
malha_rreo_uf_ano AS (
    SELECT
        m.uf,
        m.cod_ibge,
        m.instituicao,
        m.populacao,
        a.ano
    FROM municipios m
    INNER JOIN anos_com_dados_rreo a
        ON m.uf = a.uf
),
ultimo_periodo_rreo AS (
    SELECT
        cod_ibge,
        ano,
        MAX(periodo) AS periodo_rreo
    FROM {{ ref('stg_siconfi_rreo') }}
    GROUP BY cod_ibge, ano
),
dados_rreo AS (
    SELECT
        r.cod_ibge,
        r.ano,
        up.periodo_rreo,
        TRUE AS has_rreo_ultimo_periodo,

        MAX(CASE
            WHEN r.anexo LIKE 'RREO-Anexo 01%'
             AND r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
             AND REGEXP_CONTAINS(LOWER(r.coluna), r'^at. o bimestre \(c\)$')
            THEN r.valor
        END) AS receita_realizada,

        MAX(CASE
            WHEN r.anexo LIKE 'RREO-Anexo 01%'
             AND r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
             AND REGEXP_CONTAINS(LOWER(r.coluna), r'^previs.o atualizada \(a\)$')
            THEN r.valor
        END) AS receita_prevista,

        MAX(CASE
            WHEN r.anexo LIKE 'RREO-Anexo 01%'
             AND r.cod_conta = 'TotalDespesas'
             AND REGEXP_CONTAINS(LOWER(r.coluna), r'^despesas liquidadas at. o bimestre \(h\)$')
            THEN r.valor
        END) AS despesa_liquidada,

        MAX(CASE
            WHEN r.anexo LIKE 'RREO-Anexo 07%'
             AND r.cod_conta = 'RestosAPagarNaoProcessadosAPagar'
             AND REGEXP_CONTAINS(LOWER(r.coluna), r'^saldo k = \(f ?\+ ?g\) - \(i ?\+ ?j\)$')
             AND REGEXP_CONTAINS(LOWER(r.conta), r'^total \(iii\) = \(i \+ ii\)$')
            THEN r.valor
        END) AS rrestos_nao_processados,

        MAX(CASE
            WHEN r.anexo LIKE 'RREO-Anexo 07%'
             AND r.cod_conta IN (
                 'RestosAPagarProcessadosENaoProcessadosLiquidadosAPagar',
                 'RestosAPagarProcessadosENaoProcessadosLiquidadosAPagarIntra'
             )
             AND REGEXP_CONTAINS(LOWER(r.coluna), r'^saldo e = \(a ?\+ ?b\) - \(c ?\+ ?d\)$')
             AND REGEXP_CONTAINS(LOWER(r.conta), r'^total \(iii\) = \(i \+ ii\)$')
            THEN r.valor
        END) AS rrestos_processados
    FROM {{ ref('stg_siconfi_rreo') }} r
    INNER JOIN ultimo_periodo_rreo up
        ON r.cod_ibge = up.cod_ibge
       AND r.ano = up.ano
       AND r.periodo = up.periodo_rreo
    GROUP BY r.cod_ibge, r.ano, up.periodo_rreo
),
ultimo_periodo_rgf AS (
    SELECT
        cod_ibge,
        ano,
        periodicidade,
        MAX(periodo) AS periodo_rgf
    FROM {{ ref('stg_siconfi_rgf') }}
    WHERE anexo = 'RGF-Anexo 05'
    GROUP BY cod_ibge, ano, periodicidade
),
regime_prioritario AS (
    SELECT
        cod_ibge,
        ano,
        periodicidade,
        periodo_rgf,
        ROW_NUMBER() OVER (
            PARTITION BY cod_ibge, ano
            ORDER BY CASE periodicidade WHEN 'Q' THEN 1 WHEN 'S' THEN 2 ELSE 3 END
        ) AS prioridade
    FROM ultimo_periodo_rgf
),
dados_rgf AS (
    SELECT
        r.cod_ibge,
        r.ano,
        rp.periodicidade AS periodicidade_rgf,
        rp.periodo_rgf,
        TRUE AS has_rgf_regime_prioritario,

        MAX(CASE
            WHEN r.cod_conta = 'DisponibilidadeDeCaixaLiquidaAposRP'
             AND REGEXP_CONTAINS(LOWER(r.conta), r'^total \(iv\) = \(i \+ ii \+ iii\)$')
            THEN r.valor
        END) AS dcl_apos_rp_total_iv,
        MAX(CASE
            WHEN r.cod_conta = 'DisponibilidadeDeCaixaLiquidaAposRP'
             AND REGEXP_CONTAINS(LOWER(r.conta), r'^total \(iii\) = \(i \+ ii\)$')
            THEN r.valor
        END) AS dcl_apos_rp_total_iii,
        MAX(CASE
            WHEN r.cod_conta = 'DisponibilidadeDeCaixaLiquidaAposRP'
             AND REGEXP_CONTAINS(LOWER(r.conta), r'^total dos recursos vinculados ao rpps \(iii\)$')
            THEN r.valor
        END) AS dcl_apos_rp_rpps,

        MAX(CASE
            WHEN r.cod_conta = 'DisponibilidadeDeCaixaLiquida'
             AND REGEXP_CONTAINS(LOWER(r.conta), r'^total \(iv\) = \(i \+ ii \+ iii\)$')
            THEN r.valor
        END) AS dcl_pre_rp_total_iv,
        MAX(CASE
            WHEN r.cod_conta = 'DisponibilidadeDeCaixaLiquida'
             AND REGEXP_CONTAINS(LOWER(r.conta), r'^total \(iii\) = \(i \+ ii\)$')
            THEN r.valor
        END) AS dcl_pre_rp_total_iii,
        MAX(CASE
            WHEN r.cod_conta = 'DisponibilidadeDeCaixaLiquida'
             AND REGEXP_CONTAINS(LOWER(r.conta), r'^total dos recursos vinculados ao rpps \(iii\)$')
            THEN r.valor
        END) AS dcl_pre_rp_rpps
    FROM {{ ref('stg_siconfi_rgf') }} r
    INNER JOIN regime_prioritario rp
        ON r.cod_ibge = rp.cod_ibge
       AND r.ano = rp.ano
       AND r.periodicidade = rp.periodicidade
       AND r.periodo = rp.periodo_rgf
       AND rp.prioridade = 1
    WHERE r.anexo LIKE 'RGF-Anexo 05%'
    GROUP BY r.cod_ibge, r.ano, rp.periodicidade, rp.periodo_rgf
),
entidade_ano_source AS (
    SELECT cod_ibge, ano, TRUE AS in_malha_rreo_uf_ano
    FROM malha_rreo_uf_ano

    UNION ALL

    SELECT cod_ibge, ano, FALSE AS in_malha_rreo_uf_ano
    FROM dados_rreo

    UNION ALL

    SELECT cod_ibge, ano, FALSE AS in_malha_rreo_uf_ano
    FROM dados_rgf
),
entidade_ano AS (
    SELECT
        eas.cod_ibge,
        eas.ano,
        LOGICAL_OR(eas.in_malha_rreo_uf_ano) AS in_malha_rreo_uf_ano,
        ANY_VALUE(m.uf) AS uf,
        ANY_VALUE(m.instituicao) AS instituicao,
        ANY_VALUE(m.populacao) AS populacao
    FROM entidade_ano_source eas
    LEFT JOIN municipios m
        ON eas.cod_ibge = m.cod_ibge
    GROUP BY eas.cod_ibge, eas.ano
)
SELECT
    ea.uf,
    ea.cod_ibge,
    ea.instituicao,
    ea.ano,
    ea.populacao,
    ea.in_malha_rreo_uf_ano,
    COALESCE(dr.has_rreo_ultimo_periodo, FALSE) AS has_rreo_ultimo_periodo,
    COALESCE(dg.has_rgf_regime_prioritario, FALSE) AS has_rgf_regime_prioritario,
    dr.periodo_rreo,
    dg.periodicidade_rgf,
    dg.periodo_rgf,
    dr.receita_prevista,
    dr.receita_realizada,
    dr.despesa_liquidada,
    dr.rrestos_nao_processados,
    dr.rrestos_processados,
    COALESCE(dg.dcl_apos_rp_total_iv, dg.dcl_apos_rp_total_iii) AS dcl_apos_rp_total,
    dg.dcl_apos_rp_rpps,
    COALESCE(dg.dcl_pre_rp_total_iv, dg.dcl_pre_rp_total_iii) AS dcl_pre_rp_total,
    dg.dcl_pre_rp_rpps
FROM entidade_ano ea
LEFT JOIN dados_rreo dr
    ON ea.cod_ibge = dr.cod_ibge
   AND ea.ano = dr.ano
LEFT JOIN dados_rgf dg
    ON ea.cod_ibge = dg.cod_ibge
   AND ea.ano = dg.ano

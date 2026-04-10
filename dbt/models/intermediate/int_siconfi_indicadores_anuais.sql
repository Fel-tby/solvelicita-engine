{{ config(materialized='view') }}

WITH anos_com_dados AS (
    SELECT DISTINCT
        uf,
        ano
    FROM {{ ref('stg_siconfi_rreo') }}
    WHERE cod_conta IS NOT NULL
      AND valor IS NOT NULL
),
malha_base AS (
    SELECT
        m.uf,
        m.cod_ibge,
        m.municipio AS instituicao,
        m.populacao,
        a.ano
    FROM {{ ref('stg_municipios') }} m
    INNER JOIN anos_com_dados a
        ON m.uf = a.uf
),
ultimo_periodo_rreo AS (
    SELECT
        cod_ibge,
        ano,
        MAX(periodo) AS max_periodo
    FROM {{ ref('stg_siconfi_rreo') }}
    GROUP BY cod_ibge, ano
),
dados_rreo AS (
    SELECT
        r.cod_ibge,
        r.ano,

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
       AND r.periodo = up.max_periodo
    GROUP BY r.cod_ibge, r.ano
),
ultimo_periodo_rgf AS (
    SELECT
        cod_ibge,
        ano,
        periodicidade,
        MAX(periodo) AS max_periodo
    FROM {{ ref('stg_siconfi_rgf') }}
    WHERE anexo = 'RGF-Anexo 05'
    GROUP BY cod_ibge, ano, periodicidade
),
regime_prioritario AS (
    SELECT
        cod_ibge,
        ano,
        periodicidade,
        max_periodo,
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
        rp.max_periodo AS periodo_rgf,

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
       AND r.periodo = rp.max_periodo
       AND rp.prioridade = 1
    WHERE r.anexo LIKE 'RGF-Anexo 05%'
    GROUP BY r.cod_ibge, r.ano, rp.periodicidade, rp.max_periodo
),
base AS (
    SELECT
        mb.uf,
        mb.cod_ibge,
        mb.instituicao,
        mb.ano,
        mb.populacao,
        dr.receita_prevista,
        dr.receita_realizada,
        dr.despesa_liquidada,
        dr.rrestos_nao_processados,
        dr.rrestos_processados,
        COALESCE(rg.dcl_apos_rp_total_iv, rg.dcl_apos_rp_total_iii) AS dcl_apos_rp_total,
        rg.dcl_apos_rp_rpps,
        COALESCE(rg.dcl_pre_rp_total_iv, rg.dcl_pre_rp_total_iii) AS dcl_pre_rp_total,
        rg.dcl_pre_rp_rpps,
        rg.periodicidade_rgf,
        rg.periodo_rgf
    FROM malha_base mb
    LEFT JOIN dados_rreo dr
        ON mb.cod_ibge = dr.cod_ibge
       AND mb.ano = dr.ano
    LEFT JOIN dados_rgf rg
        ON mb.cod_ibge = rg.cod_ibge
       AND mb.ano = rg.ano
),
calculado AS (
    SELECT
        uf,
        cod_ibge,
        instituicao,
        ano,
        populacao,
        receita_prevista,
        receita_realizada,
        despesa_liquidada,
        rrestos_nao_processados,
        rrestos_processados,
        dcl_apos_rp_total,
        dcl_apos_rp_rpps,
        dcl_pre_rp_total,
        dcl_pre_rp_rpps,
        periodicidade_rgf,
        periodo_rgf,
        receita_prevista IS NOT NULL AS entregou_rreo,
        CASE
            WHEN receita_prevista IS NOT NULL AND receita_prevista > 0
            THEN ROUND(receita_realizada / receita_prevista * 100, 2)
        END AS eorcam,
        CASE
            WHEN rrestos_nao_processados IS NOT NULL
             AND receita_realizada IS NOT NULL
             AND receita_realizada > 0
            THEN ROUND(rrestos_nao_processados / receita_realizada * 100, 2)
        END AS rrestos_nproc_pct,
        CASE
            WHEN rrestos_processados IS NOT NULL
             AND receita_realizada IS NOT NULL
             AND receita_realizada > 0
            THEN ROUND(rrestos_processados / receita_realizada * 100, 2)
        END AS rproc_pct,
        CASE
            WHEN despesa_liquidada IS NOT NULL
             AND receita_realizada IS NOT NULL
             AND receita_realizada > 0
            THEN ROUND((despesa_liquidada - receita_realizada) / receita_realizada * 100, 2)
        END AS deficit_pct,
        CASE
            WHEN receita_realizada IS NULL OR receita_realizada <= 0 THEN NULL
            WHEN dcl_apos_rp_total IS NOT NULL
                THEN ROUND((dcl_apos_rp_total - COALESCE(dcl_apos_rp_rpps, 0)) / receita_realizada, 6)
            WHEN dcl_pre_rp_total IS NOT NULL
                THEN ROUND((dcl_pre_rp_total - COALESCE(dcl_pre_rp_rpps, 0)) / receita_realizada, 6)
        END AS lliq,
        CASE
            WHEN receita_realizada IS NULL OR receita_realizada <= 0 THEN NULL
            WHEN dcl_apos_rp_total IS NOT NULL
                THEN ROUND(dcl_apos_rp_total - COALESCE(dcl_apos_rp_rpps, 0), 2)
            WHEN dcl_pre_rp_total IS NOT NULL
                THEN ROUND(dcl_pre_rp_total - COALESCE(dcl_pre_rp_rpps, 0), 2)
        END AS lliq_bruta,
        CASE
            WHEN receita_realizada IS NULL OR receita_realizada <= 0 THEN FALSE
            WHEN dcl_apos_rp_total IS NOT NULL THEN FALSE
            WHEN dcl_pre_rp_total IS NOT NULL THEN TRUE
            ELSE FALSE
        END AS lliq_parcial
    FROM base
)
SELECT *
FROM calculado
WHERE NOT (
    receita_prevista IS NULL
    AND receita_realizada IS NULL
    AND despesa_liquidada IS NULL
    AND rrestos_nao_processados IS NULL
    AND rrestos_processados IS NULL
    AND dcl_apos_rp_total IS NULL
    AND dcl_pre_rp_total IS NULL
)

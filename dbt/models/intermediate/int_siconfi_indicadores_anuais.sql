{{ config(materialized='table') }}

WITH calculado AS (
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
    FROM {{ ref('int_siconfi_base_anual') }}
    WHERE in_malha_rreo_uf_ano
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

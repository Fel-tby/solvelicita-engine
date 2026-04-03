WITH ultimo_periodo_rreo AS (
SELECT cod_ibge, ano, MAX(periodo) AS max_periodo
FROM {{ ref('stg_siconfi_rreo') }}
WHERE ano BETWEEN 2020 AND 2025
GROUP BY cod_ibge, ano
),
receita AS (
SELECT
    r.cod_ibge,
    r.ano,
    MAX(CASE
        WHEN r.anexo LIKE 'RREO-Anexo 01%'
        AND r.cod_conta = 'ReceitasExcetoIntraOrcamentarias'
        AND REGEXP_CONTAINS(LOWER(r.coluna), r'^at. o bimestre \(c\)$')
        THEN r.valor
    END) AS receita_realizada
FROM {{ ref('stg_siconfi_rreo') }} r
INNER JOIN ultimo_periodo_rreo up
    ON r.cod_ibge = up.cod_ibge
    AND r.ano    = up.ano
    AND r.periodo = up.max_periodo
GROUP BY r.cod_ibge, r.ano
),
ultimo_periodo_rgf AS (
SELECT cod_ibge, ano, periodicidade, MAX(periodo) AS max_periodo
FROM {{ ref('stg_siconfi_rgf') }}
WHERE anexo = 'RGF-Anexo 05'
AND ano BETWEEN 2020 AND 2025
GROUP BY cod_ibge, ano, periodicidade
),
regime_prioritario AS (
SELECT
    cod_ibge, ano, periodicidade, max_periodo,
    ROW_NUMBER() OVER (
        PARTITION BY cod_ibge, ano
        ORDER BY CASE periodicidade WHEN 'Q' THEN 1 WHEN 'S' THEN 2 ELSE 3 END
    ) AS prioridade
FROM ultimo_periodo_rgf
),
rgf_pivot AS (
SELECT
    r.cod_ibge,
    r.ano,
    rp.periodicidade AS periodicidade_rgf,
    rp.max_periodo   AS periodo_rgf,

    -- AposRP total: estrutura com RPPS usa (IV), sem RPPS usa (III) como fallback
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

    -- PreRP total: estrutura com RPPS usa (IV), sem RPPS usa (III) como fallback
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
    ON r.cod_ibge     = rp.cod_ibge
    AND r.ano         = rp.ano
    AND r.periodicidade = rp.periodicidade
    AND r.periodo     = rp.max_periodo
    AND rp.prioridade = 1
WHERE r.anexo LIKE 'RGF-Anexo 05%'
GROUP BY r.cod_ibge, r.ano, rp.periodicidade, rp.max_periodo
)
SELECT
    rg.cod_ibge,
    rg.ano,
    rg.periodicidade_rgf,
    rg.periodo_rgf,
    COALESCE(rg.dcl_apos_rp_total_iv, rg.dcl_apos_rp_total_iii) AS dcl_apos_rp_total,
    rg.dcl_apos_rp_rpps,
    COALESCE(rg.dcl_pre_rp_total_iv,  rg.dcl_pre_rp_total_iii)  AS dcl_pre_rp_total,
    rg.dcl_pre_rp_rpps,
    rc.receita_realizada
FROM rgf_pivot rg
LEFT JOIN receita rc
    ON rg.cod_ibge = rc.cod_ibge
    AND rg.ano     = rc.ano
SELECT
    cod_ibge,
    ano,
    periodicidade_rgf,
    periodo_rgf,
    dcl_apos_rp_total,
    dcl_apos_rp_rpps,
    dcl_pre_rp_total,
    dcl_pre_rp_rpps,
    receita_realizada
FROM {{ ref('int_siconfi_base_anual') }}
WHERE has_rgf_regime_prioritario
-- Dinamico: sempre cobre os ultimos 6 anos completos. Em 2026 = 2020 AND 2025.
  AND ano BETWEEN EXTRACT(YEAR FROM CURRENT_DATE()) - 6
              AND EXTRACT(YEAR FROM CURRENT_DATE()) - 1

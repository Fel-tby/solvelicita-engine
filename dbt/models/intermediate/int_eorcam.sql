SELECT
    cod_ibge,
    ano,
    receita_realizada,
    receita_prevista,
    receita_prevista IS NOT NULL AS entregou_rreo,
    CASE
        WHEN receita_prevista IS NOT NULL AND receita_prevista > 0
        THEN ROUND(receita_realizada / receita_prevista * 100, 6)
    END AS eorcam_raw
FROM {{ ref('int_siconfi_base_anual') }}
-- Dinamico: sempre cobre os ultimos 6 anos completos. Em 2026 = 2020 AND 2025.
WHERE has_rreo_ultimo_periodo
  AND ano BETWEEN EXTRACT(YEAR FROM CURRENT_DATE()) - 6
              AND EXTRACT(YEAR FROM CURRENT_DATE()) - 1

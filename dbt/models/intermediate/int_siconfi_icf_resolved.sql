{{ config(materialized='table') }}

WITH target_years AS (
    SELECT DISTINCT cod_ibge, ano
    FROM {{ ref('int_siconfi_base_anual') }}

    UNION DISTINCT

    SELECT DISTINCT cod_ibge, ano
    FROM {{ ref('int_autonomia_base') }}
),
icf_clean AS (
    SELECT
        cod_ibge,
        ano AS icf_exercicio,
        edicao_ranking,
        status_icf,
        conceito_icf,
        fator_icf,
        percentual_acertos,
        fonte_url
    FROM {{ ref('stg_siconfi_icf') }}
),
resolved AS (
    SELECT
        t.cod_ibge,
        t.ano,
        i.icf_exercicio,
        i.edicao_ranking,
        i.status_icf,
        i.conceito_icf,
        i.fator_icf,
        i.percentual_acertos,
        i.fonte_url,
        ROW_NUMBER() OVER (
            PARTITION BY t.cod_ibge, t.ano
            ORDER BY
                i.icf_exercicio DESC,
                CASE i.status_icf
                    WHEN 'FINAL' THEN 1
                    WHEN 'PREVIO_OFICIAL' THEN 2
                    ELSE 9
                END
        ) AS rn
    FROM target_years t
    LEFT JOIN icf_clean i
      ON i.cod_ibge = t.cod_ibge
     AND i.icf_exercicio <= t.ano
)
SELECT
    cod_ibge,
    ano,
    icf_exercicio,
    edicao_ranking,
    COALESCE(status_icf, 'SEM_ICF') AS status_icf,
    COALESCE(conceito_icf, 'SEM_ICF') AS conceito_icf,
    COALESCE(fator_icf, 0.80) AS fator_icf,
    percentual_acertos,
    fonte_url,
    icf_exercicio IS NULL AS icf_sem_registro,
    icf_exercicio IS NOT NULL AND icf_exercicio < ano AS icf_defasado,
    COALESCE(status_icf = 'PREVIO_OFICIAL', FALSE) AS icf_previo
FROM resolved
WHERE rn = 1

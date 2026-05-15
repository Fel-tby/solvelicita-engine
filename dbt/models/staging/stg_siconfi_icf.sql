WITH source AS (
    SELECT * FROM {{ source('raw', 'siconfi_icf') }}
),
typed AS (
    SELECT
        UPPER(TRIM(CAST(uf AS STRING))) AS uf,
        CAST(LPAD(CAST(cod_ibge AS STRING), 7, '0') AS INT64) AS cod_ibge,
        municipio,
        CAST(exercicio AS INT64) AS ano,
        CAST(exercicio AS INT64) AS exercicio,
        CAST(edicao_ranking AS INT64) AS edicao_ranking,
        status_icf,
        UPPER(TRIM(CAST(conceito_icf AS STRING))) AS conceito_icf,
        CAST(fator_icf AS FLOAT64) AS fator_icf,
        CAST(percentual_acertos AS FLOAT64) AS percentual_acertos,
        SAFE_CAST(posicao_ranking AS INT64) AS posicao_ranking,
        CAST(total_pontos AS FLOAT64) AS total_pontos,
        CAST(dim_i AS FLOAT64) AS dim_i,
        CAST(dim_ii AS FLOAT64) AS dim_ii,
        CAST(dim_iii AS FLOAT64) AS dim_iii,
        CAST(dim_iv AS FLOAT64) AS dim_iv,
        fonte_url
    FROM source
)
SELECT *
FROM typed
WHERE uf IS NOT NULL
  AND cod_ibge IS NOT NULL
  AND ano IS NOT NULL
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cod_ibge, ano
    ORDER BY
        CASE status_icf
            WHEN 'FINAL' THEN 1
            WHEN 'PREVIO_OFICIAL' THEN 2
            ELSE 9
        END
) = 1

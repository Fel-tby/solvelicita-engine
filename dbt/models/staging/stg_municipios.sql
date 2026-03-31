WITH source AS (
    SELECT * FROM {{ source('raw', 'dim_municipios') }}
),
renamed AS (
    SELECT
        CAST(cod_ibge AS INT64)  AS cod_ibge,
        uf,
        ente                     AS municipio,
        CAST(populacao AS INT64) AS populacao
    FROM source
    QUALIFY ROW_NUMBER() OVER(
        PARTITION BY CAST(cod_ibge AS INT64) 
        ORDER BY uf -- Ordem arbitrária, dados são imutáveis por IBGE
    ) = 1
)
SELECT * FROM renamed

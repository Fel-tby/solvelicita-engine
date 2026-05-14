WITH source AS (
    SELECT * FROM {{ source('raw', var('siconfi_rreo_source', 'siconfi_rreo')) }}
),
renamed AS (
    SELECT
        CAST(cod_ibge    AS INT64)   AS cod_ibge,
        uf,
        instituicao,
        CAST(exercicio   AS INT64)   AS ano,
        periodo,
        periodicidade,
        demonstrativo,
        anexo,
        esfera,
        rotulo,
        coluna,
        cod_conta,
        conta,
        CAST(valor       AS FLOAT64) AS valor,
        CAST(populacao   AS INT64)   AS populacao
    FROM source
    QUALIFY ROW_NUMBER() OVER(
        PARTITION BY
            CAST(cod_ibge AS INT64),
            CAST(exercicio AS INT64),
            periodo,
            anexo,
            cod_conta,
            coluna,
            conta,
            esfera
        ORDER BY uf
    ) = 1
)
SELECT * FROM renamed

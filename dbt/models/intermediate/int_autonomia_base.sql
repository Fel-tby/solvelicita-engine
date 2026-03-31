SELECT
    cod_ibge,
    ano,
    populacao,
    rec_tributaria,
    rec_corrente,
    CASE
        WHEN rec_tributaria IS NOT NULL
         AND rec_corrente   IS NOT NULL
         AND rec_corrente   > 0
        THEN ROUND(rec_tributaria / rec_corrente, 6)
    END AS autonomia_raw
FROM {{ ref('stg_dca') }}
WHERE ano BETWEEN 2020 AND 2024
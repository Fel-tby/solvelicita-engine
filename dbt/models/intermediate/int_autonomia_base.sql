WITH limite AS (
    -- Dinamico: sempre cobre os 5 anos DCA uniformemente liberados. Em 2026 = 2020 AND 2024.
    SELECT LEAST(
        COALESCE(MAX(ano), EXTRACT(YEAR FROM CURRENT_DATE()) - 2),
        EXTRACT(YEAR FROM CURRENT_DATE()) - 2
    ) AS ano_max
    FROM {{ ref('stg_dca') }}
)
SELECT
    d.cod_ibge,
    d.ano,
    d.populacao,
    d.rec_tributaria,
    d.rec_corrente,
    CASE
        WHEN d.rec_tributaria IS NOT NULL
         AND d.rec_corrente   IS NOT NULL
         AND d.rec_corrente   > 0
        THEN ROUND(d.rec_tributaria / d.rec_corrente, 6)
    END AS autonomia_raw
FROM {{ ref('stg_dca') }} d
CROSS JOIN limite l
WHERE d.ano BETWEEN l.ano_max - 4 AND l.ano_max

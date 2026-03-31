WITH pendencias_long AS (
    SELECT cod_ibge, col_stg, valor_req
    FROM {{ ref('stg_cauc') }}
    UNPIVOT INCLUDE NULLS (
        valor_req FOR col_stg IN (
            req_previdenciaria_rpps,
            req_fiscal_rfb,
            req_pgfn,
            req_fgts,
            req_trabalhista_tst,
            req_lrf_pessoal_exec,
            req_lrf_pessoal_leg,
            req_siops,
            req_siops_demo,
            req_siope,
            req_siope_demo,
            req_siope_compl,
            req_siope_obs,
            req_siga,
            req_siconv_pc,
            req_siconv_debitos,
            req_cadin,
            req_tcu,
            req_cgu,
            req_sistn_divida,
            req_sistn_garantias,
            req_siconfi_rreo,
            req_siconfi_rgf,
            req_siconfi_balanco,
            req_siconfi_dca,
            req_siconfi_pcasp,
            req_siconfi_dcasp,
            req_siconfi_mcasp
        )
    )
),
pendentes AS (
    SELECT
        p.cod_ibge,
        r.descricao,
        r.gravidade
    FROM pendencias_long p
    INNER JOIN {{ ref('cauc_requisitos') }} r ON p.col_stg = r.col_stg
    WHERE TRIM(COALESCE(p.valor_req, '')) IN ('!', '')
),
agregado AS (
    SELECT
        cod_ibge,
        COUNTIF(gravidade = 'GRAVE')    AS n_graves,
        COUNTIF(gravidade = 'MODERADA') AS n_moderadas,
        COUNTIF(gravidade = 'LEVE')     AS n_leves,
        STRING_AGG(
            descricao, ' | '
            ORDER BY CASE gravidade WHEN 'GRAVE' THEN 1 WHEN 'MODERADA' THEN 2 ELSE 3 END,
                     descricao
        ) AS pendencias
    FROM pendentes
    GROUP BY cod_ibge
)
SELECT
    s.cod_ibge,
    COALESCE(a.n_graves,    0) AS n_graves,
    COALESCE(a.n_moderadas, 0) AS n_moderadas,
    COALESCE(a.n_leves,     0) AS n_leves,
    CASE
        WHEN a.cod_ibge IS NULL THEN 'REGULAR'
        ELSE a.pendencias
    END AS pendencias,
    CASE
        WHEN a.cod_ibge IS NULL
          OR (COALESCE(a.n_graves,0) + COALESCE(a.n_moderadas,0) + COALESCE(a.n_leves,0)) = 0
            THEN 0.0
        WHEN COALESCE(a.n_graves, 0) > 0
            THEN 1.0
        ELSE LEAST(
            (COALESCE(a.n_moderadas, 0) * 2.0 + COALESCE(a.n_leves, 0)) / 20.0,
            0.5
        )
    END AS ccauc
FROM {{ ref('stg_cauc') }} s
LEFT JOIN agregado a ON s.cod_ibge = a.cod_ibge
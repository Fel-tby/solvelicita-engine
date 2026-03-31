WITH source AS (
    SELECT * FROM {{ source('raw', 'cauc') }}
),
renamed AS (
    SELECT
        uf,
        municipio,
        CAST(cod_ibge   AS INT64)  AS cod_ibge,
        CAST(cod_siafi  AS INT64)  AS cod_siafi,
        regiao,
        CAST(populacao  AS INT64)  AS populacao,
        -- requisitos: mantém string ("!" = pendente, data = regular)
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
        req_siconfi_mcasp,
        COALESCE(
            SAFE.PARSE_DATE('%Y-%m-%d', SUBSTR(data_pesquisa, 1, 10)),
            SAFE.PARSE_DATE('%d/%m/%Y', SUBSTR(data_pesquisa, 1, 10))
        ) AS data_pesquisa,
        COALESCE(
            SAFE.PARSE_DATE('%Y-%m-%d', SUBSTR(data_coleta, 1, 10)),
            SAFE.PARSE_DATE('%d/%m/%Y', SUBSTR(data_coleta, 1, 10))
        ) AS data_coleta
    FROM source
    -- Garante que só o snapshot mais recente por município passe do staging
    QUALIFY ROW_NUMBER() OVER(
        PARTITION BY CAST(cod_ibge AS INT64) 
        ORDER BY data_coleta DESC, data_pesquisa DESC
    ) = 1
)
SELECT * FROM renamed

# Frontend Runtime Contract

This document defines the runtime boundary that the Next.js app depends on
today. Its purpose is to make a future split between `frontend` and
`pipeline/backend` straightforward without changing the live site behavior now.

## Scope

At runtime, the frontend depends on only three external inputs:

1. Supabase environment variables exposed to the browser.
2. A public dataset contract in the `municipios` table.
3. Static map artifacts published into the frontend workspace.

The frontend does not call Python code, `dbt`, `pipeline.py`, or BigQuery
directly at request time.

## Environment Variables

Defined in `frontend/.env.local`:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

These are consumed by `frontend/lib/supabase.js`.

## Supabase Data Contract

Current source:

- table: `public.municipios`

The frontend now selects only the columns below in
`frontend/lib/municipios.js`:

- `uf`
- `cod_ibge`
- `ente`
- `populacao`
- `score`
- `classificacao`
- `lliq_raw`
- `eorcam_raw`
- `rproc_pct_atual`
- `qsiconfi`
- `ccauc`
- `autonomia_media`
- `pendencias_cauc_json`
- `n_anos_cronicos`
- `dado_defasado`
- `dado_suspeito`
- `autonomia_critica`
- `n_licitacoes`
- `valor_homologado_total`
- `pct_dispensa`
- `alerta_dispensa`

### Required semantics

- `uf` must be a two-letter uppercase state code such as `PB` or `CE`.
- `cod_ibge` must be a 7-digit municipality IBGE identifier as text.
- `classificacao` must remain compatible with the frontend normalization logic:
  values containing `baixo`, `medio`, `alto`, `critico`, or `sem dados`.
- `qsiconfi` is expected as a 0-1 ratio and displayed as a percent in the UI.
- `pct_dispensa` is expected as a 0-1 ratio and displayed as a percent in the
  UI.
- `pendencias_cauc_json` is expected to be either null/empty or a JSON array.

### `pendencias_cauc_json` shape

When present, the frontend expects an array of objects compatible with:

```json
[
  {
    "codigo": "string",
    "descricao": "string",
    "gravidade": "GRAVE | MODERADA | LEVE"
  }
]
```

Unknown extra keys are safe. Missing `codigo`, `descricao`, or `gravidade`
degrade the UI quality for alert badges.

## Static Artifact Contract

The frontend also depends on published static map assets:

- `frontend/public/{uf}_geo.geojson`
- `frontend/lib/brazilMapData.js`

### State GeoJSON files

These files are fetched by the browser from `frontend/public` and are used in
the choropleth dashboard.

Current published files:

- `al_geo.geojson`
- `ba_geo.geojson`
- `ce_geo.geojson`
- `ma_geo.geojson`
- `pb_geo.geojson`
- `pe_geo.geojson`
- `pi_geo.geojson`
- `rn_geo.geojson`
- `se_geo.geojson`

Requirements:

- each feature must contain `properties.id`
- `properties.id` must match the municipality `cod_ibge`
- geometries must be valid GeoJSON consumable by Leaflet

Generator today:

- `src/utils/geojson_asset.py`

### Brazil landing-page asset

`frontend/lib/brazilMapData.js` powers the animated Brazil map on the landing
page.

Generator today:

- `src/utils/build_brazil_map_data.py`

## Current Supabase Schema Note

Based on the current SQL editor definition, the source table includes many more
columns than the frontend needs. That is fine. The frontend runtime contract is
the narrower list above, not the full table.

## Safe Split Target

When the repository split happens, the frontend should keep depending on only:

1. Supabase credentials
2. a stable public data contract
3. published static map artifacts

The pipeline repo should own data production. The frontend repo should own data
consumption and rendering.

## Recommended next backend step

Today the frontend reads directly from `public.municipios`. A future hardening
step is to expose a dedicated view such as `public.municipios_dashboard` with
exactly the columns above. That would let the pipeline evolve its internal table
shape with less risk to the site.

Suggested SQL for that future step:

```sql
create or replace view public.municipios_dashboard as
select
  uf,
  cod_ibge,
  ente,
  populacao,
  score,
  classificacao,
  lliq_raw,
  eorcam_raw,
  rproc_pct_atual,
  qsiconfi,
  ccauc,
  autonomia_media,
  pendencias_cauc_json,
  n_anos_cronicos,
  dado_defasado,
  dado_suspeito,
  autonomia_critica,
  n_licitacoes,
  valor_homologado_total,
  pct_dispensa,
  alerta_dispensa
from public.municipios;
```

## Runtime Dependencies

Para manter a futura divisao entre repositorios simples, o frontend hoje assume
somente estas dependencias externas:

- public Supabase credentials (`NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`)
- o contrato de dados publicado na tabela `municipios`
- os GeoJSONs publicados em `frontend/public/*_geo.geojson`
- o asset `frontend/lib/brazilMapData.js` usado no mapa da home

O contrato detalhado esta documentado em
[`docs/frontend-runtime-contract.md`](../docs/frontend-runtime-contract.md).

-- Limpeza de indices duplicados em public.municipios.
--
-- Rodar no Supabase SQL Editor.
-- Estes comandos preservam:
-- - municipios_pkey, chave primaria atual em cod_ibge;
-- - municipios_cod_ibge_uf_key, constraint UNIQUE em (cod_ibge, uf);
-- - municipios_uf_idx;
-- - municipios_score_desc_idx.
--
-- Observacao: o SQL Editor do Supabase pode executar o bloco dentro de uma
-- transacao. Por isso usamos DROP INDEX normal. A tabela atual tem poucos MB,
-- entao o lock deve ser muito breve.

-- 1) Diagnostico: confirme se algum indice candidato e constraint.
select
  i.relname as index_name,
  pg_get_indexdef(i.oid) as index_def,
  c.conname as backing_constraint
from pg_class i
join pg_index ix on ix.indexrelid = i.oid
join pg_class t on t.oid = ix.indrelid
left join pg_constraint c on c.conindid = i.oid
where t.relname = 'municipios'
  and t.relnamespace = 'public'::regnamespace
  and i.relname in (
    'municipios_score_idx',
    'municipios_score_desc_idx',
    'municipios_cod_ibge_uf_key',
    'municipios_cod_ibge_uf_uidx'
  )
order by i.relname;

-- 2) Limpeza: remove apenas os duplicados nao necessarios.
drop index if exists public.municipios_score_idx;
drop index if exists public.municipios_cod_ibge_uf_uidx;

-- 3) Conferencia final.
select
  indexname,
  indexdef
from pg_indexes
where schemaname = 'public'
  and tablename = 'municipios'
order by indexname;

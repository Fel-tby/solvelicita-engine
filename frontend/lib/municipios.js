import { supabase } from './supabase'
import { RISK_ORDER, normalizeRisk } from './risk'
import { UF_METADATA, UF_METADATA_BY_UF } from './siteData'

// Explicit frontend contract: these are the only Supabase columns required by
// the Next.js app at runtime today. Narrowing this query makes a future repo
// split safer without changing current site behavior.
export const MUNICIPIOS_SELECT_FIELDS = [
  'uf',
  'cod_ibge',
  'ente',
  'populacao',
  'score',
  'classificacao',
  'lliq_raw',
  'eorcam_raw',
  'rproc_pct_atual',
  'qsiconfi',
  'ccauc',
  'autonomia_media',
  'pendencias_cauc_json',
  'n_anos_cronicos',
  'dado_defasado',
  'dado_suspeito',
  'autonomia_critica',
  'n_licitacoes',
  'valor_homologado_total',
  'pct_dispensa',
  'alerta_dispensa',
]

const MUNICIPIOS_SELECT = MUNICIPIOS_SELECT_FIELDS.join(',')

const UF_CANDIDATE_KEYS = [
  'uf',
  'sigla_uf',
  'sg_uf',
  'estado_uf',
  'estado_sigla',
  'uf_ibge',
]

const SUPABASE_PAGE_SIZE = 1000

export function normalizeUf(value) {
  const text = String(value || '').trim().toUpperCase()
  return /^[A-Z]{2}$/.test(text) ? text : ''
}

export function inferUfFromRow(row) {
  if (!row || typeof row !== 'object') return ''

  for (const key of UF_CANDIDATE_KEYS) {
    const normalized = normalizeUf(row[key])
    if (normalized) return normalized
  }

  return ''
}

export async function fetchMunicipios() {
  const rows = []
  let from = 0

  while (true) {
    // Supabase REST limits unpaginated selects to 1000 rows by default.
    const { data, error } = await supabase
      .from('municipios')
      .select(MUNICIPIOS_SELECT)
      .order('cod_ibge', { ascending: true })
      .range(from, from + SUPABASE_PAGE_SIZE - 1)

    if (error) throw error

    const batch = Array.isArray(data) ? data : []
    rows.push(...batch)

    if (batch.length < SUPABASE_PAGE_SIZE) break
    from += SUPABASE_PAGE_SIZE
  }

  return rows
}

export async function fetchMunicipiosByUf(uf) {
  const normalizedUf = normalizeUf(uf)
  if (!normalizedUf) return []

  try {
    const { data, error } = await supabase
      .from('municipios')
      .select(MUNICIPIOS_SELECT)
      .eq('uf', normalizedUf)
      .order('cod_ibge', { ascending: true })

    if (error) throw error

    return Array.isArray(data) ? data : []
  } catch {
    const rows = await fetchMunicipios()
    return rows.filter((row) => inferUfFromRow(row) === normalizedUf)
  }
}

export async function fetchGeoJsonForUf(uf) {
  const normalizedUf = normalizeUf(uf)
  const candidates = [
    UF_METADATA_BY_UF[normalizedUf]?.geojsonPath,
    `/${normalizedUf.toLowerCase()}_geo.geojson`,
  ].filter(Boolean)

  for (const path of candidates) {
    const response = await fetch(path)
    if (response.ok) return response.json()
    if (response.status !== 404) {
      throw new Error(`Erro ao carregar o mapa de ${normalizedUf}.`)
    }
  }

  return null
}

export function buildStateSummaries(rows) {
  const grouped = new Map()

  rows.forEach((row) => {
    const uf = inferUfFromRow(row)
    if (!uf) return

    const canonicalRisk = normalizeRisk(row.classificacao)
    const bucket = grouped.get(uf) || {
      total: 0,
      baixo: 0,
      medio: 0,
      alto: 0,
      critico: 0,
      sem_dados: 0,
    }

    bucket.total += 1
    bucket[canonicalRisk] += 1
    grouped.set(uf, bucket)
  })

  return UF_METADATA.map((meta) => {
    const summary = grouped.get(meta.uf)
    const hasData = Boolean(summary?.total)

    return {
      ...meta,
      hasData,
      total: summary?.total || meta.municipios || 0,
      baixo: summary?.baixo || 0,
      medio: summary?.medio || 0,
      alto: summary?.alto || 0,
      critico: summary?.critico || 0,
      sem_dados: summary?.sem_dados || 0,
    }
  })
}

export function getStateName(uf) {
  return UF_METADATA_BY_UF[normalizeUf(uf)]?.nome || normalizeUf(uf)
}

export function getRiskSegments(summary) {
  return RISK_ORDER.map((riskKey) => ({
    key: riskKey,
    value: summary?.[riskKey] || 0,
  }))
}

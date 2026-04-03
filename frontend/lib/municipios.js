import { supabase } from './supabase'
import { RISK_ORDER, normalizeRisk } from './risk'
import { UF_METADATA, UF_METADATA_BY_UF } from './siteData'

const UF_CANDIDATE_KEYS = [
  'uf',
  'sigla_uf',
  'sg_uf',
  'estado_uf',
  'estado_sigla',
  'uf_ibge',
]

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
  const { data, error } = await supabase.from('municipios').select('*')
  if (error) throw error
  return Array.isArray(data) ? data : []
}

export async function fetchMunicipiosByUf(uf) {
  const normalizedUf = normalizeUf(uf)
  const rows = await fetchMunicipios()
  return rows.filter((row) => inferUfFromRow(row) === normalizedUf)
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

export const RISK_ORDER = ['baixo', 'medio', 'alto', 'critico', 'sem_dados']

function normalizeText(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

export function normalizeRisk(value) {
  const text = normalizeText(value)

  if (text.includes('sem dados')) return 'sem_dados'
  if (text.includes('s/d')) return 'sem_dados'
  if (text.includes('baixo')) return 'baixo'
  if (text.includes('medio')) return 'medio'
  if (text.includes('alto')) return 'alto'
  if (text.includes('critico')) return 'critico'
  return 'sem_dados'
}

export function getRiskMeta(value) {
  const risk = normalizeRisk(value)

  if (risk === 'baixo') {
    return { shortLabel: 'BAIXO', longLabel: 'Risco Baixo', color: 'var(--green)' }
  }

  if (risk === 'medio') {
    return { shortLabel: 'MÉDIO', longLabel: 'Risco Médio', color: 'var(--yellow)' }
  }

  if (risk === 'alto') {
    return { shortLabel: 'ALTO', longLabel: 'Risco Alto', color: 'var(--red)' }
  }

  if (risk === 'critico') {
    return { shortLabel: 'CRÍTICO', longLabel: 'Crítico', color: '#a01010' }
  }

  return { shortLabel: 'S/D', longLabel: 'Sem Dados', color: 'var(--gray)' }
}

export function getRiskLongLabel(value) {
  return getRiskMeta(value).longLabel
}

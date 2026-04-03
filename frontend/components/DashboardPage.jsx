import { useCallback, useEffect, useMemo, useState } from 'react'
import dynamic from 'next/dynamic'
import { fetchGeoJsonForUf, fetchMunicipiosByUf, getStateName, normalizeUf } from '../lib/municipios'

const MapaCoropletico = dynamic(() => import('./MapaCoropletico'), {
  ssr: false,
  loading: () => (
    <div
      style={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-lo)',
        fontFamily: 'var(--mono)',
        fontSize: '0.75rem',
        letterSpacing: '0.1em',
      }}
    >
      CARREGANDO MAPA...
    </div>
  ),
})

const ORDEM_RISCO = ['baixo', 'medio', 'alto', 'critico', 'sem_dados']

const CORES_RISCO = {
  baixo: 'var(--risk-baixo)',
  medio: 'var(--risk-medio)',
  alto: 'var(--risk-alto)',
  critico: 'var(--risk-critico)',
  sem_dados: 'var(--risk-nd)',
}

const LABEL_RISCO = {
  baixo: 'BAIXO',
  medio: 'MEDIO',
  alto: 'ALTO',
  critico: 'CRITICO',
  sem_dados: 'S/D',
}

const LABEL_RISCO_LONGO = {
  baixo: 'Risco Baixo',
  medio: 'Risco Medio',
  alto: 'Risco Alto',
  critico: 'Critico',
  sem_dados: 'Sem Dados',
}

const COLUNAS = [
  { key: '#', label: '#', field: null },
  { key: 'ente', label: 'Municipio', field: 'ente' },
  { key: 'score', label: 'Score', field: 'score' },
  { key: 'class', label: 'Risco', field: 'classificacao_canonica' },
  { key: 'pop', label: 'Pop.', field: 'populacao' },
  { key: 'eorcam', label: 'Exec.Orc.%', field: 'eorcam_raw' },
  { key: 'rproc', label: 'RP Proc.', field: 'n_anos_cronicos' },
  { key: 'siconfi', label: 'SICONFI', field: 'qsiconfi' },
  { key: 'cauc', label: 'CAUC', field: 'ccauc' },
  { key: 'lliq', label: 'Lliq', field: 'lliq_raw' },
  { key: 'autonomia', label: 'Autonomia', field: 'autonomia_media' },
  { key: 'licit', label: 'Licitacoes', field: 'n_licitacoes' },
  { key: 'valor', label: 'Val.Homolog.', field: 'valor_homologado_total' },
  { key: 'dispensa', label: '% Dispensa', field: 'pct_dispensa' },
  { key: 'alertas', label: 'Alertas', field: null },
]

const PREVIEW_LINHAS = 10

function normalizeText(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

function normalizeClassificacao(value) {
  const text = normalizeText(value)
  if (text.includes('sem dados') || text.includes('s/d')) return 'sem_dados'
  if (text.includes('baixo')) return 'baixo'
  if (text.includes('medio')) return 'medio'
  if (text.includes('alto')) return 'alto'
  if (text.includes('critico')) return 'critico'
  return 'sem_dados'
}

function ordemRiscoIndex(value) {
  return ORDEM_RISCO.indexOf(normalizeClassificacao(value))
}

function corPorScore(score) {
  if (score == null || Number.isNaN(Number(score))) return 'var(--risk-nd)'
  if (Number(score) >= 80) return 'var(--risk-baixo)'
  if (Number(score) >= 60) return 'var(--risk-medio)'
  if (Number(score) >= 40) return 'var(--risk-alto)'
  return 'var(--risk-critico)'
}

function fmtNum(value, decimals = 1) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(decimals)
}

function fmtPct(value, decimals = 1) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  return `${Number(value).toFixed(decimals)}%`
}

function fmtBRL(value) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  if (value >= 1e9) return `R$ ${(value / 1e9).toFixed(1)} bi`
  if (value >= 1e6) return `R$ ${(value / 1e6).toFixed(1)} mi`
  return `R$ ${Number(value).toLocaleString('pt-BR')}`
}

function mediana(values) {
  const sorted = values
    .filter((value) => value != null && !Number.isNaN(Number(value)))
    .map(Number)
    .sort((left, right) => left - right)

  if (!sorted.length) return null

  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

function BadgeRisco({ classe }) {
  const risco = normalizeClassificacao(classe)
  const cor = CORES_RISCO[risco] || 'var(--risk-nd)'

  return (
    <span
      style={{
        display: 'inline-block',
        padding: '1px 6px',
        borderRadius: '2px',
        fontSize: '0.68rem',
        fontFamily: 'var(--mono)',
        fontWeight: 700,
        letterSpacing: '0.06em',
        color: cor,
        background: `${cor}22`,
        border: `1px solid ${cor}44`,
      }}
    >
      {LABEL_RISCO[risco] || 'S/D'}
    </span>
  )
}

function AlertaBadge({ label, cor = '#f59e0b' }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '3px',
        padding: '1px 5px',
        borderRadius: '2px',
        fontSize: '0.62rem',
        fontFamily: 'var(--mono)',
        fontWeight: 700,
        color: cor,
        background: `${cor}18`,
        border: `1px solid ${cor}33`,
      }}
    >
      ! {label}
    </span>
  )
}

function KPI({ label, value, destaque }) {
  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-dim)',
        borderTop: `3px solid ${destaque || 'var(--border-dim)'}`,
        padding: '8px 10px',
        borderRadius: '3px',
        flex: 1,
        minWidth: 0,
      }}
    >
      <div
        style={{
          fontSize: '0.55rem',
          color: 'var(--text-lo)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          fontFamily: 'var(--mono)',
          marginBottom: '3px',
          lineHeight: 1.3,
          wordBreak: 'break-word',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: '1.3rem',
          fontWeight: 700,
          color: 'var(--text-hi)',
          fontFamily: 'var(--mono)',
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
    </div>
  )
}

function PainelTitulo({ children }) {
  return (
    <div
      style={{
        fontSize: '0.6rem',
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        color: 'var(--text-lo)',
        fontFamily: 'var(--mono)',
        paddingBottom: '7px',
        marginBottom: '9px',
        borderBottom: '1px solid var(--border-dim)',
      }}
    >
      {children}
    </div>
  )
}

function Painel({ children, style }) {
  return (
    <div
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-dim)',
        borderRadius: '3px',
        padding: '12px 14px',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

function getMunicipioAlertas(municipio) {
  const alertas = []
  if (municipio.alerta_dispensa) alertas.push({ label: 'DISPENSA', cor: '#ef4444' })
  if (municipio.dado_suspeito) alertas.push({ label: 'SUSPEITO', cor: '#f59e0b' })
  if (municipio.autonomia_critica) alertas.push({ label: 'AUT. CRITICA', cor: '#f59e0b' })
  if (Number(municipio.n_anos_cronicos) >= 5) alertas.push({ label: 'RP CRONICO', cor: '#ef4444' })
  if (municipio.dado_defasado) alertas.push({ label: 'DEFASADO', cor: '#64748b' })
  return alertas
}

function MunicipioSelecionado({ municipio }) {
  if (!municipio) {
    return (
      <Painel>
        <PainelTitulo>Municipio Selecionado</PainelTitulo>
        <div
          style={{
            color: 'var(--text-lo)',
            fontFamily: 'var(--mono)',
            fontSize: '0.72rem',
            lineHeight: 1.8,
          }}
        >
          Clique em um municipio no mapa ou na tabela para ver os indicadores detalhados.
        </div>
      </Painel>
    )
  }

  const risco = normalizeClassificacao(municipio.classificacao)
  const blocos = [
    ['Score', municipio.score != null ? Number(municipio.score).toFixed(1) : '-'],
    ['Risco', LABEL_RISCO_LONGO[risco]],
    ['Populacao', municipio.populacao?.toLocaleString('pt-BR') || '-'],
    ['Exec. Orcamentaria', fmtPct(municipio.eorcam_raw)],
    ['RP Processados', municipio.n_anos_cronicos != null ? `${municipio.n_anos_cronicos}a` : '-'],
    ['SICONFI', municipio.qsiconfi != null ? fmtPct(Number(municipio.qsiconfi) * 100, 0) : '-'],
    ['CAUC', fmtNum(municipio.ccauc, 2)],
    ['Lliq', fmtNum(municipio.lliq_raw, 3)],
    ['Autonomia', fmtNum(municipio.autonomia_media, 3)],
    ['Licitacoes', municipio.n_licitacoes?.toLocaleString('pt-BR') || '-'],
    ['Valor homologado', fmtBRL(municipio.valor_homologado_total)],
    ['% Dispensa', municipio.pct_dispensa != null ? fmtPct(Number(municipio.pct_dispensa) * 100) : '-'],
  ]

  return (
    <Painel>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '10px',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '10px',
        }}
      >
        <div>
          <PainelTitulo>Municipio Selecionado</PainelTitulo>
          <div
            style={{
              fontSize: '1rem',
              color: 'var(--text-hi)',
              fontWeight: 700,
              fontFamily: 'var(--mono)',
              letterSpacing: '0.04em',
            }}
          >
            {municipio.ente}
          </div>
        </div>
        <BadgeRisco classe={municipio.classificacao} />
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
          gap: '8px',
        }}
      >
        {blocos.map(([label, value]) => (
          <div
            key={label}
            style={{
              padding: '8px 9px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-dim)',
              borderRadius: '3px',
            }}
          >
            <div
              style={{
                fontSize: '0.58rem',
                color: 'var(--text-lo)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                fontFamily: 'var(--mono)',
                marginBottom: '4px',
              }}
            >
              {label}
            </div>
            <div
              style={{
                fontSize: '0.78rem',
                color: 'var(--text-hi)',
                fontFamily: 'var(--mono)',
                fontWeight: 600,
                lineHeight: 1.4,
              }}
            >
              {value}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '10px' }}>
        {getMunicipioAlertas(municipio).map((alerta) => (
          <AlertaBadge key={alerta.label} label={alerta.label} cor={alerta.cor} />
        ))}
      </div>
    </Painel>
  )
}

export default function DashboardPage({ uf }) {
  const normalizedUf = normalizeUf(uf)
  const [municipios, setMunicipios] = useState([])
  const [geoData, setGeoData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState(null)
  const [filtroRisco, setFiltroRisco] = useState(new Set(ORDEM_RISCO))
  const [scoreRange, setScoreRange] = useState([0, 100])
  const [busca, setBusca] = useState('')
  const [munSelecionado, setMunSelecionado] = useState(null)
  const [sortField, setSortField] = useState('classificacao_canonica')
  const [sortAsc, setSortAsc] = useState(true)
  const [tabelaExpandida, setTabelaExpandida] = useState(false)
  const [sidebarAberta, setSidebarAberta] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    function checar() {
      setIsMobile(window.innerWidth < 768)
    }

    checar()
    window.addEventListener('resize', checar)
    return () => window.removeEventListener('resize', checar)
  }, [])

  useEffect(() => {
    let ativo = true

    async function carregar() {
      setLoading(true)
      setErro(null)

      try {
        const [rows, geo] = await Promise.all([
          fetchMunicipiosByUf(normalizedUf),
          fetchGeoJsonForUf(normalizedUf),
        ])

        if (!ativo) return

        const enriquecidos = rows.map((item) => ({
          ...item,
          classificacao_canonica: normalizeClassificacao(item.classificacao),
        }))

        setMunicipios(enriquecidos)
        setGeoData(geo)
      } catch (error) {
        if (ativo) {
          setErro(error.message || 'Erro ao carregar dados.')
        }
      } finally {
        if (ativo) {
          setLoading(false)
        }
      }
    }

    carregar()

    return () => {
      ativo = false
    }
  }, [normalizedUf])

  useEffect(() => {
    if (!munSelecionado) return
    const proximo = municipios.find((item) => item.cod_ibge === munSelecionado.cod_ibge) || null
    setMunSelecionado(proximo)
  }, [municipios, munSelecionado])

  const handleSort = useCallback((field) => {
    if (!field) return

    setSortField((anterior) => {
      if (anterior === field) {
        setSortAsc((valor) => !valor)
        return field
      }

      setSortAsc(true)
      return field
    })
  }, [])

  const municipiosFiltrados = useMemo(() => {
    const filtrados = municipios.filter((municipio) => {
      const risco = municipio.classificacao_canonica || 'sem_dados'

      if (!filtroRisco.has(risco)) return false
      if (municipio.score != null && (municipio.score < scoreRange[0] || municipio.score > scoreRange[1])) return false
      if (busca.trim() && !municipio.ente?.toLowerCase().includes(busca.trim().toLowerCase())) return false

      return true
    })

    return [...filtrados].sort((left, right) => {
      if (sortField === 'classificacao_canonica') {
        const indexLeft = ordemRiscoIndex(left.classificacao_canonica)
        const indexRight = ordemRiscoIndex(right.classificacao_canonica)

        if (indexLeft !== indexRight) {
          return sortAsc ? indexLeft - indexRight : indexRight - indexLeft
        }

        return (Number(right.score) || -1) - (Number(left.score) || -1)
      }

      const valueLeft = left[sortField]
      const valueRight = right[sortField]

      if (valueLeft == null && valueRight == null) return 0
      if (valueLeft == null) return 1
      if (valueRight == null) return -1

      if (typeof valueLeft === 'string') {
        return sortAsc
          ? valueLeft.localeCompare(valueRight, 'pt-BR')
          : valueRight.localeCompare(valueLeft, 'pt-BR')
      }

      return sortAsc ? valueLeft - valueRight : valueRight - valueLeft
    })
  }, [municipios, filtroRisco, scoreRange, busca, sortField, sortAsc])

  const ibgesFiltrados = useMemo(
    () => new Set(municipiosFiltrados.map((municipio) => String(municipio.cod_ibge))),
    [municipiosFiltrados],
  )

  const comScore = useMemo(
    () => municipios.filter((municipio) => municipio.score != null && !Number.isNaN(Number(municipio.score))),
    [municipios],
  )

  const mediaEstado = useMemo(() => {
    if (!comScore.length) return null
    return comScore.reduce((total, municipio) => total + Number(municipio.score), 0) / comScore.length
  }, [comScore])

  const medianaEstado = useMemo(() => mediana(comScore.map((municipio) => municipio.score)), [comScore])

  const nBaixo = useMemo(
    () => municipios.filter((municipio) => municipio.classificacao_canonica === 'baixo').length,
    [municipios],
  )

  const nAlto = useMemo(
    () =>
      municipios.filter((municipio) =>
        ['alto', 'critico'].includes(municipio.classificacao_canonica),
      ).length,
    [municipios],
  )

  const nAlertas = useMemo(
    () =>
      municipios.filter(
        (municipio) =>
          municipio.alerta_dispensa ||
          municipio.dado_suspeito ||
          municipio.autonomia_critica ||
          municipio.dado_defasado ||
          Number(municipio.n_anos_cronicos) >= 5,
      ).length,
    [municipios],
  )

  const distribuicao = useMemo(() => {
    const contagem = { baixo: 0, medio: 0, alto: 0, critico: 0, sem_dados: 0 }

    municipios.forEach((municipio) => {
      const risco = municipio.classificacao_canonica || 'sem_dados'
      contagem[risco] += 1
    })

    return contagem
  }, [municipios])

  const medianas = useMemo(
    () => ({
      'Exec. Orcamentaria (%)': fmtPct(mediana(municipios.map((municipio) => municipio.eorcam_raw))),
      'RP Processados (contrib.)': fmtNum(mediana(municipios.map((municipio) => municipio.contrib_rproc)), 2),
      'Conformidade SICONFI':
        mediana(municipios.map((municipio) => municipio.qsiconfi)) != null
          ? fmtPct(mediana(municipios.map((municipio) => municipio.qsiconfi)) * 100, 0)
          : '-',
      'Lliq / Rec. (RGF A05)': fmtNum(mediana(municipios.map((municipio) => municipio.lliq_raw)), 3),
      'Autonomia Tributaria': fmtNum(mediana(municipios.map((municipio) => municipio.autonomia_media)), 3),
    }),
    [municipios],
  )

  const alertas = useMemo(
    () => ({
      dispensa: municipios.filter((municipio) => municipio.alerta_dispensa).length,
      suspeito: municipios.filter((municipio) => municipio.dado_suspeito).length,
      autonomia: municipios.filter((municipio) => municipio.autonomia_critica).length,
      cronicos: municipios.filter((municipio) => Number(municipio.n_anos_cronicos) >= 5).length,
      defasado: municipios.filter((municipio) => municipio.dado_defasado).length,
    }),
    [municipios],
  )

  const toggleRisco = useCallback((classe) => {
    setFiltroRisco((anterior) => {
      const proximo = new Set(anterior)
      if (proximo.has(classe)) proximo.delete(classe)
      else proximo.add(classe)
      return proximo
    })
  }, [])

  if (loading) {
    return (
      <div
        style={{
          minHeight: 'calc(100vh - 56px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#06090f',
          color: 'var(--text-lo)',
          fontFamily: 'var(--mono)',
          fontSize: '0.75rem',
          letterSpacing: '0.12em',
        }}
      >
        CARREGANDO DADOS...
      </div>
    )
  }

  if (erro) {
    return (
      <div
        style={{
          minHeight: 'calc(100vh - 56px)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          background: '#06090f',
          color: 'var(--risk-alto)',
          fontFamily: 'var(--mono)',
          fontSize: '0.8rem',
        }}
      >
        <span>ERRO AO CARREGAR DADOS</span>
        <span style={{ color: 'var(--text-lo)', fontSize: '0.7rem' }}>{erro}</span>
      </div>
    )
  }

  const SidebarConteudo = () => (
    <>
      <div
        style={{
          marginBottom: '18px',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
        }}
      >
        <div />
        {isMobile ? (
          <button
            onClick={() => setSidebarAberta(false)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-lo)',
              fontSize: '1.1rem',
              cursor: 'pointer',
              padding: 0,
              lineHeight: 1,
            }}
          >
            x
          </button>
        ) : null}
      </div>

      <div style={{ borderTop: '1px solid var(--border-dim)', paddingTop: '12px' }}>
        <div
          style={{
            fontSize: '0.58rem',
            color: 'var(--text-lo)',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            fontFamily: 'var(--mono)',
            marginBottom: '7px',
          }}
        >
          Classificacao
        </div>
        {ORDEM_RISCO.map((classe) => {
          const ativo = filtroRisco.has(classe)
          const cor = CORES_RISCO[classe]

          return (
            <div
              key={classe}
              onClick={() => toggleRisco(classe)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '7px',
                padding: '4px 6px',
                borderRadius: '2px',
                cursor: 'pointer',
                marginBottom: '2px',
                background: ativo ? `${cor}14` : 'transparent',
                border: `1px solid ${ativo ? `${cor}44` : 'transparent'}`,
                opacity: ativo ? 1 : 0.35,
                transition: 'all 0.15s',
              }}
            >
              <div
                style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  background: ativo ? cor : 'var(--text-lo)',
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: '0.68rem',
                  color: ativo ? 'var(--text-hi)' : 'var(--text-lo)',
                  fontFamily: 'var(--mono)',
                }}
              >
                {LABEL_RISCO[classe]}
              </span>
              <span
                style={{
                  marginLeft: 'auto',
                  fontSize: '0.62rem',
                  color: 'var(--text-lo)',
                  fontFamily: 'var(--mono)',
                }}
              >
                {distribuicao[classe] || 0}
              </span>
            </div>
          )
        })}
      </div>

      <div style={{ borderTop: '1px solid var(--border-dim)', paddingTop: '12px', marginTop: '10px' }}>
        <div
          style={{
            fontSize: '0.58rem',
            color: 'var(--text-lo)',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            fontFamily: 'var(--mono)',
            marginBottom: '5px',
          }}
        >
          Score
        </div>
        <div
          style={{
            fontSize: '0.62rem',
            color: 'var(--text-mid)',
            marginBottom: '3px',
            fontFamily: 'var(--mono)',
          }}
        >
          {scoreRange[0]} - {scoreRange[1]}
        </div>
        <input
          type="range"
          min="0"
          max="100"
          value={scoreRange[0]}
          onChange={(event) => setScoreRange([Number(event.target.value), scoreRange[1]])}
          style={{ width: '100%', marginBottom: '3px', accentColor: 'var(--accent)' }}
        />
        <input
          type="range"
          min="0"
          max="100"
          value={scoreRange[1]}
          onChange={(event) => setScoreRange([scoreRange[0], Number(event.target.value)])}
          style={{ width: '100%', accentColor: 'var(--accent)' }}
        />
      </div>

      <div style={{ borderTop: '1px solid var(--border-dim)', paddingTop: '12px', marginTop: '10px' }}>
        <div
          style={{
            fontSize: '0.58rem',
            color: 'var(--text-lo)',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            fontFamily: 'var(--mono)',
            marginBottom: '5px',
          }}
        >
          Municipio
        </div>
        <input
          type="text"
          placeholder="Ex: Campina Grande"
          value={busca}
          onChange={(event) => setBusca(event.target.value)}
          style={{
            width: '100%',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-dim)',
            borderRadius: '2px',
            padding: '5px 7px',
            color: 'var(--text-hi)',
            fontSize: '0.7rem',
            fontFamily: 'var(--mono)',
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
      </div>

    </>
  )

  return (
    <>
      {isMobile && sidebarAberta ? (
        <div
          onClick={() => setSidebarAberta(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.6)',
            zIndex: 99,
          }}
        />
      ) : null}

      {isMobile ? (
        <aside
          style={{
            position: 'fixed',
            top: '56px',
            left: 0,
            bottom: 0,
            width: '240px',
            background: '#080b11',
            borderRight: '1px solid var(--border-dim)',
            display: 'flex',
            flexDirection: 'column',
            padding: '16px 14px',
            overflowY: 'auto',
            transform: sidebarAberta ? 'translateX(0)' : 'translateX(-100%)',
            transition: 'transform 0.25s ease',
            zIndex: 100,
          }}
        >
          <SidebarConteudo />
        </aside>
      ) : null}

      <div
        style={{
          display: 'flex',
          minHeight: 'calc(100vh - 56px)',
          background: '#06090f',
          borderTop: '1px solid var(--border-dim)',
        }}
      >
        {!isMobile ? (
          <aside
            style={{
              width: '195px',
              minWidth: '195px',
              background: '#080b11',
              borderRight: '1px solid var(--border-dim)',
              display: 'flex',
              flexDirection: 'column',
              padding: '16px 14px',
              overflowY: 'auto',
            }}
          >
            <SidebarConteudo />
          </aside>
        ) : null}

        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            overflowX: 'hidden',
            padding: isMobile ? '12px' : '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            minWidth: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {isMobile ? (
              <button
                onClick={() => setSidebarAberta(true)}
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-dim)',
                  borderRadius: '3px',
                  color: 'var(--text-hi)',
                  cursor: 'pointer',
                  padding: '6px 10px',
                  fontSize: '1rem',
                  flexShrink: 0,
                }}
              >
                ≡
              </button>
            ) : null}

            <div style={{ borderLeft: '3px solid var(--accent)', paddingLeft: '11px', minWidth: 0 }}>
              <h1
                style={{
                  fontSize: isMobile ? '0.85rem' : '1rem',
                  fontWeight: 700,
                  color: 'var(--text-hi)',
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                  fontFamily: 'var(--mono)',
                  margin: 0,
                }}
              >
                Capacidade de Pagamento - {getStateName(normalizedUf)}
              </h1>
              <p
                style={{
                  fontSize: '0.62rem',
                  color: 'var(--text-lo)',
                  fontFamily: 'var(--mono)',
                  marginTop: '2px',
                  marginBottom: 0,
                }}
              >
                SCORE DE SOLVENCIA · {municipios.length} MUNICIPIOS · REFERENCIA 2020-2025
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <KPI label={`Score medio ${normalizedUf}`} value={mediaEstado ? mediaEstado.toFixed(1) : '-'} />
            <KPI label="Score mediano" value={medianaEstado ? medianaEstado.toFixed(1) : '-'} />
            <KPI label="Risco baixo" value={nBaixo} destaque="var(--risk-baixo)" />
            <KPI label="Alto + Critico" value={nAlto} destaque="var(--risk-alto)" />
            <KPI label="Alertas ativos" value={nAlertas} destaque="#f59e0b" />
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: isMobile ? 'column' : 'row',
              gap: '10px',
              height: isMobile ? 'auto' : '480px',
              minHeight: isMobile ? 'auto' : '480px',
            }}
          >
            <div
              style={{
                flex: isMobile ? 'none' : '1 1 0',
                height: isMobile ? '320px' : '100%',
                minWidth: 0,
                background: 'var(--bg-panel)',
                border: '1px solid var(--border-dim)',
                borderRadius: '3px',
                overflow: 'hidden',
                position: 'relative',
                zIndex: 0,
              }}
            >
              {geoData ? (
                <MapaCoropletico
                  geoData={geoData}
                  municipios={municipios}
                  ibgesFiltrados={ibgesFiltrados}
                  corPorScore={corPorScore}
                  onSelect={setMunSelecionado}
                />
              ) : (
                <div
                  style={{
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-lo)',
                    fontFamily: 'var(--mono)',
                    fontSize: '0.72rem',
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                  }}
                >
                  MAPA NAO DISPONIVEL PARA {normalizedUf}
                </div>
              )}
            </div>

            <div
              style={{
                width: isMobile ? '100%' : '270px',
                minWidth: isMobile ? 'unset' : '270px',
                display: 'flex',
                flexDirection: isMobile ? 'row' : 'column',
                flexWrap: isMobile ? 'wrap' : 'nowrap',
                gap: '8px',
                overflowY: isMobile ? 'visible' : 'auto',
              }}
            >
              <Painel style={{ flex: isMobile ? '1 1 100%' : 'none' }}>
                <PainelTitulo>Distribuicao por Faixa de Risco</PainelTitulo>
                {ORDEM_RISCO.map((classe) => {
                  const total = municipios.length || 1
                  const quantidade = distribuicao[classe] || 0
                  const percentual = (quantidade / total) * 100
                  const cor = CORES_RISCO[classe]

                  return (
                    <div
                      key={classe}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '7px',
                        padding: '3px 0',
                        borderBottom: '1px solid var(--border-dim)',
                        fontFamily: 'var(--mono)',
                        fontSize: '0.7rem',
                      }}
                    >
                      <span style={{ color: cor, minWidth: '48px' }}>{LABEL_RISCO[classe]}</span>
                      <div
                        style={{
                          flex: 1,
                          background: 'var(--bg-card)',
                          borderRadius: '2px',
                          height: '5px',
                        }}
                      >
                        <div
                          style={{
                            width: `${percentual}%`,
                            height: '5px',
                            background: cor,
                            borderRadius: '2px',
                            transition: 'width 0.4s',
                          }}
                        />
                      </div>
                      <span style={{ color: 'var(--text-mid)', minWidth: '22px', textAlign: 'right' }}>
                        {quantidade}
                      </span>
                      <span style={{ color: 'var(--text-lo)', minWidth: '30px', textAlign: 'right' }}>
                        {percentual.toFixed(0)}%
                      </span>
                    </div>
                  )
                })}
              </Painel>

              <Painel style={{ flex: isMobile ? '1 1 calc(50% - 4px)' : 'none' }}>
                <PainelTitulo>Indicadores - Mediana Estadual</PainelTitulo>
                {Object.entries(medianas).map(([label, value]) => (
                  <div
                    key={label}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '4px 0',
                      borderBottom: '1px solid var(--border-dim)',
                      fontFamily: 'var(--mono)',
                      fontSize: '0.7rem',
                      gap: '10px',
                    }}
                  >
                    <span style={{ color: 'var(--text-lo)' }}>{label}</span>
                    <span style={{ color: 'var(--text-hi)', fontWeight: 600 }}>{value}</span>
                  </div>
                ))}
              </Painel>

              <Painel style={{ flex: isMobile ? '1 1 calc(50% - 4px)' : 'none' }}>
                <PainelTitulo>Alertas por Tipo</PainelTitulo>
                {[
                  { label: 'Dispensa > 30%', value: alertas.dispensa, cor: '#ef4444' },
                  { label: 'Dado suspeito', value: alertas.suspeito, cor: '#f59e0b' },
                  { label: 'Autonomia critica', value: alertas.autonomia, cor: '#f59e0b' },
                  { label: 'RP cronico (>=5 anos)', value: alertas.cronicos, cor: '#ef4444' },
                  { label: 'Dado defasado', value: alertas.defasado, cor: '#64748b' },
                ].map((item) => (
                  <div
                    key={item.label}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '4px 0',
                      borderBottom: '1px solid var(--border-dim)',
                      gap: '10px',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '0.68rem',
                        color: 'var(--text-lo)',
                        fontFamily: 'var(--mono)',
                      }}
                    >
                      {item.label}
                    </span>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        fontFamily: 'var(--mono)',
                        color: item.value > 0 ? item.cor : 'var(--text-lo)',
                      }}
                    >
                      {item.value}
                    </span>
                  </div>
                ))}
              </Painel>
            </div>
          </div>

          <MunicipioSelecionado municipio={munSelecionado} />

          <div
            style={{
              flexShrink: 0,
              background: 'var(--bg-panel)',
              border: '1px solid var(--border-dim)',
              borderRadius: '3px',
              overflow: 'auto',
            }}
          >
            <div
              style={{
                padding: '7px 12px',
                borderBottom: '1px solid var(--border-dim)',
                fontSize: '0.6rem',
                color: 'var(--text-lo)',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                fontFamily: 'var(--mono)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '10px',
              }}
            >
              <span>
                Ranking - {tabelaExpandida ? municipiosFiltrados.length : Math.min(PREVIEW_LINHAS, municipiosFiltrados.length)} de{' '}
                {municipiosFiltrados.length} municipios
              </span>
              {!isMobile ? (
                <span style={{ color: 'var(--text-lo)' }}>
                  clique nas colunas para ordenar
                  {busca ? <span style={{ color: 'var(--accent)', marginLeft: '8px' }}>filtrado: "{busca}"</span> : null}
                </span>
              ) : null}
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.73rem' }}>
              <thead>
                <tr style={{ background: 'var(--bg-card)' }}>
                  {COLUNAS.map((coluna) => {
                    const ativo = sortField === coluna.field
                    const clicavel = coluna.field !== null

                    return (
                      <th
                        key={coluna.key}
                        onClick={() => {
                          if (clicavel) handleSort(coluna.field)
                        }}
                        style={{
                          padding: '6px 9px',
                          textAlign: 'left',
                          color: ativo ? 'var(--text-hi)' : 'var(--text-lo)',
                          fontWeight: 600,
                          fontSize: '0.6rem',
                          letterSpacing: '0.06em',
                          textTransform: 'uppercase',
                          fontFamily: 'var(--mono)',
                          borderBottom: `1px solid ${ativo ? 'var(--accent)' : 'var(--border-dim)'}`,
                          whiteSpace: 'nowrap',
                          cursor: clicavel ? 'pointer' : 'default',
                          userSelect: 'none',
                          transition: 'color 0.1s',
                        }}
                      >
                        {coluna.label}
                        {ativo ? <span style={{ marginLeft: '4px', opacity: 0.7 }}>{sortAsc ? '↑' : '↓'}</span> : null}
                      </th>
                    )
                  })}
                </tr>
              </thead>

              <tbody>
                {(tabelaExpandida ? municipiosFiltrados : municipiosFiltrados.slice(0, PREVIEW_LINHAS)).map((municipio, index) => {
                  const alertasMunicipio = getMunicipioAlertas(municipio)

                  return (
                    <tr
                      key={municipio.cod_ibge || `${municipio.ente}-${index}`}
                      onClick={() => setMunSelecionado(municipio)}
                      style={{
                        borderBottom: '1px solid var(--border-dim)',
                        cursor: 'pointer',
                        background:
                          munSelecionado?.cod_ibge === municipio.cod_ibge ? 'rgba(59,91,219,0.12)' : 'transparent',
                        transition: 'background 0.1s',
                      }}
                    >
                      <td style={{ padding: '5px 9px', color: 'var(--text-lo)', fontFamily: 'var(--mono)' }}>
                        {index + 1}
                      </td>
                      <td style={{ padding: '5px 9px', color: 'var(--text-hi)', fontWeight: 500, whiteSpace: 'nowrap' }}>
                        {municipio.ente}
                      </td>
                      <td
                        style={{
                          padding: '5px 9px',
                          fontFamily: 'var(--mono)',
                          color: corPorScore(municipio.score),
                          fontWeight: 700,
                        }}
                      >
                        {municipio.score != null ? Number(municipio.score).toFixed(1) : '-'}
                      </td>
                      <td style={{ padding: '5px 9px' }}>
                        <BadgeRisco classe={municipio.classificacao} />
                      </td>
                      <td style={{ padding: '5px 9px', color: 'var(--text-mid)', fontFamily: 'var(--mono)' }}>
                        {municipio.populacao?.toLocaleString('pt-BR') || '-'}
                      </td>
                      <td style={{ padding: '5px 9px', color: 'var(--text-mid)', fontFamily: 'var(--mono)' }}>
                        {fmtPct(municipio.eorcam_raw)}
                      </td>
                      <td
                        style={{
                          padding: '5px 9px',
                          fontFamily: 'var(--mono)',
                          color: Number(municipio.n_anos_cronicos) >= 5 ? '#ef4444' : 'var(--text-mid)',
                        }}
                      >
                        {municipio.n_anos_cronicos != null ? `${municipio.n_anos_cronicos}a` : '-'}
                      </td>
                      <td style={{ padding: '5px 9px', color: 'var(--text-mid)', fontFamily: 'var(--mono)' }}>
                        {municipio.qsiconfi != null ? fmtPct(Number(municipio.qsiconfi) * 100, 0) : '-'}
                      </td>
                      <td
                        style={{
                          padding: '5px 9px',
                          fontFamily: 'var(--mono)',
                          color: Number(municipio.ccauc) > 0 ? '#ef4444' : 'var(--text-mid)',
                        }}
                      >
                        {fmtNum(municipio.ccauc, 2)}
                      </td>
                      <td
                        style={{
                          padding: '5px 9px',
                          fontFamily: 'var(--mono)',
                          color: Number(municipio.lliq_raw) < 0 ? '#ef4444' : 'var(--text-mid)',
                        }}
                      >
                        {fmtNum(municipio.lliq_raw, 3)}
                      </td>
                      <td
                        style={{
                          padding: '5px 9px',
                          fontFamily: 'var(--mono)',
                          color: Number(municipio.autonomia_media) < 0.08 ? '#f59e0b' : 'var(--text-mid)',
                        }}
                      >
                        {fmtNum(municipio.autonomia_media, 3)}
                      </td>
                      <td style={{ padding: '5px 9px', color: 'var(--text-mid)', fontFamily: 'var(--mono)' }}>
                        {municipio.n_licitacoes?.toLocaleString('pt-BR') || '-'}
                      </td>
                      <td style={{ padding: '5px 9px', color: 'var(--text-mid)', fontFamily: 'var(--mono)' }}>
                        {fmtBRL(municipio.valor_homologado_total)}
                      </td>
                      <td
                        style={{
                          padding: '5px 9px',
                          fontFamily: 'var(--mono)',
                          color: Number(municipio.pct_dispensa) > 0.3 ? '#ef4444' : 'var(--text-mid)',
                        }}
                      >
                        {municipio.pct_dispensa != null ? fmtPct(Number(municipio.pct_dispensa) * 100) : '-'}
                      </td>
                      <td style={{ padding: '5px 9px' }}>
                        <div style={{ display: 'flex', gap: '3px', flexWrap: 'wrap' }}>
                          {alertasMunicipio.map((alerta) => (
                            <AlertaBadge key={alerta.label} label={alerta.label} cor={alerta.cor} />
                          ))}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {municipiosFiltrados.length > PREVIEW_LINHAS ? (
              <div
                onClick={() => setTabelaExpandida((valor) => !valor)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  padding: '9px',
                  cursor: 'pointer',
                  borderTop: '1px solid var(--border-dim)',
                  color: 'var(--text-lo)',
                  fontFamily: 'var(--mono)',
                  fontSize: '0.62rem',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  background: 'var(--bg-card)',
                }}
              >
                {tabelaExpandida ? <span>▲ Colapsar - mostrar apenas top {PREVIEW_LINHAS}</span> : <span>▼ Ver todos os municipios</span>}
              </div>
            ) : null}
          </div>

        </main>
      </div>
    </>
  )
}

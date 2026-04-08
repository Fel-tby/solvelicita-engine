import { useEffect, useState } from 'react'
import Link from 'next/link'
import SiteFooter from '../../components/SiteFooter'
import SiteLayout from '../../components/SiteLayout'
import { buildPageTitle } from '../../config/site'
import { buildStateSummaries, fetchMunicipios } from '../../lib/municipios'
import { ESTADOS } from '../../lib/prototypeData'

export default function DadosPage() {
  const [states, setStates] = useState(ESTADOS)

  useEffect(() => {
    let active = true

    async function load() {
      try {
        const rows = await fetchMunicipios()
        if (!active) return

        const summaries = buildStateSummaries(rows)
        const byUf = new Map(summaries.map((item) => [item.uf, item]))

        setStates(
          ESTADOS.map((estado) => {
            const summary = byUf.get(estado.uf)
            if (!summary || !summary.hasData) return estado

            return {
              ...estado,
              nome: summary.nome || estado.nome,
              n: summary.total,
              baixo: summary.baixo,
              medio: summary.medio,
              alto: summary.alto,
              critico: summary.critico,
              nd: summary.sem_dados,
              ativo: true,
            }
          }),
        )
      } catch {
        if (active) {
          setStates(ESTADOS)
        }
      }
    }

    load()

    return () => {
      active = false
    }
  }, [])

  return (
    <SiteLayout
      title={buildPageTitle('Dados')}
      description="Selecione um estado para abrir o dashboard interativo."
      activeNav="dados"
    >
      <section id="dados" className="section active">
        <div className="page-header">
          <h1>Panorama Nacional</h1>
          <p>
            Selecione um estado para abrir o dashboard interativo. Estados em
            cinza ainda não foram processados.
          </p>
        </div>
        <div id="uf-grid" className="uf-grid">
          {states.map((estado) => {
            if (estado.ativo) {
              return (
                <Link
                  key={estado.uf}
                  href={`/dados/${estado.uf.toLowerCase()}`}
                  className="uf-card"
                >
                  <div className="uf-sigla">{estado.uf}</div>
                  <div className="uf-name">{estado.nome}</div>
                  <div className="uf-bar">
                    <div style={{ flex: Math.max(estado.baixo || 0, 1), background: 'var(--green)' }} />
                    <div style={{ flex: Math.max(estado.medio || 0, 1), background: 'var(--yellow)' }} />
                    <div style={{ flex: Math.max(estado.alto || 0, 1), background: 'var(--red)' }} />
                    <div style={{ flex: Math.max(estado.critico || 0, 1), background: '#a01010' }} />
                  </div>
                  <div className="uf-mun">{estado.n} municípios</div>
                  <span
                    className="uf-tag"
                    style={{ background: 'var(--green-bg)', color: 'var(--green)' }}
                  >
                    Disponível
                  </span>
                </Link>
              )
            }

            return (
              <div key={estado.uf} className="uf-card em-breve">
                <div className="uf-sigla" style={{ color: 'var(--text-light)' }}>
                  {estado.uf}
                </div>
                <div className="uf-name">{estado.nome}</div>
                <div className="uf-mun" style={{ marginTop: '0.5rem' }}>
                  {estado.n} municípios
                </div>
                <span
                  className="uf-tag"
                  style={{ background: 'var(--gray-bg)', color: 'var(--gray)' }}
                >
                  Em breve
                </span>
              </div>
            )
          })}
        </div>
        <SiteFooter />
      </section>
    </SiteLayout>
  )
}

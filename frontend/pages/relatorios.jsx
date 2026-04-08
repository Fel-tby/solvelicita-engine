import SiteFooter from '../components/SiteFooter'
import SiteLayout from '../components/SiteLayout'
import { buildPageTitle } from '../config/site'

export default function RelatoriosPage() {
  return (
    <SiteLayout
      title={buildPageTitle('Relatórios')}
      description="Relatórios estaduais em preparação para publicação."
      activeNav="relatorios"
    >
      <section id="relatorios" className="section active">
        <div className="page-header">
          <h1>Relatórios Estaduais</h1>
          <p>Os relatórios narrativos ainda estão em preparação para publicação.</p>
        </div>

        <div className="rel-placeholder">
          <div className="rel-placeholder-card">
            <div className="rel-tag">Em produção</div>
            <h2 className="rel-placeholder-title">Primeiro relatório: Paraíba</h2>
            <p className="rel-placeholder-body">
              O relatório estadual da Paraíba está em produção. Assim que a
              primeira versão for concluída, esta aba vai passar a listar os
              relatórios publicados e seus respectivos históricos.
            </p>
            <div className="rel-placeholder-meta">
              <span className="rel-placeholder-chip">Paraíba</span>
              <span className="rel-placeholder-chip">Publicação em breve</span>
            </div>
          </div>
        </div>

        <SiteFooter />
      </section>
    </SiteLayout>
  )
}

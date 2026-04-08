import { useRouter } from 'next/router'
import DashboardPage from '../../components/DashboardPage'
import SiteLayout from '../../components/SiteLayout'
import { buildPageTitle, siteConfig } from '../../config/site'

export default function EstadoPage() {
  const router = useRouter()
  const uf = typeof router.query.uf === 'string' ? router.query.uf.toUpperCase() : ''

  return (
    <SiteLayout
      title={buildPageTitle(uf || 'Dados')}
      description={`Dashboard interativo do ${siteConfig.brandName} por estado.`}
      activeNav="dados"
    >
      <section id="dados" className="section active">
        {uf ? <DashboardPage uf={uf} /> : <div className="page-header"><p>Carregando estado…</p></div>}
      </section>
    </SiteLayout>
  )
}

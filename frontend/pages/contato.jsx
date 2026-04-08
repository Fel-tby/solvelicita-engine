import SiteFooter from '../components/SiteFooter'
import SiteLayout from '../components/SiteLayout'
import { buildPageTitle, siteConfig } from '../config/site'

export default function ContatoPage() {
  return (
    <SiteLayout
      title={buildPageTitle('Contato')}
      description="Entre em contato com o projeto."
      activeNav="contato"
    >
      <section id="contato" className="section active">
        <div className="contato-wrap">
          <h1>Contato</h1>
          <p>
            Para entrar em contato, escreva para{' '}
            <a href={`mailto:${siteConfig.contactEmail}`}>{siteConfig.contactEmail}</a>.
          </p>

          <div className="contato-alts">
            <div
              className="contato-alt"
              style={{ marginLeft: 'auto', marginRight: 'auto', textAlign: 'center' }}
            >
              <div className="contato-alt-label">GitHub</div>
              <a href={siteConfig.repoUrl}>{siteConfig.githubLabel}</a>
            </div>
          </div>
        </div>
        <SiteFooter />
      </section>
    </SiteLayout>
  )
}

import Link from 'next/link'
import { buildFooterLabel, siteConfig } from '../config/site'

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-left">
        <div className="site-footer-title">{buildFooterLabel()}</div>
        <div className="site-footer-subtitle">Dados públicos, código aberto.</div>
      </div>

      <div className="site-footer-right">
        <div className="footer-links">
          <a href={siteConfig.repoUrl}>GitHub</a>
          <Link href={siteConfig.paths.methodology}>Docs</Link>
          <Link href={`${siteConfig.paths.methodology}#metodologia`}>Metodologia</Link>
        </div>

        <div className="footer-contact">
          <a href={`mailto:${siteConfig.contactEmail}`}>{siteConfig.contactEmail}</a>
        </div>

        <div className="footer-links footer-links-muted">
          <Link href={siteConfig.paths.privacy}>Privacidade</Link>
          <Link href={siteConfig.paths.terms}>Termos</Link>
        </div>
      </div>
    </footer>
  )
}

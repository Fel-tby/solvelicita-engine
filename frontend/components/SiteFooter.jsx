import Link from 'next/link'
import { buildFooterLabel, siteConfig } from '../config/site'

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="site-footer-top">
          <div className="site-footer-brand">
            <div className="site-footer-title">{siteConfig.brandName}</div>
            <div className="site-footer-subtitle">Os dados são públicos. A forma que avaliamos, também.</div>
          </div>

          <div className="site-footer-nav">
            <div className="footer-nav-col">
              <Link href={siteConfig.paths.methodology}>Docs</Link>
              <Link href={`${siteConfig.paths.methodology}#metodologia`}>Metodologia</Link>
              <a href={siteConfig.repoUrl}>GitHub</a>
            </div>
            <div className="footer-nav-col">
              <a href={`mailto:${siteConfig.contactEmail}`}>{siteConfig.contactEmail}</a>
              <Link href={siteConfig.paths.privacy}>Privacidade</Link>
              <Link href={siteConfig.paths.terms}>Termos</Link>
            </div>
          </div>
        </div>

        <div className="site-footer-bottom">
          {buildFooterLabel()}
        </div>
      </div>
    </footer>
  )
}

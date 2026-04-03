import Link from 'next/link'

export default function SiteFooter({ left = 'SolveLicita · 2026 · Brasil' }) {
  return (
    <footer className="site-footer">
      <div>{left}</div>
      <div className="footer-links">
        <a href="https://github.com/Fel-tby/solvelicita">GitHub</a>
        <Link href="/docs">Metodologia</Link>
        <Link href="/contato">Contato</Link>
      </div>
    </footer>
  )
}

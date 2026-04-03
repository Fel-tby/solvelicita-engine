import Head from 'next/head'
import Link from 'next/link'
import { useRouter } from 'next/router'

const NAV_ITEMS = [
  { key: 'sobre', href: '/sobre', label: 'Sobre' },
  { key: 'dados', href: '/dados', label: 'Dados' },
  { key: 'relatorios', href: '/relatorios', label: 'Relatórios' },
  { key: 'docs', href: '/docs', label: 'Docs' },
  { key: 'contato', href: '/contato', label: 'Contato' },
]

export default function SiteLayout({ title, description, activeNav, children }) {
  const router = useRouter()

  function goTo(href) {
    router.push(href)
  }

  return (
    <>
      <Head>
        <title>{title}</title>
        <meta name="description" content={description} />
      </Head>

      <nav>
        <Link className="nav-logo" href="/">
          Solve<span>Licita</span>
        </Link>
        <div className="nav-links">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              className={`nav-link ${activeNav === item.key ? 'active' : ''}`}
              onClick={() => goTo(item.href)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="nav-right" />
      </nav>

      {children}
    </>
  )
}

import Link from 'next/link'
import { useRouter } from 'next/router'
import SeoHead from './SeoHead'
import { navigationItems } from '../config/navigation'
import {
  buildBreadcrumbJsonLd,
  buildDatasetJsonLd,
  buildOrganizationJsonLd,
  siteConfig,
} from '../config/site'
import { ESTADOS } from '../lib/prototypeData'

const PATH_LABELS = {
  '/sobre': 'Sobre',
  '/dados': 'Dados',
  '/docs': 'Docs',
  '/relatorios': 'Relatórios',
  '/contato': 'Contato',
  '/privacidade': 'Privacidade',
  '/termos': 'Termos',
}

function normalizePath(value) {
  if (!value) return '/'
  const [pathWithoutQuery] = value.split('?')
  const [pathWithoutHash] = pathWithoutQuery.split('#')
  return pathWithoutHash || '/'
}

function resolveStateMeta(path) {
  if (!path.startsWith('/dados/')) return null

  const uf = path.split('/')[2]
  if (!uf) return null

  const requestedUf = uf.toUpperCase()
  const state = ESTADOS.find((item) => item.uf === requestedUf)

  return {
    uf: requestedUf,
    name: state?.nome || requestedUf,
    isActive: Boolean(state?.ativo),
  }
}

function buildDefaultRobots(path, stateMeta) {
  if (path === siteConfig.paths.contact || path === siteConfig.paths.privacy || path === siteConfig.paths.terms) {
    return 'noindex,follow'
  }

  if (stateMeta && !stateMeta.isActive) {
    return 'noindex,follow'
  }

  return 'index,follow'
}

function buildDefaultJsonLd(path, stateMeta) {
  if (path === siteConfig.paths.home) {
    return buildOrganizationJsonLd()
  }

  if (stateMeta) {
    return [
      buildBreadcrumbJsonLd([
        { name: 'Início', path: siteConfig.paths.home },
        { name: 'Dados', path: siteConfig.paths.data },
        { name: stateMeta.name, path },
      ]),
      buildDatasetJsonLd({
        name: `Score de Solvência Municipal — ${stateMeta.name}`,
        description: `Dashboard do ${siteConfig.brandName} para ${stateMeta.name}, com score de solvência municipal e distribuição de risco.`,
        path,
      }),
    ]
  }

  if (path === siteConfig.paths.data) {
    return [
      buildBreadcrumbJsonLd([
        { name: 'Início', path: siteConfig.paths.home },
        { name: 'Dados', path: siteConfig.paths.data },
      ]),
      buildDatasetJsonLd({
        name: 'Score de Solvência Municipal por estado',
        description:
          'Base do SolveLicita com dashboards estaduais e cobertura municipal do score de solvência.',
        path,
      }),
    ]
  }

  if (PATH_LABELS[path]) {
    return buildBreadcrumbJsonLd([
      { name: 'Início', path: siteConfig.paths.home },
      { name: PATH_LABELS[path], path },
    ])
  }

  return null
}

export default function SiteLayout({
  title,
  description,
  activeNav,
  canonicalPath,
  robots,
  jsonLd,
  ogType = 'website',
  children,
}) {
  const router = useRouter()
  const resolvedPath = canonicalPath || normalizePath(router.asPath || router.pathname)
  const stateMeta = resolveStateMeta(resolvedPath)
  const resolvedRobots = robots || buildDefaultRobots(resolvedPath, stateMeta)
  const resolvedJsonLd = jsonLd || buildDefaultJsonLd(resolvedPath, stateMeta)

  return (
    <>
      <SeoHead
        title={title}
        description={description}
        path={resolvedPath}
        robots={resolvedRobots}
        jsonLd={resolvedJsonLd}
        ogType={ogType}
      />

      <nav>
        <Link className="nav-logo" href="/">
          <svg
            height="24"
            viewBox="0 0 100 100"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <rect width="100" height="100" rx="18" fill="#185FA5" />
            <path
              d="M50,18 C74,12 82,32 66,42 C50,52 30,54 18,66 C8,78 22,92 50,90"
              fill="none"
              stroke="white"
              strokeWidth="8.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M50,18 V90 H76"
              fill="none"
              stroke="white"
              strokeWidth="8.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <svg
            aria-label={siteConfig.brandName}
            className="nav-wordmark"
            viewBox="0 0 132 20"
            xmlns="http://www.w3.org/2000/svg"
            role="img"
          >
            <text
              x="0"
              y="15"
              fontFamily="system-ui,-apple-system,'Helvetica Neue',sans-serif"
              fontSize="15"
              fontWeight="600"
              letterSpacing="-0.5"
            >
              <tspan fill="#111827">Solve</tspan>
              <tspan fill="#185FA5">Licita</tspan>
            </text>
          </svg>
        </Link>
        <div className="nav-links">
          {navigationItems.map((item) => (
            <Link
              key={item.key}
              className={`nav-link ${activeNav === item.key ? 'active' : ''}`}
              href={item.href}
              aria-current={activeNav === item.key ? 'page' : undefined}
            >
              {item.label}
            </Link>
          ))}
        </div>
        <div className="nav-right" />
      </nav>

      {children}
    </>
  )
}

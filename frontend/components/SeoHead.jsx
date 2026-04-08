import Head from 'next/head'
import { buildAbsoluteUrl, siteConfig } from '../config/site'

function normalizeJsonLd(jsonLd) {
  if (!jsonLd) return []
  return Array.isArray(jsonLd) ? jsonLd.filter(Boolean) : [jsonLd]
}

export default function SeoHead({
  title,
  description,
  path = '/',
  robots = 'index,follow',
  jsonLd,
  ogType = 'website',
}) {
  const canonicalUrl = buildAbsoluteUrl(path)
  const ogImageUrl = buildAbsoluteUrl('/logo.svg')
  const items = normalizeJsonLd(jsonLd)

  return (
    <Head>
      <title>{title}</title>
      <meta name="description" content={description} />
      <meta name="robots" content={robots} />
      <meta name="googlebot" content={robots} />
      <link rel="canonical" href={canonicalUrl} />

      <meta property="og:site_name" content={siteConfig.brandName} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:type" content={ogType} />
      <meta property="og:locale" content="pt_BR" />
      <meta property="og:image" content={ogImageUrl} />
      <meta property="og:image:width" content="100" />
      <meta property="og:image:height" content="100" />

      <meta name="twitter:card" content="summary" />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />

      {items.map((item, index) => (
        <script
          key={`${path}-jsonld-${index}`}
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(item) }}
        />
      ))}
    </Head>
  )
}

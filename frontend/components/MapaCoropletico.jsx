import { useEffect, useMemo, useRef } from 'react'
import { GeoJSON, MapContainer, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

function FitGeoJson({ geoData }) {
  const map = useMap()

  useEffect(() => {
    if (!geoData) return
    const bounds = L.geoJSON(geoData).getBounds()
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [16, 16] })
    }
  }, [geoData, map])

  return null
}

export default function MapaCoropletico({ geoData, municipios, ibgesFiltrados, corPorScore, onSelect }) {
  const geoJsonRef = useRef(null)

  const scoreMap = useMemo(() => {
    const map = {}
    municipios.forEach((municipio) => {
      map[String(municipio.cod_ibge)] = municipio
    })
    return map
  }, [municipios])

  useEffect(() => {
    if (!geoJsonRef.current) return

    geoJsonRef.current.eachLayer((layer) => {
      const ibge = String(layer.feature?.properties?.id || '').substring(0, 7)
      const municipio = scoreMap[ibge]
      const ativo = ibgesFiltrados.has(ibge)

      layer.setStyle({
        fillColor: municipio ? corPorScore(municipio.score) : '#374151',
        fillOpacity: ativo ? 0.85 : 0.15,
        color: '#080b11',
        weight: 0.5,
      })
    })
  }, [ibgesFiltrados, scoreMap, corPorScore])

  function estilo(feature) {
    const ibge = String(feature.properties?.id || '').substring(0, 7)
    const municipio = scoreMap[ibge]

    return {
      fillColor: municipio ? corPorScore(municipio.score) : '#374151',
      fillOpacity: ibgesFiltrados.has(ibge) ? 0.85 : 0.15,
      color: '#080b11',
      weight: 0.5,
    }
  }

  function onEachFeature(feature, layer) {
    const ibge = String(feature.properties?.id || '').substring(0, 7)
    const municipio = scoreMap[ibge]
    if (!municipio) return

    layer.bindTooltip(
      `<div style="font-family:'DM Mono',monospace;font-size:11px;background:#1e2433;color:#e2e8f0;padding:5px 8px;border-radius:2px;border:1px solid #2d3748"><strong>${municipio.ente}</strong> · ${municipio.score != null ? Number(municipio.score).toFixed(1) : '-'}</div>`,
      { sticky: true, opacity: 1 },
    )

    layer.on({
      mouseover: (event) => {
        event.target.setStyle({ fillOpacity: 1, weight: 2, color: '#94a3b8' })
        event.target.bringToFront()
      },
      mouseout: (event) => {
        const ativo = ibgesFiltrados.has(ibge)
        event.target.setStyle({ fillOpacity: ativo ? 0.85 : 0.15, weight: 0.5, color: '#080b11' })
      },
      click: () => onSelect?.(municipio),
    })
  }

  return (
    <MapContainer center={[-14.235, -51.9253]} zoom={4} style={{ height: '100%', width: '100%', background: '#0a0d14' }} zoomControl>
      {geoData ? <FitGeoJson geoData={geoData} /> : null}
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://carto.com">CARTO</a>'
      />
      <GeoJSON ref={geoJsonRef} data={geoData} style={estilo} onEachFeature={onEachFeature} />
    </MapContainer>
  )
}

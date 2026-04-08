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
        fillColor: municipio ? corPorScore(municipio.score) : '#cbd5e1',
        fillOpacity: ativo ? 0.85 : 0.15,
        color: '#cbd5e1',
        weight: 0.5,
      })
    })
  }, [ibgesFiltrados, scoreMap, corPorScore])

  function estilo(feature) {
    const ibge = String(feature.properties?.id || '').substring(0, 7)
    const municipio = scoreMap[ibge]

    return {
      fillColor: municipio ? corPorScore(municipio.score) : '#cbd5e1',
      fillOpacity: ibgesFiltrados.has(ibge) ? 0.85 : 0.15,
      color: '#cbd5e1',
      weight: 0.5,
    }
  }

  function onEachFeature(feature, layer) {
    const ibge = String(feature.properties?.id || '').substring(0, 7)
    const municipio = scoreMap[ibge]
    if (!municipio) return

    layer.bindTooltip(
      `<div style="font-family:var(--sans);font-size:12px;background:var(--bg-card);color:var(--text-hi);padding:8px 10px;border-radius:8px;border:1px solid var(--border);box-shadow:0 10px 22px rgba(15,23,42,0.08)"><strong style="display:block;font-size:12px;margin-bottom:2px">${municipio.ente}</strong><span style="font-family:var(--mono);font-size:11px;color:var(--text-lo)">Score ${municipio.score != null ? Number(municipio.score).toFixed(1) : '-'}</span></div>`,
      { sticky: true, opacity: 1 },
    )

    layer.on({
      mouseover: (event) => {
        event.target.setStyle({ fillOpacity: 1, weight: 2, color: '#94a3b8' })
        event.target.bringToFront()
      },
      mouseout: (event) => {
        const ativo = ibgesFiltrados.has(ibge)
        event.target.setStyle({ fillOpacity: ativo ? 0.85 : 0.15, weight: 0.5, color: '#cbd5e1' })
      },
      click: () => onSelect?.(municipio),
    })
  }

  return (
    <MapContainer center={[-14.235, -51.9253]} zoom={4} style={{ height: '100%', width: '100%', background: '#f8fafc' }} zoomControl>
      {geoData ? <FitGeoJson geoData={geoData} /> : null}
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://carto.com">CARTO</a>'
      />
      <GeoJSON ref={geoJsonRef} data={geoData} style={estilo} onEachFeature={onEachFeature} />
    </MapContainer>
  )
}

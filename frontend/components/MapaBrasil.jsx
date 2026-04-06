import { BRAZIL_MAP_STATES, BRAZIL_MAP_VIEWBOX } from '../lib/brazilMapData'

const ACTIVE_UFS = new Set(['AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE'])

export default function MapaBrasil() {
  return (
    <svg className="brazil-map-svg" viewBox={BRAZIL_MAP_VIEWBOX} xmlns="http://www.w3.org/2000/svg" aria-label="Mapa do Brasil — cobertura atual">
      {BRAZIL_MAP_STATES.map((state, index) => {
        const isActive = ACTIVE_UFS.has(state.uf)

        return (
          <path
            key={state.uf}
            d={state.d}
            className={isActive ? 'state-active' : 'state-inactive'}
            data-uf={state.uf}
            data-name={state.name}
            style={isActive ? undefined : { animationDelay: `${(index * 0.12).toFixed(2)}s` }}
          />
        )
      })}
    </svg>
  )
}

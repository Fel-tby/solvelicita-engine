import { useRouter } from 'next/router'
import MapaBrasil from './MapaBrasil'

export default function AboutPage() {
  const router = useRouter()

  return (
    <>
      <div className="hero">
        <h1>Essa prefeitura tem capacidade de pagar o que contrata?</h1>
        <p>
          Municípios brasileiros licitam bilhões em serviços e fornecimentos por
          ano. Os dados para responder essa pergunta já existem, nos sistemas do
          Tesouro Nacional. O SolveLicita os cruza e transforma em um score por
          município.
        </p>
        <div className="hero-actions">
          <button className="btn-primary" onClick={() => router.push('/dados')} type="button">
            Ver os dados
          </button>
          <button className="btn-secondary" onClick={() => router.push('/docs')} type="button">
            Como funciona
          </button>
        </div>
      </div>

      <div className="brazil-map-section">
        <div className="brazil-map-inner">
          <div className="brazil-map-label">Cobertura atual</div>
          <MapaBrasil />
          <div className="brazil-map-legend">
            <div className="map-legend-item">
              <div className="map-legend-dot active" />
              <span>Disponível</span>
            </div>
            <div className="map-legend-item">
              <div className="map-legend-dot pending" />
              <span>Em processamento</span>
            </div>
          </div>
        </div>
      </div>

      <div className="sobre-stats-new">
        <div className="stat-new">
          <div className="stat-new-n">5,6×</div>
          <div className="stat-new-label">
            mais risco de uma prefeitura classificada como Risco Alto atrasar
            pagamentos de forma crônica do que uma de Risco Baixo. Comprovado
            com dados históricos.
          </div>
        </div>
        <div className="stat-new">
          <div className="stat-new-n">1 em 2</div>
          <div className="stat-new-label">
            municípios classificados como Risco Alto acumularam contas atrasadas
            no ano seguinte. Entre os de Risco Baixo, essa proporção cai para
            apenas 1 em 11.
          </div>
        </div>
        <div className="stat-new">
          <div className="stat-new-n">5.570</div>
          <div className="stat-new-label">
            municípios brasileiros compõem a ambição de cobertura do projeto.
            Nesta fase, o piloto está validado nas 1.794 cidades do Nordeste.
          </div>
        </div>
      </div>

      <div className="sobre-body">
        <h2>O que é o SolveLicita</h2>
        <p>
          O SolveLicita calcula um Score de Solvência (0 a 100), atualmente,
          para cada município do Nordeste, cruzando dados fiscais públicos do Tesouro
          Nacional e do Governo Federal. Seis indicadores ponderados por
          relevância, calculados a partir de bases oficiais federais, com dados
          declarados pelos municípios e registros verificados pelo Governo
          Federal.
        </p>
        <p>
          Não é um modelo de previsão pontual de inadimplência. É um indicador
          de risco estrutural, com metodologia documentada, código aberto e
          resultados reproduzíveis.
        </p>
        <h2>Para que serve</h2>
        <p>
          Serve para apoiar decisões que dependem da capacidade fiscal do
          município. Ajuda a identificar sinais de fragilidade, comparar
          prefeituras com critérios consistentes e reduzir assimetria de
          informação antes de contratar, analisar ou monitorar um ente público.
        </p>
        <p>
          É útil para fornecedores, equipes comerciais, pesquisadores,
          jornalistas e gestores públicos que precisam de uma referência técnica
          e comparável sobre risco fiscal municipal.
        </p>
      </div>
    </>
  )
}

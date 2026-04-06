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
          <div className="stat-new-n">5,7×</div>
          <div className="stat-new-label">
            mais chance de um município Risco Alto acumular Restos a Pagar
            crônicos do que um Risco Baixo. Validado retroativamente.
          </div>
        </div>
        <div className="stat-new">
          <div className="stat-new-n">1 em 2</div>
          <div className="stat-new-label">
            municípios classificados Risco Alto registrou acúmulo recorrente de pagamentos não quitados no ano
            seguinte, contra 1 em 11 entre os de Risco Baixo
          </div>
        </div>
        <div className="stat-new">
          <div className="stat-new-n">5.570</div>
          <div className="stat-new-label">
            municípios brasileiros, com metodologia e arquitetura de dados projetadas para cobertura
            nacional e piloto cobrindo os 1.794 municípios do Nordeste
          </div>
        </div>
      </div>

      <div className="sobre-body">
        <h2>O que é o SolveLicita</h2>
        <p>
          O SolveLicita calcula um Score de Solvência (0 a 100) para cada
          município brasileiro, cruzando dados fiscais públicos do Tesouro
          Nacional e do Governo Federal. Seis indicadores ponderados por
          relevância, todos declarados pelos próprios municípios às autoridades
          federais.
        </p>
        <p>
          Não é um modelo de previsão pontual de inadimplência. É um indicador
          de risco estrutural, com metodologia documentada, código aberto e
          resultados reproduzíveis.
        </p>
        <h2>Para que serve</h2>
        <p>
          Para quem precisa avaliar a capacidade fiscal de um município antes de
          tomar uma decisão.
        </p>
        <p>
          Fornecedores avaliando o risco de contratar com uma prefeitura.
          Pesquisadores comparando gestão fiscal entre municípios. Jornalistas
          verificando saúde orçamentária. Gestores públicos acompanhando os
          próprios indicadores antes que virem problema.
        </p>
      </div>
    </>
  )
}

import SiteFooter from '../components/SiteFooter'
import SiteLayout from '../components/SiteLayout'
import { buildPageTitle } from '../config/site'

export default function TermosPage() {
  return (
    <SiteLayout
      title={buildPageTitle('Termos')}
      description="Informações sobre os termos de uso do produto."
      activeNav=""
    >
      <section className="section active">
        <div className="legal-wrap">
          <article className="legal-card">
            <header className="legal-header">
              <p className="legal-eyebrow">Aviso Legal</p>
              <h1>Termos de Uso</h1>
              <p className="legal-meta">Última atualização: 7 de abril de 2026</p>
              <p className="legal-lead">
                Ao acessar o site solvelicita.tech, você concorda com os termos descritos
                abaixo. Se não concordar, por favor não utilize o site.
              </p>
            </header>

            <section className="legal-section">
              <h2>1. O que é o SolveLicita</h2>
              <p>
                O SolveLicita é uma ferramenta de análise de risco fiscal municipal. Ele
                cruza dados públicos do Tesouro Nacional, CAUC, SICONFI, DCA e PNCP para
                gerar um Score de Solvência por município, indicando a capacidade estrutural
                de honrar contratos públicos.
              </p>
            </section>

            <section className="legal-section">
              <h2>2. Natureza dos dados apresentados</h2>
              <p>
                Todos os dados exibidos no site são originários de fontes federais públicas,
                declarados pelos próprios municípios às autoridades federais. O SolveLicita
                os coleta, transforma e apresenta de forma estruturada, mas não os produz
                nem os audita na origem.
              </p>
            </section>

            <section className="legal-section">
              <h2>3. Limitações do score</h2>
              <p>O score é um indicador de risco relativo e estrutural. Ele não é:</p>
              <ul>
                <li>uma previsão de inadimplência pontual</li>
                <li>uma garantia de pagamento ou de comportamento futuro</li>
                <li>um substituto para análise de fluxo de caixa, auditoria contábil ou due diligence jurídica</li>
              </ul>
              <p>
                Decisões contratuais, financeiras ou editoriais baseadas nos dados do
                SolveLicita são de responsabilidade exclusiva de quem as toma.
              </p>
            </section>

            <section className="legal-section">
              <h2>4. Uso permitido</h2>
              <p>
                O site e seus dados podem ser usados livremente para fins de pesquisa,
                jornalismo, análise fiscal e avaliação de risco contratual, desde que:
              </p>
              <ul>
                <li>a fonte seja citada (SolveLicita / solvelicita.tech)</li>
                <li>os dados não sejam alterados ou descontextualizados de forma enganosa</li>
              </ul>
            </section>

            <section className="legal-section">
              <h2>5. Código aberto</h2>
              <p>
                O código-fonte do SolveLicita está disponível publicamente no GitHub
                sob licença AGPL-3.0. Contribuições são bem-vindas.
              </p>
            </section>

            <section className="legal-section">
              <h2>6. Disponibilidade</h2>
              <p>
                O site é oferecido no estado em que se encontra. Não garantimos
                disponibilidade contínua, ausência de erros ou atualização em tempo real
                dos dados. O pipeline de coleta tem frequências variáveis por fonte,
                descritas na documentação.
              </p>
            </section>

            <section className="legal-section">
              <h2>7. Alterações destes termos</h2>
              <p>
                Estes termos poderão ser atualizados para refletir mudanças no produto
                ou na estrutura jurídica do SolveLicita. A versão mais recente ficará
                sempre disponível nesta página.
              </p>
              <p><strong>Para dúvidas:</strong> contato@solvelicita.tech</p>
            </section>
          </article>
        </div>
        <SiteFooter />
      </section>
    </SiteLayout>
  )
}

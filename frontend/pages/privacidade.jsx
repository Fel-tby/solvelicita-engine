import SiteFooter from '../components/SiteFooter'
import SiteLayout from '../components/SiteLayout'
import { buildPageTitle } from '../config/site'

export default function PrivacidadePage() {
  return (
    <SiteLayout
      title={buildPageTitle('Privacidade')}
      description="Informações sobre privacidade do produto."
      activeNav=""
    >
      <section className="section active">
        <div className="legal-wrap">
          <article className="legal-card">
            <header className="legal-header">
              <p className="legal-eyebrow">Aviso Legal</p>
              <h1>Aviso de Privacidade</h1>
              <p className="legal-meta">Última atualização: 7 de abril de 2026</p>
              <p className="legal-lead">
                O SolveLicita respeita a sua privacidade e trata dados pessoais de forma
                compatível com a Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018).
              </p>
              <p className="legal-lead">
                Este aviso explica, de forma objetiva, quais dados podem ser tratados quando
                você navega no site solvelicita.tech.
              </p>
            </header>

            <section className="legal-section">
              <h2>1. Quem é o responsável pelo tratamento</h2>
              <p><strong>Responsável pelo site:</strong> SolveLicita</p>
              <p><strong>Contato para assuntos de privacidade:</strong> contato@solvelicita.tech</p>
              <p>
                Nota: enquanto o produto estiver em fase pré-operacional, este site é mantido
                por seu fundador. Quando houver constituição formal da empresa e CNPJ,
                este aviso será atualizado.
              </p>
            </section>

            <section className="legal-section">
              <h2>2. Quais dados podem ser tratados</h2>

              <div className="legal-subsection">
                <h3>a) Dados de navegação (Vercel Analytics)</h3>
                <p>
                  Este site usa o Vercel Analytics para medir o desempenho técnico e o uso
                  geral das páginas. Os dados coletados são agregados e anônimos, não
                  identificam você individualmente. Podem incluir:
                </p>
                <ul>
                  <li>páginas acessadas e tempo de carregamento</li>
                  <li>tipo de dispositivo e navegador</li>
                  <li>país de origem da requisição</li>
                </ul>
                <p>
                  Nenhum cookie é criado por essa ferramenta. Para mais informações, consulte
                  a política de privacidade da Vercel:{' '}
                  <a href="https://vercel.com/legal/privacy-policy">https://vercel.com/legal/privacy-policy</a>
                </p>
              </div>

              <div className="legal-subsection">
                <h3>b) Dados técnicos de hospedagem</h3>
                <p>
                  Ao acessar o site, podem ser registrados dados técnicos básicos pelo
                  serviço de hospedagem (Vercel), como endereço IP, data e hora do acesso
                  e logs de requisição. Esses dados são necessários para manter o site
                  em funcionamento e garantir sua segurança.
                </p>
              </div>
            </section>

            <section className="legal-section">
              <h2>3. Para quais finalidades usamos esses dados</h2>
              <p>Os dados podem ser tratados para:</p>
              <ul>
                <li>operar, manter e proteger o site</li>
                <li>prevenir abuso, fraude e uso indevido</li>
                <li>medir desempenho técnico e uso geral do site</li>
                <li>melhorar o conteúdo e a experiência de navegação</li>
              </ul>
            </section>

            <section className="legal-section">
              <h2>4. Base legal do tratamento</h2>
              <p>
                O tratamento ocorre com base no legítimo interesse para funcionamento,
                segurança e melhoria do site, nos termos da LGPD.
              </p>
            </section>

            <section className="legal-section">
              <h2>5. Compartilhamento de dados</h2>
              <p>Seus dados não são vendidos. Podem ser compartilhados apenas com:</p>
              <ul>
                <li>Vercel Inc. — hospedagem do site e coleta de analytics agregado</li>
              </ul>
            </section>

            <section className="legal-section">
              <h2>6. Seus direitos</h2>
              <p>
                Nos termos da LGPD, você pode solicitar confirmação, acesso, correção
                ou eliminação de dados, quando aplicável.
              </p>
              <p><strong>Para exercer seus direitos:</strong> contato@solvelicita.tech</p>
            </section>

            <section className="legal-section">
              <h2>7. Segurança</h2>
              <p>
                Adotamos medidas razoáveis de segurança compatíveis com o estágio atual
                do projeto. Nenhum sistema é completamente livre de riscos.
              </p>
            </section>

            <section className="legal-section">
              <h2>8. Links para terceiros</h2>
              <p>
                O site pode conter links para GitHub e fontes públicas de dados. O
                tratamento realizado nesses ambientes segue as políticas próprias
                desses terceiros.
              </p>
            </section>

            <section className="legal-section">
              <h2>9. Alterações deste aviso</h2>
              <p>
                Este aviso poderá ser atualizado para refletir mudanças no site ou na
                estrutura jurídica do SolveLicita. A versão mais recente ficará sempre
                disponível nesta página.
              </p>
            </section>
          </article>
        </div>
        <SiteFooter />
      </section>
    </SiteLayout>
  )
}

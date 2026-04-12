import Link from 'next/link'
import AboutPage from '../components/AboutPage'
import SiteFooter from '../components/SiteFooter'
import SiteLayout from '../components/SiteLayout'
import { buildPageTitle } from '../config/site'

export default function SobrePage() {
  return (
    <SiteLayout
      title={buildPageTitle('Solvência Municipal')}
      description="Visão geral do SolveLicita."
      activeNav="sobre"
    >
      <section id="sobre" className="section active">
        <AboutPage />

        <div className="score-section">
          <div className="score-inner">
            <h2>Composição do score</h2>
            <p>Seis indicadores ponderados por relevância, todos de fontes oficiais.</p>
            <div className="score-rows">
              <div className="score-row">
                <div className="score-row-left">
                  <div className="score-row-name">Liquidez Líquida</div>
                  <div className="score-row-fonte">SICONFI / RGF Anexo 05</div>
                  <div className="score-row-desc">Caixa disponível após dedução de todos os Restos a Pagar</div>
                </div>
                <div className="score-bar-wrap"><div className="score-bar" style={{ width: '100%' }} /></div>
                <div className="score-pct">35%</div>
              </div>
              <div className="score-row">
                <div className="score-row-left">
                  <div className="score-row-name">RP Crônicos</div>
                  <div className="score-row-fonte">SICONFI / RREO Anexo 07</div>
                  <div className="score-row-desc">Padrão histórico de dívidas não pagas com fornecedores</div>
                </div>
                <div className="score-bar-wrap"><div className="score-bar" style={{ width: '43%', background: '#e67700' }} /></div>
                <div className="score-pct">15%</div>
              </div>
              <div className="score-row">
                <div className="score-row-left">
                  <div className="score-row-name">Execução Orçamentária</div>
                  <div className="score-row-fonte">SICONFI / RREO Anexo 01</div>
                  <div className="score-row-desc">Aderência entre receita prevista e efetivamente arrecadada</div>
                </div>
                <div className="score-bar-wrap"><div className="score-bar" style={{ width: '43%', background: '#2f9e44' }} /></div>
                <div className="score-pct">15%</div>
              </div>
              <div className="score-row">
                <div className="score-row-left">
                  <div className="score-row-name">Transparência Fiscal</div>
                  <div className="score-row-fonte">SICONFI</div>
                  <div className="score-row-desc">Continuidade histórica de entrega de dados ao Tesouro Nacional</div>
                </div>
                <div className="score-bar-wrap"><div className="score-bar" style={{ width: '43%', background: '#1098ad' }} /></div>
                <div className="score-pct">15%</div>
              </div>
              <div className="score-row">
                <div className="score-row-left">
                  <div className="score-row-name">Autonomia Tributária</div>
                  <div className="score-row-fonte">FINBRA / DCA</div>
                  <div className="score-row-desc">Dependência de repasses federais (FPM) vs receita própria</div>
                </div>
                <div className="score-bar-wrap"><div className="score-bar" style={{ width: '29%', background: '#868e96' }} /></div>
                <div className="score-pct">10%</div>
              </div>
              <div className="score-row">
                <div className="score-row-left">
                  <div className="score-row-name">Bloqueio Federal</div>
                  <div className="score-row-fonte">CAUC / STN</div>
                  <div className="score-row-desc">Pendências que bloqueiam recebimento de repasses federais</div>
                </div>
                <div className="score-bar-wrap"><div className="score-bar" style={{ width: '29%', background: '#868e96' }} /></div>
                <div className="score-pct">10%</div>
              </div>
            </div>
            <div className="classi-row">
              <span style={{ fontSize: '0.78rem', color: 'var(--text-light)' }}>Classificação:</span>
              <div className="classi-item"><span className="classi-badge" style={{ background: 'var(--green-bg)', color: 'var(--green)' }}>BAIXO</span> ≥ 80</div>
              <div className="classi-item"><span className="classi-badge" style={{ background: 'var(--yellow-bg)', color: 'var(--yellow)' }}>MÉDIO</span> 60–79</div>
              <div className="classi-item"><span className="classi-badge" style={{ background: 'var(--red-bg)', color: 'var(--red)' }}>ALTO</span> 40–59</div>
              <div className="classi-item"><span className="classi-badge" style={{ background: '#fff0f0', color: '#a01010' }}>CRÍTICO</span> &lt; 40</div>
            </div>
          </div>
        </div>

        <div className="fontes-section">
          <div className="fontes-inner">
            <p className="fontes-label">Dados coletados de fontes federais públicas</p>
            <div className="fontes-grid">
              <div className="fonte-card">
                <div className="fonte-sigla">SICONFI</div>
                <div className="fonte-inst">Tesouro Nacional · STN</div>
                <div className="fonte-desc">Relatórios fiscais bimestrais declarados pelos municípios: RREO e RGF</div>
              </div>
              <div className="fonte-card">
                <div className="fonte-sigla">CAUC</div>
                <div className="fonte-inst">Secretaria do Tesouro Nacional</div>
                <div className="fonte-desc">Cadastro de pendências que bloqueiam repasses federais, atualizado diariamente</div>
              </div>
              <div className="fonte-card">
                <div className="fonte-sigla">DCA</div>
                <div className="fonte-inst">Tesouro Nacional · FINBRA</div>
                <div className="fonte-desc">Receitas tributárias próprias e transferências constitucionais anuais</div>
              </div>
              <div className="fonte-card">
                <div className="fonte-sigla">PNCP</div>
                <div className="fonte-inst">Governo Federal</div>
                <div className="fonte-desc">Portal Nacional de Contratações Públicas, histórico de licitações e contratos</div>
              </div>
            </div>
          </div>
        </div>

        <div className="val-banner-v2">
          <div className="val-banner-v2-inner">
            <p>
              <strong>O score foi testado com dados históricos</strong> em 4.671 avaliações
              anuais de municípios entre 2021 e 2025, simulando cenários reais
              sem acesso a informações do futuro. A classificação provou ser consistente: municípios
              de Risco Alto registraram alto volume de contas atrasadas (Restos a Pagar) em 51,9% dos casos no
              ano seguinte, contra apenas 9,2% entre os de Risco Baixo. A probabilidade
              do modelo acertar ao separar os bons e os maus pagadores foi de 74,4%.
            </p>
            <div className="val-stats-v2">
              <div><div className="val-stat-v2-n">4.671</div><div className="val-stat-v2-l">avaliações anuais testadas</div></div>
              <div><div className="val-stat-v2-n">51,9%</div><div className="val-stat-v2-l">atrasos crônicos no Risco Alto</div></div>
              <div><div className="val-stat-v2-n">9,2%</div><div className="val-stat-v2-l">atrasos crônicos no Risco Baixo</div></div>
            </div>
            <Link className="val-docs-link" href="/docs">
              Ver metodologia completa →
            </Link>
          </div>
        </div>

        <SiteFooter />
      </section>
    </SiteLayout>
  )
}

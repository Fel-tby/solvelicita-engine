import { useState } from 'react'
import SiteFooter from '../components/SiteFooter'
import SiteLayout from '../components/SiteLayout'
import { buildPageTitle, siteConfig } from '../config/site'

const DOC_LINKS = [
  { id: 'visao', label: 'Visão geral', group: 'Metodologia' },
  { id: 'formula', label: 'Fórmula e pesos', group: 'Metodologia' },
  { id: 'lliq', label: 'Liquidez Líquida', group: 'Metodologia' },
  { id: 'outros', label: 'Demais indicadores', group: 'Metodologia' },
  { id: 'caps', label: 'Caps duros', group: 'Metodologia' },
  { id: 'ausentes', label: 'Dados ausentes', group: 'Metodologia' },
  { id: 'val', label: 'Resultados', group: 'Validação' },
  { id: 'sens', label: 'Sensibilidade', group: 'Validação' },
  { id: 'erros', label: 'Erros extremos', group: 'Validação' },
  { id: 'glossario', label: 'Glossário', group: 'Referência' },
  { id: 'faq', label: 'FAQ', group: 'Referência' },
  { id: 'citar', label: 'Como citar', group: 'Referência' },
]

const DOC_GROUPS = [...new Set(DOC_LINKS.map((item) => item.group))]

export default function DocsPage() {
  const [docId, setDocId] = useState('visao')

  return (
    <SiteLayout
      title={buildPageTitle('Docs')}
      description={`Metodologia, validação e referência do ${siteConfig.brandName}.`}
      activeNav="docs"
    >
      <section id="docs" className="section active">
        <div id="docs-wrap" className="docs-wrap">
          <div className="docs-mobile-nav">
            <select
              className="docs-select"
              value={docId}
              onChange={(e) => setDocId(e.target.value)}
            >
              {DOC_GROUPS.map((group) => (
                <optgroup key={group} label={group}>
                  {DOC_LINKS.filter((item) => item.group === group).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          <div className="docs-sidebar">
            {DOC_GROUPS.map((group) => (
              <div key={group} className="docs-nav-group">
                <div className="docs-sec-title">{group}</div>
                <div className="docs-nav-links">
                  {DOC_LINKS.filter((item) => item.group === group).map((item) => (
                    <a
                      key={item.id}
                      className={`doc-link ${docId === item.id ? 'active' : ''}`}
                      href="#"
                      onClick={(event) => {
                        event.preventDefault()
                        setDocId(item.id)
                      }}
                    >
                      {item.label}
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="docs-content">
            <div id="doc-visao" className={`doc-page ${docId === 'visao' ? 'active' : ''}`}>
              <div className="doc-h1">Metodologia do Score de Solvência</div>
              <div className="doc-meta">Versão 7.0 · Março/2026 · <a href={siteConfig.repoUrl}>METODOLOGIA.md no GitHub</a></div>
              <div className="doc-callout"><strong>Aviso:</strong> Score baseado exclusivamente em dados oficiais declarados pelo próprio município ao Tesouro Nacional (SICONFI/RREO/RGF e FINBRA/DCA) e ao Governo Federal (CAUC/STN). Qualquer questionamento sobre os dados deve ser direcionado às fontes originais.</div>
              <div className="doc-h2">Objetivo</div>
              <p className="doc-p">SolveLicita responde à pergunta: <strong>"Essa prefeitura tem capacidade fiscal de honrar seus contratos?"</strong></p>
              <p className="doc-p">O score mede a capacidade estrutural de solvência de curto a médio prazo, com horizonte de 12 a 24 meses, compatível com o ciclo de contratos públicos de fornecimento, serviços continuados e obras.</p>
              <p className="doc-p">Não é um modelo de previsão de inadimplência pontual. É um score de risco relativo, construído exclusivamente com dados públicos.</p>
              <div className="doc-h2">Fontes</div>
              <table className="doc-table">
                <thead><tr><th>Fonte</th><th>O que contém</th><th>Frequência</th></tr></thead>
                <tbody>
                  <tr><td>SICONFI / RGF Anexo 05</td><td>Disponibilidade de caixa após Restos a Pagar</td><td>Bimestral / Semestral</td></tr>
                  <tr><td>SICONFI / RREO Anexo 01</td><td>Receita prevista e realizada</td><td>Bimestral / Semestral</td></tr>
                  <tr><td>SICONFI / RREO Anexo 07</td><td>Restos a Pagar processados e não processados</td><td>Bimestral / Semestral</td></tr>
                  <tr><td>CAUC / STN</td><td>Pendências para recebimento de repasses federais</td><td>Diária</td></tr>
                  <tr><td>FINBRA / DCA</td><td>Receita tributária própria, FPM, receita corrente</td><td>Anual</td></tr>
                  <tr><td>PNCP</td><td>Histórico de licitações e contratações diretas</td><td>Contínua</td></tr>
                </tbody>
              </table>
            </div>

            <div id="doc-formula" className={`doc-page ${docId === 'formula' ? 'active' : ''}`}>
              <div className="doc-h1">Fórmula e pesos</div>
              <div className="doc-meta">Versão 7.0</div>
              <div className="doc-code">S = 35·f(Lliq) + 10·(1 − Ccauc) + 15·g(Eorcam)<br /> + 15·Qsiconfi + 10·h(Autonomia) + 15·i(RPproc)</div>
              <p className="doc-p">O score é expresso em pontos (0–100). Cada componente é normalizado para [0, 1] antes de ser multiplicado pelo peso.</p>
              <div className="doc-h2">Classificação</div>
              <table className="doc-table">
                <thead><tr><th>Score</th><th>Classificação</th></tr></thead>
                <tbody>
                  <tr><td>≥ 80</td><td><span className="badge b-baixo">Risco Baixo</span></td></tr>
                  <tr><td>60 – 79</td><td><span className="badge b-medio">Risco Médio</span></td></tr>
                  <tr><td>40 – 59</td><td><span className="badge b-alto">Risco Alto</span></td></tr>
                  <tr><td>&lt; 40</td><td><span className="badge b-critico">Crítico</span></td></tr>
                </tbody>
              </table>
              <div className="doc-callout">Além do score numérico, dois <strong>caps duros</strong> operam independentemente: municípios com histórico de não entrega de dados não podem ser classificados como Risco Baixo; municípios com padrão crônico de RP Processados têm teto em Risco Médio.</div>
            </div>

            <div id="doc-lliq" className={`doc-page ${docId === 'lliq' ? 'active' : ''}`}>
              <div className="doc-h1">Liquidez Líquida (Lliq)</div>
              <div className="doc-meta">Peso 35% · Fonte: RGF Anexo 05</div>
              <div className="doc-code">Lliq = (DCL_total_pós_RP − DCL_RPPS_pós_RP) / Receita_Realizada</div>
              <p className="doc-p">Extraído do RGF Anexo 05 (Demonstrativo da Disponibilidade de Caixa) do período mais recente entregue pelo município. O componente RPPS é subtraído por ter caixa vinculado de uso restrito, incluí-lo distorceria a liquidez real.</p>
              <div className="doc-h2">Curva de pontuação</div>
              <table className="doc-table">
                <thead><tr><th>Lliq</th><th>Pontuação</th><th>Interpretação</th></tr></thead>
                <tbody>
                  <tr><td>≥ 0,35</td><td>1,00</td><td>Folga de liquidez sólida</td></tr>
                  <tr><td>0,10 – 0,35</td><td>linear 0,60 → 1,00</td><td>Liquidez razoável</td></tr>
                  <tr><td>0,00 – 0,10</td><td>linear 0,35 → 0,60</td><td>Liquidez positiva, mas estreita</td></tr>
                  <tr><td>−0,50 – 0,00</td><td>linear 0,00 → 0,35</td><td>Passivo imediato maior que caixa</td></tr>
                  <tr><td>&lt; −0,50</td><td>0,00 + flag</td><td>Anomalia, dado suspeito</td></tr>
                </tbody>
              </table>
              <div className="doc-h2">Por que DCL pós-RP e não Caixa Bruto</div>
              <p className="doc-p">A versão anterior (v5.x) usava Saldo de Caixa (DCA) e Restos a Pagar (RREO Anexo 07) como variáveis independentes. Por construção contábil, esses dois indicadores são altamente correlacionados negativamente, o modelo penalizava duas vezes o mesmo fenômeno.</p>
              <p className="doc-p">A fusão em Lliq via RGF Anexo 05 elimina a multicolinearidade e eleva a frequência de atualização de anual (DCA) para bimestral/semestral (RGF).</p>
            </div>

            <div id="doc-outros" className={`doc-page ${docId === 'outros' ? 'active' : ''}`}>
              <div className="doc-h1">Demais indicadores</div>
              <div className="doc-h2">Execução Orçamentária (Eorcam) — 15%</div>
              <p className="doc-p">Mede se o município arrecada o que planejou. Usa média ponderada por recência (2020–2025). A zona saudável é 90–105%, excesso por verba extraordinária também é penalizado.</p>
              <div className="doc-h2">Qualidade SICONFI (Qsiconfi) — 15%</div>
              <p className="doc-p">Proporção de anos (2020–2025) em que o município entregou o RREO ao Tesouro. Dado ausente não é sinal neutro, equivale a rebaixamento automático.</p>
              <div className="doc-h2">RP Crônicos (RPproc) — 15%</div>
              <p className="doc-p">Contagem de anos em que rproc_pct &gt; 3%. Municípios com 5 ou mais anos crônicos têm classificação máxima travada em Risco Médio.</p>
              <div className="doc-h2">Autonomia Tributária — 10%</div>
              <p className="doc-p">Receita própria (IPTU, ISS, ITBI, taxas) como proporção da receita corrente. Municípios com autonomia abaixo de 8% da RCL recebem flag autonomia_critica, dependência total do FPM, que oscila 20–30% entre meses.</p>
              <div className="doc-h2">Bloqueio Federal (Ccauc) — 10%</div>
              <p className="doc-p">Único indicador verificado externamente pelo Governo Federal, não autodeclarado. Qualquer pendência grave zera a contribuição do componente.</p>
            </div>

            <div id="doc-caps" className={`doc-page ${docId === 'caps' ? 'active' : ''}`}>
              <div className="doc-h1">Caps duros de classificação</div>
              <div className="doc-callout">Caps duros são restrições independentes do score calculado. Um município pode ter score numérico alto e ainda assim ter sua classificação rebaixada.</div>
              <div className="doc-h2">Cap de Transparência</div>
              <table className="doc-table">
                <thead><tr><th>Anos entregues (de 6)</th><th>Cap máximo</th></tr></thead>
                <tbody>
                  <tr><td>≥ 4 de 6</td><td>Sem restrição</td></tr>
                  <tr><td>3 de 6</td><td><span className="badge b-medio">Teto: Risco Médio</span></td></tr>
                  <tr><td>≤ 2 de 6</td><td><span className="badge b-alto">Teto: Risco Alto</span></td></tr>
                  <tr><td>0 de 6</td><td>Sem Dados</td></tr>
                </tbody>
              </table>
              <div className="doc-h2">Cap de Cronicidade</div>
              <p className="doc-p">Municípios com n_anos_cronicos ≥ 5 têm classificação máxima travada em Risco Médio, independente do score numérico.</p>
            </div>

            <div id="doc-ausentes" className={`doc-page ${docId === 'ausentes' ? 'active' : ''}`}>
              <div className="doc-h1">Tratamento de dados ausentes</div>
              <table className="doc-table">
                <thead><tr><th>Situação</th><th>Comportamento</th></tr></thead>
                <tbody>
                  <tr><td>Município sem RREO (0 anos)</td><td>Score não calculado — Sem Dados</td></tr>
                  <tr><td>RGF Anexo 05 fora da janela temporal</td><td>Confidence decay proporcional em Lliq + flag dado_defasado</td></tr>
                  <tr><td>Apenas coluna pré-RPNP disponível</td><td>lliq_parcial = True + penalidade de 5 pts</td></tr>
                  <tr><td>Lliq anômalo (&lt; −0,50)</td><td>Capping em −0,50 + flag dado_suspeito</td></tr>
                  <tr><td>rproc_pct indisponível em algum ano</td><td>Ano excluído do cômputo de n_anos_cronicos</td></tr>
                  <tr><td>Município ausente no CAUC</td><td>Pior caso (Ccauc = 1,0) — conservador</td></tr>
                  <tr><td>DCA ausente</td><td>Contribuição = 0 — penaliza ausência</td></tr>
                </tbody>
              </table>
            </div>

            <div id="doc-val" className={`doc-page ${docId === 'val' ? 'active' : ''}`}>
              <div className="doc-h1">Validação Retroativa</div>
              <div className="doc-meta">Walk-forward · 2020–2025 · <a href={siteConfig.repoUrl}>VALIDACAO.md no GitHub</a></div>
              <p className="doc-p">O score é calculado com dados de T0 e o desfecho observado é rproc_pct em T1. Réplica da situação real de uso: previsão de comportamento futuro a partir de informação presente, sem acesso a dados do período avaliado.</p>
              <div className="metric-row">
                <div className="metric-card"><div className="metric-n">881</div><div className="metric-l">pares walk-forward</div></div>
                <div className="metric-card"><div className="metric-n">342</div><div className="metric-l">era completa (com lliq)</div></div>
                <div className="metric-card"><div className="metric-n">539</div><div className="metric-l">era parcial (sem lliq)</div></div>
              </div>
              <div className="doc-h2">Correlação de Spearman</div>
              <table className="doc-table">
                <thead><tr><th>Par</th><th>n</th><th>r</th><th>p</th></tr></thead>
                <tbody>
                  <tr><td>2020 → 2021</td><td>172</td><td>−0,091</td><td>0,233 n.s. ⚠ COVID</td></tr>
                  <tr><td>2021 → 2022</td><td>183</td><td>−0,302</td><td>&lt; 0,001 ***</td></tr>
                  <tr><td>2022 → 2023</td><td>182</td><td>−0,362</td><td>&lt; 0,001 ***</td></tr>
                  <tr><td>2023 → 2024</td><td>166</td><td>−0,363</td><td>&lt; 0,001 ***</td></tr>
                  <tr><td>2024 → 2025</td><td>178</td><td>−0,337</td><td>&lt; 0,001 ***</td></tr>
                </tbody>
              </table>
              <div className="doc-h2">AUC-ROC (desfecho: rproc_T1 &gt; 3%)</div>
              <div className="metric-row">
                <div className="metric-card"><div className="metric-n" style={{ color: 'var(--accent)' }}>0,750</div><div className="metric-l">era completa</div></div>
                <div className="metric-card"><div className="metric-n">0,643</div><div className="metric-l">era parcial</div></div>
                <div className="metric-card"><div className="metric-n" style={{ color: 'var(--green)' }}>5,7×</div><div className="metric-l">Alto vs Baixo</div></div>
              </div>
              <div className="doc-callout">Municípios classificados como Risco Alto têm <strong>5,7× mais probabilidade</strong> de se tornarem crônicos no ano seguinte do que os de Risco Baixo. O gradiente é monótono e sem inversões.</div>
            </div>

            <div id="doc-sens" className={`doc-page ${docId === 'sens' ? 'active' : ''}`}>
              <div className="doc-h1">Análise de Sensibilidade</div>
              <div className="doc-h2">1. Exclusão de 2020 como T0</div>
              <p className="doc-p">O par 2020→2021 quebra a sequência (r=−0,091 n.s.). A causa são os repasses emergenciais da LC 173/2020 (COVID), que inflaram os indicadores de municípios com perfil fiscal deteriorado.</p>
              <table className="doc-table">
                <thead><tr><th>Era</th><th>AUC (com 2020)</th><th>AUC (sem 2020)</th><th>Delta</th></tr></thead>
                <tbody>
                  <tr><td>Era Parcial</td><td>0,643</td><td>0,706</td><td style={{ color: 'var(--green)' }}>+0,063</td></tr>
                  <tr><td>Era Completa</td><td>0,750</td><td>0,750</td><td>0,000</td></tr>
                </tbody>
              </table>
              <div className="doc-h2">2. Remoção de RPproc (circularidade)</div>
              <table className="doc-table">
                <thead><tr><th>Era</th><th>AUC com RPproc</th><th>AUC sem RPproc</th><th>Delta</th></tr></thead>
                <tbody>
                  <tr><td>Era Parcial</td><td>0,643</td><td>0,547</td><td style={{ color: 'var(--red)' }}>−0,096</td></tr>
                  <tr><td>Era Completa</td><td>0,750</td><td>0,642</td><td style={{ color: 'var(--red)' }}>−0,108</td></tr>
                </tbody>
              </table>
              <p className="doc-p">O AUC sem RPproc na era completa (0,642) ainda discrimina moderadamente, o sinal de lliq, eorcam e qsiconfi é real e independente.</p>
            </div>

            <div id="doc-erros" className={`doc-page ${docId === 'erros' ? 'active' : ''}`}>
              <div className="doc-h1">Erros Extremos — Era Completa</div>
              <div className="doc-h2">Falsos positivos (classificados como Alto/Crítico, rproc T1 &lt; 1%)</div>
              <p className="doc-p">Todos os casos têm score entre 55–60, fronteira exata da classe Alto. Nenhum no núcleo da classificação. Concentração na fronteira é esperada estatisticamente.</p>
              <div className="doc-h2">Falsos negativos (classificados como Baixo/Médio, rproc T1 &gt; 5%)</div>
              <p className="doc-p">Padrão dominante: liquidez positiva em T0 seguida de deterioração abrupta de RP em T1. Choque que nenhum modelo anual consegue antecipar sem dados infraanuais.</p>
              <div className="doc-callout">Mitigação recomendada: monitoramento trimestral de rproc_pct para municípios com score entre 70–90 e n_anos_cronicos ≥ 1.</div>
            </div>

            <div id="doc-glossario" className={`doc-page ${docId === 'glossario' ? 'active' : ''}`}>
              <div className="doc-h1">Glossário</div>
              <table className="doc-table">
                <thead><tr><th>Termo</th><th>Definição</th></tr></thead>
                <tbody>
                  <tr><td>Lliq</td><td>Liquidez Líquida. DCL pós-RP excluindo RPPS, normalizada pela Receita Realizada</td></tr>
                  <tr><td>DCL</td><td>Disponibilidade de Caixa Líquida após dedução de Restos a Pagar</td></tr>
                  <tr><td>RP Processados</td><td>Despesas já liquidadas mas não pagas ao fornecedor</td></tr>
                  <tr><td>RP Não Processados</td><td>Despesas empenhadas mas ainda não liquidadas</td></tr>
                  <tr><td>RPPS</td><td>Regime Próprio de Previdência Social, caixa vinculado, excluído do Lliq</td></tr>
                  <tr><td>Eorcam</td><td>Execução Orçamentária. Receita realizada / receita prevista, em %</td></tr>
                  <tr><td>Ccauc</td><td>Score de pendência no CAUC. 0,0 = regular; 1,0 = pendência grave</td></tr>
                  <tr><td>rproc_pct</td><td>RP processados liquidados a pagar como % da Receita Realizada</td></tr>
                  <tr><td>n_anos_cronicos</td><td>Nº de anos em que rproc_pct &gt; 3%</td></tr>
                  <tr><td>FPM</td><td>Fundo de Participação dos Municípios, principal transferência federal</td></tr>
                  <tr><td>RGF</td><td>Relatório de Gestão Fiscal</td></tr>
                  <tr><td>RREO</td><td>Relatório Resumido da Execução Orçamentária</td></tr>
                  <tr><td>CAUC</td><td>Cadastro Único de Convênios</td></tr>
                  <tr><td>AUC-ROC</td><td>Área sob a curva ROC, mede poder discriminativo do modelo</td></tr>
                </tbody>
              </table>
            </div>

            <div id="doc-faq" className={`doc-page ${docId === 'faq' ? 'active' : ''}`}>
              <div className="doc-h1">FAQ</div>
              <div className="doc-h2">Por que meu município está como Risco Alto?</div>
              <p className="doc-p">O score reflete dados declarados pelo próprio município ao Tesouro Nacional. Se o score é baixo, algum dos seis indicadores fiscais está deteriorado. A ficha individual no dashboard mostra qual componente está puxando o score para baixo.</p>
              <div className="doc-h2">Com que frequência os dados são atualizados?</div>
              <p className="doc-p">Depende da fonte. CAUC é coletado a cada nova rodada do pipeline (em geral mensal). SICONFI é bimestral/semestral. DCA/FINBRA tem defasagem anual estrutural de até 14 meses.</p>
              <div className="doc-h2">O score substitui due diligence?</div>
              <p className="doc-p">Não. É um indicador de risco relativo baseado em dados públicos declarados. Não substitui análise de fluxo de caixa diário, auditoria do Balanço Patrimonial, ou due diligence jurídica.</p>
              <div className="doc-h2">Como reportar um erro?</div>
              <p className="doc-p">Use a <a href="/contato">seção de Contato</a> com assunto "Feedback técnico". Erros nos dados de origem devem ser direcionados à fonte original (SICONFI, CAUC ou DCA).</p>
            </div>

            <div id="doc-citar" className={`doc-page ${docId === 'citar' ? 'active' : ''}`}>
              <div className="doc-h1">Como citar</div>
              <div className="doc-code">
                {`> ${siteConfig.brandName}. Score de Solvência Municipal. ${siteConfig.foundedYear}.`}
                <br />
                {`> Disponível em: ${siteConfig.siteUrl}`}
                <br />
                {`> Código e metodologia: ${siteConfig.repoUrl}`}
              </div>
              <div className="doc-h2">Licença</div>
              <p className="doc-p">{`Código sob licença ${siteConfig.license}. Dados são de fontes públicas federais.`}</p>
            </div>
          </div>
        </div>
        <SiteFooter />
      </section>
    </SiteLayout>
  )
}

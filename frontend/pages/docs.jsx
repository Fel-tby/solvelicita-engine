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
              <div className="doc-code doc-formula">S = 35·f(Lliq) + 10·(1 − Ccauc)<br />+ 15·g(Eorcam) + 15·Qsiconfi + 10·h(Autonomia) + 15·i(RPproc)</div>
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
              <div className="doc-code doc-formula">Lliq = (DCL_total_pós_RP − DCL_RPPS_pós_RP) / Receita_Realizada</div>
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
              <p className="doc-p">Contagem de anos em que rproc_pct &gt; 3%. Municípios com 4 ou mais anos crônicos têm classificação máxima travada em Risco Médio.</p>
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
              <p className="doc-p">Municípios com n_anos_cronicos ≥ 4 têm classificação máxima travada em Risco Médio, independente do score numérico.</p>
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
              <div className="doc-meta">Walk-forward · base oficial 2021–2025 · <a href={siteConfig.repoUrl}>VALIDACAO.md no GitHub</a></div>
              <p className="doc-p">A validação compara o score calculado em um ano com o comportamento fiscal observado no ano seguinte. Esse desenho reproduz o uso real do modelo: ordenar risco futuro sem acesso a informações do período que ainda não aconteceu.</p>
              <div className="doc-callout"><strong>Nota metodológica:</strong> nesta validação, os componentes de bloqueio federal e autonomia tributária foram mantidos fixos por falta de série histórica comparável em toda a base. Por isso, o desempenho observado reflete principalmente o sinal de Liquidez Líquida, Execução Orçamentária, qualidade de entrega ao SICONFI e, no modelo operacional, também do histórico de atrasos recorrentes.</div>
              <div className="metric-row">
                <div className="metric-card"><div className="metric-n">4.671</div><div className="metric-l">pares válidos com score pleno</div></div>
                <div className="metric-card"><div className="metric-n">905</div><div className="metric-l">eventos crônicos na base principal</div></div>
                <div className="metric-card"><div className="metric-n">1.431</div><div className="metric-l">municípios em 9 UFs do Nordeste</div></div>
              </div>
              <div className="doc-h2">Modelo operacional</div>
              <table className="doc-table">
                <thead><tr><th>Métrica</th><th>Valor</th></tr></thead>
                <tbody>
                  <tr><td>Pares válidos</td><td>4.671</td></tr>
                  <tr><td>Eventos crônicos</td><td>905 (19,4%)</td></tr>
                  <tr><td>Spearman</td><td>−0,3827</td></tr>
                  <tr><td>AUC-ROC</td><td>0,7443</td></tr>
                </tbody>
              </table>
              <div className="doc-h2">Gradiente de risco</div>
              <table className="doc-table">
                <thead><tr><th>Classe no ano-base</th><th>n</th><th>Mediana de atrasos no ano seguinte</th><th>% de casos crônicos no ano seguinte</th></tr></thead>
                <tbody>
                  <tr><td><span className="badge b-baixo">Risco Baixo</span></td><td>783</td><td>0,35%</td><td>9,2%</td></tr>
                  <tr><td><span className="badge b-medio">Risco Médio</span></td><td>3.267</td><td>0,71%</td><td>15,6%</td></tr>
                  <tr><td><span className="badge b-alto">Risco Alto</span></td><td>617</td><td>3,07%</td><td>51,9%</td></tr>
                  <tr><td><span className="badge b-critico">Crítico</span></td><td>4</td><td>9,64%</td><td>50,0%</td></tr>
                </tbody>
              </table>
              <div className="metric-row">
                <div className="metric-card"><div className="metric-n" style={{ color: 'var(--accent)' }}>0,7443</div><div className="metric-l">AUC-ROC do modelo operacional</div></div>
                <div className="metric-card"><div className="metric-n">−0,3827</div><div className="metric-l">Spearman entre score atual e atraso no ano seguinte</div></div>
                <div className="metric-card"><div className="metric-n" style={{ color: 'var(--green)' }}>5,6×</div><div className="metric-l">Alto vs Baixo em cronicidade futura</div></div>
              </div>
              <div className="doc-callout">O gradiente do modelo operacional é monotônico e sem inversões relevantes. Municípios classificados como <strong>Risco Alto têm 5,6× mais probabilidade</strong> de se tornarem crônicos no ano seguinte do que os de Risco Baixo.</div>
            </div>

            <div id="doc-sens" className={`doc-page ${docId === 'sens' ? 'active' : ''}`}>
              <div className="doc-h1">Análise de Sensibilidade</div>
              <div className="doc-h2">Teste sem o componente de atrasos recorrentes</div>
              <p className="doc-p">Também rodamos uma versão mais conservadora do modelo sem o componente que mede o histórico de atrasos recorrentes. O objetivo é verificar quanto da capacidade preditiva permanece quando o score depende apenas dos demais sinais fiscais disponíveis na base histórica.</p>
              <table className="doc-table">
                <thead><tr><th>Métrica</th><th>Valor</th></tr></thead>
                <tbody>
                  <tr><td>Pares válidos</td><td>4.671</td></tr>
                  <tr><td>Eventos crônicos</td><td>905 (19,4%)</td></tr>
                  <tr><td>Spearman</td><td>−0,2632</td></tr>
                  <tr><td>AUC-ROC</td><td>0,6621</td></tr>
                </tbody>
              </table>
              <div className="doc-h2">Gradiente de risco no teste conservador</div>
              <table className="doc-table">
                <thead><tr><th>Classe no ano-base</th><th>n</th><th>Mediana de atrasos no ano seguinte</th><th>% de casos crônicos no ano seguinte</th></tr></thead>
                <tbody>
                  <tr><td><span className="badge b-baixo">Risco Baixo</span></td><td>568</td><td>0,45%</td><td>13,2%</td></tr>
                  <tr><td><span className="badge b-medio">Risco Médio</span></td><td>3.307</td><td>0,68%</td><td>16,4%</td></tr>
                  <tr><td><span className="badge b-alto">Risco Alto</span></td><td>777</td><td>1,68%</td><td>35,8%</td></tr>
                  <tr><td><span className="badge b-critico">Crítico</span></td><td>19</td><td>2,25%</td><td>42,1%</td></tr>
                </tbody>
              </table>
              <p className="doc-p">Sem esse componente, o modelo perde parte do poder discriminatório, mas continua acima do acaso. O AUC cai de 0,7443 para 0,6621 e o gradiente permanece visível: municípios classificados como Risco Alto ficam com probabilidade 2,7× maior de atraso crônico futuro do que os de Risco Baixo.</p>
              <div className="doc-callout">A leitura conjunta é estável: o histórico de atrasos recorrentes carrega sinal importante, mas o modelo não depende exclusivamente dele para ordenar risco. Em leitura conservadora, o poder discriminatório do score fica entre <strong>0,6621 e 0,7443</strong>.</div>
            </div>

            <div id="doc-erros" className={`doc-page ${docId === 'erros' ? 'active' : ''}`}>
              <div className="doc-h1">Erros Extremos — Modelo Operacional</div>
              <div className="doc-h2">Falsos positivos (classificados como Alto/Crítico, com atraso inferior a 1% no ano seguinte)</div>
              <table className="doc-table">
                <thead><tr><th>Município</th><th>UF</th><th>Score no ano-base</th><th>Atraso no ano seguinte</th></tr></thead>
                <tbody>
                  <tr><td>Vertentes</td><td>PE</td><td>59.9</td><td>0,50%</td></tr>
                  <tr><td>Cajazeiras</td><td>PB</td><td>59.9</td><td>0,26%</td></tr>
                  <tr><td>Ceará-Mirim</td><td>RN</td><td>59.9</td><td>0,58%</td></tr>
                  <tr><td>Santana do Seridó</td><td>RN</td><td>59.8</td><td>0,76%</td></tr>
                  <tr><td>Aracoiaba</td><td>CE</td><td>59.8</td><td>-1,98%</td></tr>
                  <tr><td>Jatobá</td><td>PE</td><td>59.8</td><td>0,18%</td></tr>
                  <tr><td>Santa Rita</td><td>PB</td><td>59.7</td><td>0,18%</td></tr>
                  <tr><td>Serrinha</td><td>BA</td><td>59.7</td><td>0,29%</td></tr>
                </tbody>
              </table>
              <p className="doc-p">Os falsos positivos seguem concentrados na fronteira da classe Alto, todos em torno de 60 pontos. Isso é compatível com erro de classificação próximo ao limiar, não com falha estrutural no núcleo do ranking.</p>
              <div className="doc-h2">Falsos negativos (classificados como Baixo/Médio, com atraso acima de 5% no ano seguinte)</div>
              <table className="doc-table">
                <thead><tr><th>Município</th><th>UF</th><th>Score no ano-base</th><th>Atraso no ano seguinte</th></tr></thead>
                <tbody>
                  <tr><td>Tupanatinga</td><td>PE</td><td>72.2</td><td>22,12%</td></tr>
                  <tr><td>Santana do Cariri</td><td>CE</td><td>83.8</td><td>20,43%</td></tr>
                  <tr><td>Iguatu</td><td>CE</td><td>68.1</td><td>20,36%</td></tr>
                  <tr><td>Lucena</td><td>PB</td><td>65.4</td><td>20,02%</td></tr>
                  <tr><td>Ibirajuba</td><td>PE</td><td>60.5</td><td>19,78%</td></tr>
                  <tr><td>Barra do Mendes</td><td>BA</td><td>69.6</td><td>18,57%</td></tr>
                  <tr><td>Manoel Vitorino</td><td>BA</td><td>75.3</td><td>18,47%</td></tr>
                  <tr><td>Bom Conselho</td><td>PE</td><td>61.5</td><td>18,35%</td></tr>
                </tbody>
              </table>
              <p className="doc-p">O padrão dominante nos falsos negativos graves continua sendo deterioração abrupta dos atrasos no ano seguinte, após um ano-base ainda relativamente saudável. Esse é o tipo de choque anual que o modelo consegue ordenar apenas parcialmente sem sinais infraanuais.</p>
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
              <div className="doc-code doc-cite">
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

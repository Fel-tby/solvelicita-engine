# Metodologia do Score de Solvência

**Versão:** 8.0  
**Última atualização:** Maio/2026  
**Aviso:** Score baseado exclusivamente em dados oficiais declarados pelo próprio município ao Tesouro Nacional (SICONFI/RREO/RGF e FINBRA/DCA) e ao Governo Federal (CAUC/STN). Qualquer questionamento sobre os dados deve ser direcionado às fontes originais.

> A evidência empírica de que o score discrimina risco real está documentada separadamente em [VALIDACAO.md](./VALIDACAO.md).

---

## Objetivo

SolveLicita responde à pergunta: **"Essa prefeitura tem capacidade fiscal de honrar seus contratos?"**

O score mede a **capacidade estrutural de solvência de curto a médio prazo** de municípios brasileiros, com horizonte de avaliação de 12 a 24 meses, compatível com o ciclo de contratos públicos de fornecimento, serviços continuados e obras.

Não é um modelo de previsão de inadimplência pontual. É um score de risco relativo baseado em múltiplas dimensões fiscais, construído exclusivamente com dados públicos.

---

## Fórmula

```
S = ICF_Lliq·40·f(Lliq) + 10·(1 − Ccauc)
  + ICF_Eorcam·15·g(Eorcam)
  + ICF_Autonomia·15·h(Autonomia)
  + ICF_RPproc·20·i(RPproc)
```

O score é expresso em pontos (0–100). `Qsiconfi` deixa de ter peso numérico
e passa a operar como medida de cobertura/cap duro; a qualidade formal dos
dados SICONFI entra via ICF.

---

## Variáveis

| Variável | Fonte | O que mede | Peso | Frequência |
|---|---|---|---|---|
| `Lliq` | RGF Anexo 05 (SICONFI) | Liquidez líquida: DCL pós-RP excl. RPPS / Receita Realizada | 40% × ICF | Bimestral/Sem. |
| `Ccauc` | CAUC/STN | Gravidade das pendências para recebimento federal | 10% | Diária |
| `Eorcam` | RREO Anexo 01 (SICONFI) | Execução orçamentária média ponderada por recência | 15% × ICF | Bimestral/Sem. |
| `Qsiconfi` | RREO histórico | % de anos com RREO entregue (2021–ano corrente) + cap duro | 0% | Histórico |
| `Autonomia` | DCA/FINBRA | Receita tributária própria / receita corrente | 15% × ICF | Anual |
| `RPproc` | RREO Anexo 07 (SICONFI) | Cronicidade de restos a pagar liquidados não pagos | 20% × ICF | Bimestral/Sem. |

---

## ICF SICONFI — Modulador de confiança

O ICF é o Ranking da Qualidade da Informação Contábil e Fiscal publicado pelo
Tesouro Nacional. Ele não substitui os indicadores fiscais; ele reduz a
contribuição dos indicadores cuja fonte é dado contábil/fiscal declarado pelo
município ao SICONFI.

| Conceito ICF | Fator aplicado |
|---|---|
| A | 1.00 |
| B | 0.95 |
| C | 0.90 |
| D | 0.85 |
| E | 0.80 |
| Sem ICF | 0.80 |

### Alinhamento temporal

O ranking é publicado por edição, mas avalia o exercício anterior. Portanto:

| Edição do ranking | Exercício avaliado no score |
|---|---|
| Ranking 2025 | Dados SICONFI de 2024 |
| Ranking 2026 prévio | Dados SICONFI de 2025 |

Para cada componente, o pipeline usa o ICF do mesmo exercício do dado fiscal
avaliado. Quando o mesmo exercício ainda não existe, usa o ICF mais recente
anterior do município e marca `icf_defasado = True`. O dado prévio oficial é
permitido, mas fica marcado como `icf_previo = True` até a publicação final.

O CAUC não recebe ICF, pois é verificação externa e não dado contábil
autodeclarado. `Qsiconfi` também não recebe peso numérico; ele preserva o cap
por ausência de entrega.

---

## Variável principal: Liquidez Líquida (Lliq)

### Definição

```
Lliq = (DCL_total_pós_RP − DCL_RPPS_pós_RP) / Receita_Realizada
```

Todos os componentes são extraídos do **RGF Anexo 05** (Demonstrativo da Disponibilidade de Caixa) do período mais recente entregue pelo município.

- `DCL_total_pós_RP`: Disponibilidade de Caixa Líquida após dedução dos Restos a Pagar totais (processados + não processados), extraído da linha `DisponibilidadeDeCaixaLiquidaAposRP`, conta `TOTAL (IV) = (I + II + III)`
- `DCL_RPPS_pós_RP`: porção atribuída ao RPPS — subtraída para evitar distorção do regime previdenciário próprio, que tem caixa vinculado de uso restrito
- `Receita_Realizada`: receita total realizada do exercício, extraída do RREO Anexo 01 (`ReceitasExcetoIntraOrcamentarias`, coluna `Até o Bimestre (c)`)

### Por que DCL pós-RP e não Caixa Bruto

A versão anterior (v5.x) usava Saldo de Caixa (DCA) e Restos a Pagar (RREO Anexo 07) como variáveis independentes. Esses dois indicadores são altamente correlacionados negativamente por construção contábil: quando RP Processados sobem, o caixa líquido disponível cai. Tratá-los separadamente causava **duplicação de sinal** — o modelo penalizava duas vezes o mesmo fenômeno. A fusão em `Lliq` via RGF Anexo 05 elimina a multicolinearidade, usa a mesma fonte temporal para ambos os componentes, e eleva a frequência do indicador mais importante de anual (DCA) para bimestral/semestral (RGF).

### Regime de entrega do RGF por porte

| Porte | Frequência RGF | Janela de dado aceitável |
|---|---|---|
| > 50.000 hab. | Bimestral (Q) | ≤ 90 dias |
| ≤ 50.000 hab. | Semestral (S) | ≤ 210 dias |

Quando ambas as periodicidades estão disponíveis para o mesmo exercício, o dado **quadrimestral (Q) tem prioridade** sobre o semestral (S).

Na coleta do SICONFI, municípios com até 50 mil habitantes podem aparecer tanto no **RGF normal** quanto no **RGF Simplificado**. O pipeline considera ambos os caminhos válidos e tenta a versão **semestral (S)** antes de concluir ausência de dado para esse porte.

### Fallback pré-RPNP (lliq_parcial)

Quando o município entregou RGF Anexo 05 mas **sem a coluna pós-RPNP** (padrão anterior a certas versões do SICONFI), o sistema usa a coluna pré-RPNP como proxy:

```
lliq_parcial = DCL_bruta_pré_RP / Receita_Realizada
```

O município recebe flag `lliq_parcial = True` no output. Esta versão **superestima a liquidez** por não deduzir RPNP — o modelo compensa com penalidade adicional de 5 pts no score.

### Confidence decay (defasagem de dado)

Quando o RGF Anexo 05 mais recente disponível está **fora da janela aceitável** para o porte:

- Aplica-se penalidade proporcional sobre a contribuição de `Lliq` no score final (`decay_fator < 1.0`)
- O município recebe flag `dado_defasado = True` e `dias_atraso` no output
- O fator de decay é calculado como: `decay = max(0, 1 − (dias_atraso − janela) / 365)`

### Curva de pontuação

| Lliq | Pontuação | Interpretação |
|---|---|---|
| ≥ 0.35 | 1.00 (máximo) | Folga de liquidez sólida |
| 0.10 – 0.35 | linear 0.60→1.00 | Liquidez razoável |
| 0.00 – 0.10 | linear 0.35→0.60 | Liquidez positiva, mas estreita |
| −0.50 – 0.00 | linear 0.00→0.35 | Passivo imediato maior que caixa |
| < −0.50 | 0.00 + ⚑ | Anomalia — `dado_suspeito = True` |

Valores `Lliq < −0.50` são sinalizados como `dado_suspeito = True` e têm score calculado com capping em −0.50. Possível causa: distorção de RPPS, cancelamento contábil de empenhos sem liquidação, ou erro de envio ao SICONFI.

---

## Ccauc — Risco de Bloqueio Federal (peso 10%)

Mede a **gravidade** das pendências do município no CAUC (Cadastro Único de Convênios). É o único indicador genuinamente independente das fontes SICONFI: não é autodeclarado pelo município, é verificado externamente pelo Governo Federal.

| Tipo de pendência | Exemplos | Impacto |
|---|---|---|
| **Grave** | RFB, PGFN, CADIN, SISTN Dívida, LRF Executivo, TCU, CGU | `Ccauc = 1.0` → 0 pts |
| **Moderada** | FGTS, TST, SIOPS, SIOPE, LRF Legislativo, SICONV | Penalidade proporcional, teto 0.5 |
| **Leve** | Pendências de reporte (SICONFI, MCASP, PCASP) | Penalidade mínima |
| **Regular** | Sem pendências | `Ccauc = 0.0` → 10 pts |

A coleta é feita via Portal de Dados Abertos do Tesouro (CKAN) — snapshot nacional filtrado para os municípios cobertos pela base publicada.

---

## Eorcam — Execução Orçamentária (peso 15%)

Mede se o município arrecada o que planejou. Usa **média ponderada por recência** sobre os exercícios com RREO entregue (2020–2025):

Para fins de cobertura, contam como entrega válida tanto o **RREO normal** quanto o **RREO Simplificado**, desde que o **Anexo 01** contenha as colunas necessárias para `Receita Prevista` e `Receita Realizada`.

| Exercício | Peso relativo |
|---|---|
| 2025 | 40% |
| 2024 | 25% |
| 2023 | 20% |
| 2022 | 10% |
| 2021 | 5% |
| 2020 | 0% (reserva histórica, não entra na média ponderada) |

A zona saudável é entre 90% e 105%.

| Execução (%) | Pontuação | Interpretação |
|---|---|---|
| ≥ 90% e ≤ 105% | 1.0 (máximo) | Gestão precisa e previsível |
| 105% – 120% | decaimento linear 1.0→0.5 | Excesso por verba extraordinária |
| > 120% | 0.5 (teto) | Arrecadação anômala, não sustentável |
| 70% – 90% | proporcional 0.0→1.0 | Zona de atenção |
| ≤ 70% | 0.0 | Colapso de arrecadação |

---

## Qsiconfi — Cobertura SICONFI (peso 0% + cap duro)

Proporção de anos (2021 até o ano corrente) em que o município enviou o RREO ao Tesouro Nacional.

Na contagem de `anos_entregues`, o pipeline considera entrega válida quando existe **RREO normal ou RREO Simplificado** com **Anexo 01** utilizável no exercício.

### Pontuação de cobertura

| Anos entregues (de 6) | Cobertura |
|---|---|
| 6 | 1.0 |
| 5 | 0.83 |
| 4 | 0.67 |
| 3 | 0.50 |
| 2 | 0.33 |
| 1 | 0.17 |
| 0 | 0.0 |

Essa cobertura não soma pontos diretamente no score v8.0. Ela continua sendo
exportada como `qsiconfi` e `anos_entregues`, e continua acionando caps duros
de classificação.

### Cap duro de classificação

Independente do score numérico calculado pelos demais indicadores:

| Anos entregues | Cap máximo de classificação |
|---|---|
| ≥ 4 de 6 | Sem restrição |
| 3 de 6 | Teto: 🟡 Risco Médio |
| ≤ 2 de 6 | Teto: 🔴 Risco Alto |
| 0 de 6 | ⚫ Sem Dados |

**Justificativa:** dado ausente não é sinal neutro — é risco não quantificável, que em gestão de crédito equivale a rebaixamento automático.

---

## Autonomia — Receita Tributária Própria (peso 15% × ICF + flag)

Calculado a partir do FINBRA/DCA. Mede a proporção da receita corrente gerada autonomamente pelo município (IPTU, ISS, ITBI e taxas), sem depender de repasses federais ou estaduais.

**Flag de alerta:** `autonomia_critica` é resolvida por `UF`, usando template da região correspondente. A régua da flag é mais conservadora que a curva de pontuação e serve como sinal operacional de dependência estrutural.

| Região | Limiar crítico (`autonomia_critica = True`) |
|---|---|
| Norte | `< 5,30% da RCL` |
| Nordeste | `< 5,00% da RCL` |
| Centro-Oeste | `< 7,50% da RCL` |
| Sudeste | `< 6,60% da RCL` |
| Sul | `< 7,80% da RCL` |

Pontuação via **curva sigmoid calibrada por porte populacional e resolvida por região**:

| Porte | População |
|---|---|
| Micro | < 10.000 hab. |
| Pequeno | 10.000 – 50.000 |
| Médio | 50.000 – 200.000 |
| Grande | > 200.000 hab. |

Os parâmetros regionais deslocam o ponto de inflexão da curva (`mu`) por porte. A inclinação (`k`) permanece fixa por porte na versão atual:

| Porte | `k` |
|---|---|
| Micro | `98.6` |
| Pequeno | `77.9` |
| Médio | `96.2` |
| Grande | `306.2` |

| Região | `mu` Micro | `mu` Pequeno | `mu` Médio | `mu` Grande |
|---|---|---|---|---|
| Norte | `3,14%` | `2,93%` | `3,37%` | `2,42%` |
| Nordeste | `2,96%` | `2,76%` | `3,18%` | `2,28%` |
| Centro-Oeste | `4,44%` | `4,14%` | `4,76%` | `3,42%` |
| Sudeste | `3,90%` | `3,64%` | `4,19%` | `3,00%` |
| Sul | `4,63%` | `4,32%` | `4,98%` | `3,57%` |

**Leitura prática:** um mesmo nível de receita própria recebe nota mais alta em regiões estruturalmente menos autônomas e nota mais baixa em regiões onde a capacidade tributária média é maior. O scorer continua único; muda apenas o template regional aplicado à `UF`.

**Semântica do indicador:** a regionalização não altera o peso de `Autonomia` no score nem cria cap duro adicional de classificação. Ela apenas ajusta a interpretação relativa da mesma métrica entre macrorregiões brasileiras.

---

## RPproc — Cronicidade de Restos a Pagar (peso 20% × ICF + cap duro)

Mede se o município tem **padrão crônico de não pagamento** de despesas já liquidadas.

### Indicador base: rproc_pct

```
rproc_pct = RestosAPagarProcessadosENaoProcessadosLiquidadosAPagar / Receita_Realizada
```

Extraído do **RREO Anexo 07**, `cod_conta = RestosAPagarProcessadosENaoProcessadosLiquidadosAPagar`, coluna `Saldo e = (a+ b) - (c + d)`, linha `TOTAL (III) = (I + II)`.

Quando o município entrega apenas a versão simplificada do relatório, o pipeline tenta extrair o mesmo indicador a partir do **RREO Simplificado Anexo 07**. Se o anexo não existir em algum exercício, o ano é excluído do cômputo de `n_anos_cronicos`, mas isso não invalida automaticamente todo o município.

### n_anos_cronicos

Contagem de anos (sobre todos os exercícios 2020–2025 com RREO entregue) em que `rproc_pct > 3%`. Apenas anos **anteriores a T** são considerados no cálculo — sem uso de informação futura.

### Curva de pontuação

| n_anos_cronicos | rproc_norm | Interpretação |
|---|---|---|
| 0 | 1.00 | Nenhum padrão de atraso |
| 1 | 0.75 | Episódico |
| 2 | 0.50 | Recorrente |
| 3 | 0.30 | Preocupante |
| 4 | 0.10 | Grave |
| 5 ou 6 | 0.00 | Crônico estrutural |

### Cap duro de classificação

Municípios com `n_anos_cronicos ≥ 4` têm classificação máxima **travada em 🟡 Risco Médio**, independente do score numérico.

---

## Classificação de risco

| Score | Classificação |
|---|---|
| 75–100 | 🟢 Risco Baixo |
| 55–74 | 🟡 Risco Médio |
| 35–54 | 🔴 Risco Alto |
| 0–34 | ⛔ Crítico |
| — | ⚫ Sem Dados |

**Caps duros independentes do score numérico:**
- Transparência (`Qsiconfi`): ver seção acima
- Cronicidade de RP (`RPproc`): `n_anos_cronicos ≥ 4` → teto 🟡 Risco Médio

---

## Tratamento de dados ausentes

| Situação | Comportamento |
|---|---|
| Município sem RREO (0 anos) | Score não calculado — ⚫ Sem Dados |
| Município pequeno com entrega apenas simplificada | O pipeline tenta `RREO Simplificado` e `RGF Simplificado` antes de concluir ausência de dado |
| RGF Anexo 05 fora da janela temporal | Confidence decay: fator proporcional em `Lliq` + flag `dado_defasado` |
| Apenas coluna pré-RPNP disponível | `lliq_parcial = True` + penalidade de 5 pts |
| `Lliq` anômalo (< −0.50) | Capping em −0.50 + flag `dado_suspeito` |
| `rproc_pct` indisponível em algum ano | Ano excluído do cômputo de `n_anos_cronicos` |
| Município ausente no CAUC | Pior caso (`Ccauc = 1.0`) — conservador |
| DCA ausente (sem Autonomia) | Contribuição = 0 — penaliza ausência |

---

## Limitações

- `Lliq` mede liquidez estrutural declarada — não substitui análise de fluxo de caixa diário ou due diligence jurídica
- Dados SICONFI são autodeclarados pelo município — qualidade varia; o ICF reduz a contribuição de indicadores SICONFI com menor qualidade formal, enquanto `Qsiconfi` limita a classificação quando falta entrega
- CAUC é snapshot da data de coleta — pode mudar a qualquer momento; recoletar antes de qualquer decisão é recomendado
- DCA/FINBRA tem defasagem anual estrutural (~14 meses no pior caso) — afeta `Autonomia` apenas; `Lliq` usa RGF com defasagem máxima de 90–210 dias
- `Lliq` negativo extremo pode indicar distorção de RPPS ou cancelamento contábil de empenhos — flag `dado_suspeito` sinaliza, mas detecção completa requer auditoria manual do Balanço Patrimonial
- `rproc_pct` não distingue municípios que quitaram RP por pagamento real daqueles que quitaram por cancelamento contábil
- `Autonomia` agora usa calibração regional para as 5 macrorregiões brasileiras; ajustes finos por UF podem ser necessários à medida que a cobertura nacional amadurecer

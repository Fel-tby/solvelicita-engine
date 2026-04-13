# Validação Geral do Score de Solvência

**Versão do score:** 7.0  
**Última atualização:** Abril/2026  
**Referência cruzada:** [METODOLOGIA.md](./METODOLOGIA.md)

> Este documento registra a evidência empírica da validação geral do modelo em base nacional.
> Não descreve como o score é calculado — isso está em METODOLOGIA.md.

**Componentes neutralizados em ambos os testes:** CAUC foi fixado em `0.0` e Autonomia em `0.5`. Isso foi necessário porque essas duas variáveis não possuem série histórica compatível dentro do `siconfi_indicadores`, que é a base anual consolidada usada no backtest walk-forward. Em termos práticos, isso significa que o poder discriminatório observado abaixo vem de `Lliq`, `Eorcam`, `Qsiconfi` e, no teste operacional, também de `RPproc`.

---

## Estratégia

A validação usa **walk-forward por pares de anos consecutivos**: o score é calculado com dados de T0 e o desfecho observado é `rproc_pct` em T1. Isso replica a situação real de uso — o score prevê comportamento futuro a partir de informação presente, sem acesso a dados do período avaliado.

Este documento adota, como recorte oficial, a **base geral do modelo iniciada em 2021**. O desfecho binário continua sendo `rproc_pct > 3%` em T1 = **evento crônico**, o mesmo limiar usado internamente pelo score para classificar `n_anos_cronicos`.

Dois testes são apresentados sobre a mesma base:

1. **Modelo operacional** — score com `RPproc` ativo.
2. **Modelo sem RPproc** — score recalculado sem esse componente, para medir o desempenho do restante da estrutura do modelo.

---

## Dados

| Elemento | Valor |
|---|---|
| Escopo geográfico | 9 UFs do Nordeste calibradas neste estágio do modelo: AL, BA, CE, MA, PB, PE, PI, RN e SE |
| Universo | 1.431 municípios |
| Base walk-forward 2021–2025 | 4.824 pares município×ano |
| Base principal reportada neste documento | 4.671 pares com score pleno |
| Eventos crônicos na base principal | 905 (19,4%) |
| Horizonte observado | T0→T1 em janela anual |

As métricas centrais abaixo são reportadas sobre a base principal de 4.671 pares, que é a parcela do backtest em que o modelo roda com todos os componentes historicamente disponíveis neste recorte.

---

## Métricas de validação

Duas métricas são utilizadas, cada uma respondendo a uma pergunta distinta:

**Spearman** — *a ordenação do score corresponde à ordenação do risco real?*  
Correlação ordinal entre `score_T0` e `rproc_T1` sobre a escala contínua. Independe dos limiares de classificação.

**AUC-ROC** — *o score separa municípios que vão se tornar crônicos dos que não vão?*  
Probabilidade de que o score ordene corretamente um par aleatório (crônico vs não-crônico). AUC=0.50 equivale a aleatoriedade; AUC=1.0 equivale a separação perfeita.

---

## Resultados — Modelo Operacional

### Métricas principais

| Métrica | Valor |
|---|---|
| Pares válidos | 4.671 |
| Eventos crônicos | 905 (19,4%) |
| Spearman | **−0.3827** |
| AUC-ROC | **0.7443** |

O resultado indica que o modelo **ordena bem o risco futuro e discrimina de forma consistente** em base nacional. Um AUC de 0.7443 significa que, dado um município que se tornou crônico e outro que não se tornou, o score aponta o correto em aproximadamente 74% dos casos.

### Gradiente de risco

| Classe em T0 | n | Mediana rproc T1 | % crônicos em T1 |
|---|---|---|---|
| 🟢 Risco Baixo | 783 | 0,35% | 9,2% |
| 🟡 Risco Médio | 3.267 | 0,71% | 15,6% |
| 🔴 Risco Alto | 617 | 3,07% | **51,9%** |
| ⚫ Risco Crítico | 4 | 9,64% | 50,0% |

O gradiente é monotônico e sem inversões relevantes. Municípios classificados como **Risco Alto** têm **5,6× mais probabilidade** de se tornarem crônicos no ano seguinte do que municípios classificados como **Risco Baixo**.

### Erros extremos

#### Falsos positivos (classificados como Alto/Crítico, rproc T1 < 1%)

| Município | UF | Score T0 | rproc T1 |
|---|---|---|---|
| Vertentes | PE | 59.9 | 0.50% |
| Cajazeiras | PB | 59.9 | 0.26% |
| Ceará-Mirim | RN | 59.9 | 0.58% |
| Santana do Seridó | RN | 59.8 | 0.76% |
| Aracoiaba | CE | 59.8 | -1.98% |
| Jatobá | PE | 59.8 | 0.18% |
| Santa Rita | PB | 59.7 | 0.18% |
| Serrinha | BA | 59.7 | 0.29% |

Os falsos positivos seguem concentrados na fronteira da classe Alto, todos em torno de 60 pontos. Isso é compatível com erro de classificação próximo ao limiar, não com falha estrutural no núcleo do ranking.

#### Falsos negativos (classificados como Baixo/Médio, rproc T1 > 5%)

| Município | UF | Score T0 | rproc T1 |
|---|---|---|---|
| Tupanatinga | PE | 72.2 | 22.12% |
| Santana do Cariri | CE | 83.8 | 20.43% |
| Iguatu | CE | 68.1 | 20.36% |
| Lucena | PB | 65.4 | 20.02% |
| Ibirajuba | PE | 60.5 | 19.78% |
| Barra do Mendes | BA | 69.6 | 18.57% |
| Manoel Vitorino | BA | 75.3 | 18.47% |
| Bom Conselho | PE | 61.5 | 18.35% |

O padrão dominante nos falsos negativos graves continua sendo deterioração abrupta de `rproc_pct` em T1 após um T0 ainda relativamente saudável. Isso é o tipo de choque anual que o modelo consegue ordenar apenas parcialmente sem dados infraanuais.

---

## Resultados — Modelo Sem RPproc

### Métricas principais

| Métrica | Valor |
|---|---|
| Pares válidos | 4.671 |
| Eventos crônicos | 905 (19,4%) |
| Spearman | **−0.2632** |
| AUC-ROC | **0.6621** |

Sem `RPproc`, o modelo perde poder discriminatório, mas **não colapsa para aleatoriedade**. Isso mostra que `Lliq`, `Eorcam` e `Qsiconfi` preservam sinal preditivo independente mesmo na ausência do componente historicamente mais próximo do desfecho.

### Gradiente de risco

| Classe em T0 | n | Mediana rproc T1 | % crônicos em T1 |
|---|---|---|---|
| 🟢 Risco Baixo | 568 | 0,45% | 13,2% |
| 🟡 Risco Médio | 3.307 | 0,68% | 16,4% |
| 🔴 Risco Alto | 777 | 1,68% | **35,8%** |
| ⚫ Risco Crítico | 19 | 2,25% | 42,1% |

O gradiente continua presente, embora menos íngreme. Municípios classificados como **Risco Alto** ficam com probabilidade **2,7× maior** de cronicidade futura do que municípios classificados como **Risco Baixo**.

---

## Leitura Conjunta

Os dois testes, rodados sobre a mesma base geral do modelo, apontam para a mesma conclusão central:

1. O modelo operacional entrega desempenho nacional sólido (`AUC = 0.7443`, `Spearman = −0.3827`).
2. A retirada de `RPproc` reduz esse desempenho (`AUC = 0.6621`, `Spearman = −0.2632`), mas preserva discriminação acima do acaso.
3. Isso indica que `RPproc` carrega sinal importante, mas que o modelo não depende exclusivamente dele para ordenar risco.

Em termos práticos, o intervalo relevante para leitura conservadora do poder discriminatório do score fica entre **0.6621** e **0.7443**, dependendo de se considerar ou não o componente `RPproc`.

---

## Limitações da validação

1. **CAUC e Autonomia neutralizados.** Os dois componentes foram mantidos como constantes por ausência de série histórica compatível no `siconfi_indicadores`. O desempenho observado não representa ainda o score com informação histórica completa desses blocos.

2. **Circularidade parcial de RPproc no teste operacional.** O evento validado em T1 é definido pela mesma família de variável (`rproc_pct`) que também alimenta `n_anos_cronicos` em T0. Por isso, o teste sem `RPproc` é importante como leitura complementar.

3. **Horizonte de um ano.** O score foi validado para prever cronicidade no exercício imediatamente seguinte. O desempenho em horizontes de 2+ anos não foi testado neste documento.

4. **Escopo regional deliberado.** Esta validação cobre apenas o Nordeste, que é a região para a qual o modelo está calibrado neste estágio. A leitura deste documento não deve ser extrapolada automaticamente para outras regiões sem recalibração específica.

---

## Reprodutibilidade

```bash
# Modelo operacional
python src/analysis/backtest_validacao.py --geral --excluir-t0 2020

# Modelo sem RPproc
python src/analysis/backtest_validacao.py --geral --sem-rproc --excluir-t0 2020
```

Saídas geradas em `data/analysis/geral/`:
- um CSV do modelo operacional com registro por par município×ano
- um relatório estatístico do modelo operacional
- um CSV do modelo sem `RPproc`
- um relatório estatístico do modelo sem `RPproc`

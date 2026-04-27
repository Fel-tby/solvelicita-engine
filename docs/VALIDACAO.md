# Validacao Geral do Score de Solvencia

**Versao do score:** 7.0  
**Ultima atualizacao:** Abril/2026  
**Referencia cruzada:** [METODOLOGIA.md](./METODOLOGIA.md)

> Este documento registra a evidencia empirica da validacao geral do modelo em base nacional.
> Nao descreve como o score e calculado - isso esta em METODOLOGIA.md.

**Componentes neutralizados em ambos os testes:** CAUC foi fixado em `0.0` e Autonomia em `0.5`. Isso foi necessario porque essas duas variaveis nao possuem serie historica compativel dentro do `siconfi_indicadores`, que e a base anual consolidada usada no backtest walk-forward. Em termos praticos, isso significa que o poder discriminatorio observado abaixo vem de `Lliq`, `Eorcam`, `Qsiconfi` e, no teste operacional, tambem de `RPproc`.

---

## Estrategia

A validacao usa **walk-forward por pares de anos consecutivos**: o score e calculado com dados de T0 e o desfecho observado e `rproc_pct` em T1. Isso replica a situacao real de uso - o score preve comportamento futuro a partir de informacao presente, sem acesso a dados do periodo avaliado.

Este documento adota, como recorte oficial, a **base nacional do modelo iniciada em 2021**. O ano T0=2020 foi excluido por ruido estrutural associado a COVID e aos repasses emergenciais da LC 173/2020. O desfecho binario continua sendo `rproc_pct > 3%` em T1 = **evento cronico**, o mesmo limiar usado internamente pelo score para classificar `n_anos_cronicos`.

Dois testes sao apresentados sobre a mesma base:

1. **Modelo operacional** - score com `RPproc` ativo.
2. **Modelo sem RPproc** - score recalculado sem esse componente, para medir o desempenho do restante da estrutura do modelo.

---

## Dados

| Elemento | Valor |
|---|---|
| Escopo geografico | 27 UFs do Brasil |
| Universo coletado | 5.570 municipios |
| Municipios com pares validos | 5.131 municipios |
| Base walk-forward 2021-2025 | 17.615 pares municipio-ano |
| Base principal reportada neste documento | 17.168 pares com score pleno |
| Eventos cronicos na base principal | 1.663 (9,7%) |
| Horizonte observado | T0->T1 em janela anual |

As metricas centrais abaixo sao reportadas sobre a base principal de 17.168 pares, que e a parcela do backtest em que o modelo roda com todos os componentes historicamente disponiveis neste recorte.

### Numeracao por regiao

| # | Regiao | UFs | Pares totais | Pares na base principal | Municipios | Eventos cronicos na base principal |
|---:|---|---|---:|---:|---:|---:|
| 1 | Norte | AC, AM, AP, PA, RO, RR, TO | 1.520 | 1.467 | 430 | 204 (13,9%) |
| 2 | Nordeste | AL, BA, CE, MA, PB, PE, PI, RN, SE | 6.058 | 5.879 | 1.733 | 1.035 (17,6%) |
| 3 | Centro-Oeste | DF, GO, MS, MT | 1.591 | 1.573 | 442 | 37 (2,4%) |
| 4 | Sudeste | ES, MG, RJ, SP | 5.313 | 5.144 | 1.552 | 338 (6,6%) |
| 5 | Sul | PR, RS, SC | 3.133 | 3.105 | 974 | 49 (1,6%) |

---

## Metricas de validacao

Duas metricas sao utilizadas, cada uma respondendo a uma pergunta distinta:

**Spearman** - *a ordenacao do score corresponde a ordenacao do risco real?*  
Correlacao ordinal entre `score_T0` e `rproc_T1` sobre a escala continua. Independe dos limiares de classificacao.

**AUC-ROC** - *o score separa municipios que vao se tornar cronicos dos que nao vao?*  
Probabilidade de que o score ordene corretamente um par aleatorio (cronico vs nao-cronico). AUC=0.50 equivale a aleatoriedade; AUC=1.0 equivale a separacao perfeita.

---

## Resultados - Modelo Operacional

### Metricas principais

| Metrica | Valor |
|---|---:|
| Pares validos totais | 17.615 |
| Pares na base principal | 17.168 |
| Eventos cronicos na base principal | 1.663 (9,7%) |
| Spearman | **-0.4119** |
| AUC-ROC | **0.8153** |

O resultado indica que o modelo **ordena bem o risco futuro e discrimina de forma consistente** em base nacional. Um AUC de 0.8153 significa que, dado um municipio que se tornou cronico e outro que nao se tornou, o score aponta o correto em aproximadamente 82% dos casos.

### Resultado por regiao

| # | Regiao | Pares | Eventos | % eventos | Spearman | AUC-ROC | Score medio | Mediana rproc T1 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Norte | 1.467 | 204 | 13,9% | **-0.4600** | **0.8115** | 71,45 | 0,45% |
| 2 | Nordeste | 5.879 | 1.035 | 17,6% | **-0.3527** | **0.7372** | 71,12 | 0,67% |
| 3 | Centro-Oeste | 1.573 | 37 | 2,4% | **-0.2340** | **0.8012** | 79,21 | 0,11% |
| 4 | Sudeste | 5.144 | 338 | 6,6% | **-0.2839** | **0.8168** | 79,88 | 0,12% |
| 5 | Sul | 3.105 | 49 | 1,6% | **-0.1118** | **0.8101** | 81,18 | 0,04% |

O desempenho regional mostra discriminacao forte em quatro regioes e moderada no Nordeste. A leitura do Nordeste e particularmente importante porque concentra a maior prevalencia de eventos cronicos da base principal: 1.035 dos 1.663 eventos nacionais.

### Resultado por regiao e era

| Regiao | Era | Pares | Municipios | Eventos | % eventos | Spearman | AUC-ROC |
|---|---|---:|---:|---:|---:|---:|---:|
| Centro-Oeste | Completa | 1.573 | 442 | 37 | 2,4% | -0.2340 | 0.8012 |
| Nordeste | Completa | 5.879 | 1.726 | 1.035 | 17,6% | -0.3527 | 0.7372 |
| Nordeste | Parcial | 179 | 139 | 34 | 19,0% | -0.2003 | 0.7219 |
| Norte | Completa | 1.467 | 427 | 204 | 13,9% | -0.4600 | 0.8115 |
| Norte | Parcial | 53 | 44 | 10 | 18,9% | -0.4072 | 0.7035 |
| Sudeste | Completa | 5.144 | 1.539 | 338 | 6,6% | -0.2839 | 0.8168 |
| Sudeste | Parcial | 169 | 141 | 13 | 7,7% | -0.0755 | 0.7650 |
| Sul | Completa | 3.105 | 972 | 49 | 1,6% | -0.1118 | 0.8101 |

### Gradiente de risco

| Classe em T0 | n | Mediana rproc T1 | % cronicos em T1 |
|---|---:|---:|---:|
| Risco Baixo | 6.557 | 0,07% | 2,4% |
| Risco Medio | 9.490 | 0,31% | 10,1% |
| Risco Alto | 1.115 | 2,89% | **48,4%** |
| Critico | 6 | 18,92% | 66,7% |

O gradiente e monotonicamente crescente. Municipios classificados como **Risco Alto** tem aproximadamente **20,2x mais probabilidade** de se tornarem cronicos no ano seguinte do que municipios classificados como **Risco Baixo**.

### Erros extremos

#### Falsos positivos (classificados como Alto/Critico, rproc T1 < 1%)

| Municipio | UF | Score T0 | rproc T1 |
|---|---|---:|---:|
| Humaita | AM | 59,9 | 0,35% |
| Faria Lemos | MG | 59,9 | 0,86% |
| Cachoeira Alta | GO | 59,9 | 0,24% |
| Vertentes | PE | 59,9 | 0,50% |
| Agua Nova | RN | 59,9 | -0,34% |
| Ceara-Mirim | RN | 59,9 | 0,58% |
| Cajazeiras | PB | 59,8 | 0,26% |
| Santana do Serido | RN | 59,8 | 0,76% |

Os falsos positivos seguem concentrados na fronteira da classe Alto, todos em torno de 60 pontos. Isso e compativel com erro de classificacao proximo ao limiar, nao com falha estrutural no nucleo do ranking.

#### Falsos negativos (classificados como Baixo/Medio, rproc T1 > 5%)

| Municipio | UF | Score T0 | rproc T1 |
|---|---|---:|---:|
| Apiai | SP | 60,8 | 56,85% |
| Inaja | PR | 81,7 | 29,61% |
| Guairaca | PR | 68,8 | 28,68% |
| Fronteira dos Vales | MG | 73,3 | 26,40% |
| Carlopolis | PR | 92,3 | 26,15% |
| Mocajuba | PA | 60,0 | 24,36% |
| Sao Lourenco da Serra | SP | 63,7 | 23,89% |
| Tupanatinga | PE | 72,2 | 22,12% |

O padrao dominante nos falsos negativos graves continua sendo deterioracao abrupta de `rproc_pct` em T1 apos um T0 ainda relativamente saudavel. Isso e o tipo de choque anual que o modelo consegue ordenar apenas parcialmente sem dados infraanuais.

---

## Resultados - Modelo Sem RPproc

### Metricas principais

| Metrica | Valor |
|---|---:|
| Pares validos totais | 17.615 |
| Pares na base principal | 17.168 |
| Eventos cronicos na base principal | 1.663 (9,7%) |
| Spearman | **-0.3510** |
| AUC-ROC | **0.7516** |

Sem `RPproc`, o modelo perde poder discriminatorio, mas **nao colapsa para aleatoriedade**. Isso mostra que `Lliq`, `Eorcam` e `Qsiconfi` preservam sinal preditivo independente mesmo na ausencia do componente historicamente mais proximo do desfecho.

### Resultado por regiao

| # | Regiao | Pares | Eventos | % eventos | Spearman | AUC-ROC | Score medio | Mediana rproc T1 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Norte | 1.467 | 204 | 13,9% | **-0.3962** | **0.7547** | 67,94 | 0,45% |
| 2 | Nordeste | 5.879 | 1.035 | 17,6% | **-0.2329** | **0.6504** | 68,42 | 0,67% |
| 3 | Centro-Oeste | 1.573 | 37 | 2,4% | **-0.2126** | **0.7709** | 75,91 | 0,11% |
| 4 | Sudeste | 5.144 | 338 | 6,6% | **-0.2349** | **0.7548** | 77,45 | 0,12% |
| 5 | Sul | 3.105 | 49 | 1,6% | **-0.0875** | **0.7583** | 78,16 | 0,04% |

### Gradiente de risco

| Classe em T0 | n | Mediana rproc T1 | % cronicos em T1 |
|---|---:|---:|---:|
| Risco Baixo | 4.931 | 0,07% | 3,3% |
| Risco Medio | 10.520 | 0,23% | 9,5% |
| Risco Alto | 1.699 | 1,11% | **29,0%** |
| Critico | 18 | 2,46% | 38,9% |

O gradiente continua presente, embora menos ingreme. Municipios classificados como **Risco Alto** ficam com probabilidade **8,8x maior** de cronicidade futura do que municipios classificados como **Risco Baixo**.

---

## Leitura Conjunta

Os dois testes, rodados sobre a mesma base nacional do modelo, apontam para a mesma conclusao central:

1. O modelo operacional entrega desempenho nacional forte (`AUC = 0.8153`, `Spearman = -0.4119`).
2. A retirada de `RPproc` reduz esse desempenho (`AUC = 0.7516`, `Spearman = -0.3510`), mas preserva discriminacao claramente acima do acaso.
3. Isso indica que `RPproc` carrega sinal importante, mas que o modelo nao depende exclusivamente dele para ordenar risco.
4. A validacao regional mostra comportamento consistente: todas as regioes mantem AUC acima de 0.73 no modelo operacional, com quatro regioes acima de 0.80.

Em termos praticos, o intervalo relevante para leitura conservadora do poder discriminatorio do score fica entre **0.7516** e **0.8153**, dependendo de se considerar ou nao o componente `RPproc`.

---

## Limitacoes da validacao

1. **CAUC e Autonomia neutralizados.** Os dois componentes foram mantidos como constantes por ausencia de serie historica compativel no `siconfi_indicadores`. O desempenho observado nao representa ainda o score com informacao historica completa desses blocos.

2. **Circularidade parcial de RPproc no teste operacional.** O evento validado em T1 e definido pela mesma familia de variavel (`rproc_pct`) que tambem alimenta `n_anos_cronicos` em T0. Por isso, o teste sem `RPproc` e importante como leitura complementar.

3. **Horizonte de um ano.** O score foi validado para prever cronicidade no exercicio imediatamente seguinte. O desempenho em horizontes de 2+ anos nao foi testado neste documento.

4. **Heterogeneidade regional.** A base agora e nacional, mas a prevalencia do evento varia muito por regiao. O Nordeste concentra mais eventos cronicos e apresenta AUC operacional menor que as demais regioes, enquanto Sul e Centro-Oeste tem baixa prevalencia e exigem leitura mais cautelosa de Spearman.

5. **Amostras pequenas em algumas UFs.** A leitura por UF e informativa, mas algumas unidades federativas possuem poucos eventos positivos, o que torna a AUC individual insuficiente ou instavel. Por isso, a leitura regional e nacional deve ter prioridade.

---

## Reprodutibilidade

```bash
# Modelo operacional
python src/analysis/backtest_validacao.py --geral --excluir-t0 2020

# Modelo sem RPproc
python src/analysis/backtest_validacao.py --geral --sem-rproc --excluir-t0 2020
```

Saidas geradas em `data/analysis/geral/`:

- um CSV do modelo operacional com registro por par municipio-ano
- um relatorio estatistico do modelo operacional
- um CSV do modelo sem `RPproc`
- um relatorio estatistico do modelo sem `RPproc`

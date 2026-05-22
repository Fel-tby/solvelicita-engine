# Validacao Geral do Score de Solvencia

**Versao do score:** 8.0

**Ultima atualizacao:** Maio/2026

**Referencia cruzada:** [METODOLOGIA.md](./METODOLOGIA.md)

Este documento registra a evidencia empirica da validacao geral do modelo em base nacional. A metodologia de calculo esta documentada separadamente em [METODOLOGIA.md](./METODOLOGIA.md).

## Mudanca metodologica validada

A validacao foi rerodada apos a mudanca v8.0:

| Item | Tratamento no backtest v8.0 |
|---|---|
| `Qsiconfi` | Peso numerico 0%; permanece apenas como cap duro de classificacao |
| Ranking SICONFI ICF | Resolvido historicamente por municipio/ano e aplicado como modulador de confianca |
| Componentes modulados por ICF | `Lliq`, `Eorcam`, `RPproc` e a contribuicao neutra de `Autonomia` |
| CAUC | Fixado em `0.0`, por ausencia de serie historica compativel |
| Autonomia | Normalizada em `0.5`, por ausencia de serie historica compativel no `siconfi_indicadores` |

O ICF usa o ranking do mesmo exercicio quando disponivel; caso contrario, usa o ranking mais recente anterior e marca defasagem. Quando nao ha registro, aplica o fator conservador `0.80`.

## Estrategia

A validacao usa walk-forward por pares de anos consecutivos: o score e calculado com dados de T0 e o desfecho observado e `rproc_pct` em T1. O recorte oficial exclui T0=2020 por ruido estrutural associado a COVID e aos repasses emergenciais da LC 173/2020.

O desfecho binario continua sendo `rproc_pct > 3%` em T1, o mesmo limiar usado internamente pelo score para classificar anos cronicos de RPproc.

Dois testes sao apresentados:

1. **Modelo operacional:** score com `RPproc` ativo.
2. **Modelo sem RPproc:** score recalculado sem esse componente, para medir o desempenho do restante da estrutura do modelo.

## Dados

| Elemento | Valor |
|---|---:|
| Escopo geografico | 27 UFs |
| Universo coletado | 5.570 municipios |
| Municipios com pares validos | 5.134 municipios |
| Pares walk-forward totais | 17.698 |
| Base principal reportada | 17.248 pares na era completa |
| Eventos cronicos na base principal | 1.675 (9,7%) |
| Horizonte observado | T0 -> T1 em janela anual |

## Resultados - Modelo Operacional

| Metrica | Valor |
|---|---:|
| Pares validos totais | 17.698 |
| Pares na base principal | 17.248 |
| Spearman | **-0,4200** |
| AUC-ROC | **0,8085** |

O resultado indica que o modelo segue ordenando bem o risco futuro e discriminando de forma consistente em base nacional. Mesmo sem pontuacao direta de `Qsiconfi` e com penalizacao pelo ICF, o AUC da era completa permanece acima de 0,80.

### Resultado Por Regiao

| Regiao | Pares | Eventos | % eventos | Spearman | AUC-ROC | Score medio | Mediana rproc T1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Norte | 1.484 | 207 | 13,9% | -0,4668 | 0,8058 | 60,16 | 0,45% |
| Nordeste | 5.897 | 1.039 | 17,6% | -0,3193 | 0,7247 | 60,10 | 0,66% |
| Centro-Oeste | 1.583 | 39 | 2,5% | -0,2884 | 0,8148 | 65,96 | 0,11% |
| Sudeste | 5.167 | 340 | 6,6% | -0,3012 | 0,8089 | 69,17 | 0,12% |
| Sul | 3.117 | 50 | 1,6% | -0,1580 | 0,8613 | 70,82 | 0,04% |

### Gradiente Por Classe

| Classe T0 | Pares | Mediana rproc T1 | Cronicos T1 |
|---|---:|---:|---:|
| BAIXO | 213 | 0,04% | 0,5% |
| MEDIO | 5.371 | 0,08% | 2,4% |
| ALTO | 11.516 | 0,30% | 12,6% |
| CRITICO | 148 | 5,54% | 63,5% |

## Sensibilidade Sem RPproc

| Metrica | Valor |
|---|---:|
| Pares validos totais | 17.698 |
| Pares na base principal | 17.248 |
| Spearman | **-0,3798** |
| AUC-ROC | **0,7639** |

Sem `RPproc`, o modelo perde parte do poder discriminatorio, como esperado, mas nao colapsa para aleatoriedade. O intervalo conservador para leitura do desempenho fica entre **0,7639** e **0,8085**, dependendo de considerar ou nao o componente historicamente mais proximo do desfecho.

## Limitacoes

1. CAUC e Autonomia seguem sem serie historica propria no backtest. CAUC fica neutro e Autonomia usa norma `0.5` modulada pelo ICF.
2. `RPproc` tem circularidade parcial com o desfecho; por isso a sensibilidade sem `RPproc` deve ser lida junto do modelo operacional.
3. A era parcial tem baixa comparabilidade com a era completa porque `Lliq` nao estava disponivel no mesmo contrato historico.
4. T0=2020 foi excluido do recorte oficial por ruido estrutural externo.

## Reproducao

```bash
python src/analysis/backtest_validacao.py --geral --excluir-t0 2020
python src/analysis/backtest_validacao.py --geral --sem-rproc --excluir-t0 2020
```

Artefatos gerados:

| Artefato | Caminho |
|---|---|
| Pares - operacional | `data/analysis/geral/backtest_pares_geral_ex2020.csv` |
| Resumo - operacional | `data/analysis/geral/backtest_resumo_geral_ex2020.txt` |
| Pares - sem RPproc | `data/analysis/geral/backtest_pares_geral_sem_rproc_ex2020.csv` |
| Resumo - sem RPproc | `data/analysis/geral/backtest_resumo_geral_sem_rproc_ex2020.txt` |

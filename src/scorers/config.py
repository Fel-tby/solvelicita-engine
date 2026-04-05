# Sem imports de projeto; seguro importar de qualquer lugar sem sys.path
# Versao: 7.0 | Atualizado: Marco/2026

from datetime import date

# Pesos dos indicadores
PESOS = {
    "lliq": 35,       # v6.2: 30 -> +5 (melhor preditor, AUC=0.691)
    "ccauc": 10,      # v6.2: 20 -> -10 (AUC=0 no backtest; peso excessivo)
    "eorcam": 15,     # v6.2: 20 -> -5 (AUC sub-aleatorio como preditor isolado)
    "qsiconfi": 15,   # v6.2: 15 -> sem alteracao
    "autonomia": 10,  # v6.2: 10 -> sem alteracao
    "rproc": 15,      # v6.2: 5 -> +10 (AUC=0.609; 3x mais preditivo que eorcam)
}
assert sum(PESOS.values()) == 100, "Pesos nao somam 100"

# Anos de referencia
# Dinamico: sempre cobre os ultimos 6 anos completos. Em 2026 = 2020 AND 2025.
_ano_ref = date.today().year - 1  # ultimo ano com exercicio completo
ANOS_REF = list(range(_ano_ref - 5, _ano_ref + 1))
N_ANOS = 6

# Pesos de recencia para Eorcam
# Dinamico: pesos acompanham os ultimos 5 anos fechados da janela. Em 2026 = 2021 AND 2025.
PESOS_ANO = {
    _ano_ref: 0.40,
    _ano_ref - 1: 0.25,
    _ano_ref - 2: 0.20,
    _ano_ref - 3: 0.10,
    _ano_ref - 4: 0.05,
}

# Limiares de classificacao (v7.0)
# v6.2: 75 / 55 / 35 -> v7.0: 80 / 60 / 40
# Bandas uniformes de 20 pts. Classifier le daqui; nao hardcode nos scorers.
LIMIARES_SCORE = {
    "baixo": 80,  # [80-100] Risco Baixo
    "medio": 60,  # [60-79]  Risco Medio
    "alto": 40,   # [40-59]  Risco Alto
                  # [0-39]   Critico
}

# Caps duros de classificacao
# RProc: teto rebaixado de >=5 para >=4 anos cronicos
N_ANOS_CRONICOS_CAP_MEDIO = 4  # v6.2: 5 -> v7.0: 4 (>=4 anos -> teto medio)

# Qsiconfi: mantidos inalterados da v6.2
# 3 anos entregues -> teto medio | <=2 anos -> teto alto | 0 anos -> sem dados

# Limiares operacionais
LIMIAR_RPROC_CRONICO = 3.0    # % da receita; ano acima = cronico (inalterado)
LIMIAR_AUTONOMIA_CRIT = 0.08  # < 8% RCL = dependencia critica do FPM
LIMIAR_LLIQ_SUSPEITO = -0.50  # abaixo = dado_suspeito
JANELA_RGF_BIMESTRAL = 90     # dias; municipios > 50k hab
JANELA_RGF_SEMESTRAL = 210    # dias; municipios <= 50k hab

# Pendencias CAUC por gravidade
PENDENCIAS_GRAVES = {
    "Regularidade Fiscal (RFB)",
    "Regularidade PGFN",
    "CADIN",
    "SISTN (Dívida Consolidada)",
    "LRF - Limite Pessoal Executivo",
    "Adimplência TCU",
    "Adimplência CGU",
}

PENDENCIAS_MODERADAS = {
    "Regularidade FGTS",
    "Regularidade Trabalhista (TST)",
    "SIOPS (Saúde)",
    "SIOPE (Educação)",
    "SICONV/TRANSFEREGOV Prestação de Contas",
    "SISTN (Garantias)",
    "LRF - Limite Pessoal Legislativo",
}

# Mapa de fim de periodo RGF -> mes de referencia
# Usado pelo lliq_scorer para calcular dias de atraso do dado.
# Q = quadrimestral (municipios > 50k hab) | S = semestral (<= 50k hab)
FIM_PERIODO_MES = {
    ("Q", 1): 4,
    ("Q", 2): 8,
    ("Q", 3): 12,
    ("S", 1): 6,
    ("S", 2): 12,
}

# Sigmoid de Autonomia - parametros default (calibrados para PB 2020-2024)
# Estrutura: porte -> (mu, k)
# mu = mediana empirica do grupo | k = 2 / IQR empirico
# Rever anualmente apos nova coleta DCA. Nao alterar diretamente para novos
# estados; usar OVERRIDES_UF abaixo.
SIGMOID_AUTONOMIA_DEFAULT = {
    "micro": (0.0296, 98.6),
    "pequeno": (0.0276, 77.9),
    "médio": (0.0318, 96.2),
    "grande": (0.0228, 306.2),
}

# Overrides por UF
# Estrutura:
# OVERRIDES_UF = {
#     "CE": {
#         "pesos": {"lliq": 33, "rproc": 17},  # substitui apenas o que mudar
#         "sigmoid_autonomia": {                # substitui apenas o porte alterado
#             "micro": (0.0310, 95.0),
#         },
#     },
# }
# PB nao tem override; usa os defaults calibrados acima.
# Novos estados: calibrar sigmoid_autonomia com dados reais antes de adicionar aqui.
OVERRIDES_UF: dict[str, dict] = {}


def get_pesos(uf: str) -> dict:
    """
    Retorna os pesos dos indicadores para a UF informada.
    Aplica override parcial sobre PESOS se definido em OVERRIDES_UF.
    A soma dos pesos resultantes nao e validada aqui; overrides devem
    compensar internamente.
    """
    override = OVERRIDES_UF.get(uf.upper(), {}).get("pesos", {})
    return {**PESOS, **override}


def get_sigmoid_autonomia(uf: str, porte: str) -> tuple:
    """
    Retorna (mu, k) da sigmoid de Autonomia para a UF e porte informados.
    Fallback: parametros PB (SIGMOID_AUTONOMIA_DEFAULT) quando UF nao tem override.
    """
    uf_overrides = OVERRIDES_UF.get(uf.upper(), {}).get("sigmoid_autonomia", {})
    return uf_overrides.get(porte, SIGMOID_AUTONOMIA_DEFAULT[porte])

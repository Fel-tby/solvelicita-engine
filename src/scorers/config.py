# Sem imports de projeto; seguro importar de qualquer lugar sem sys.path
# Versao: 7.0 | Atualizado: Marco/2026

from datetime import date

from src.config.br_regions import (
    REGION_CENTER_WEST,
    REGION_NORTH,
    REGION_NORTHEAST,
    REGION_SOUTH,
    REGION_SOUTHEAST,
    get_region_for_uf,
)

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
# Dinamico: sempre cobre 2021 ate o ano corrente. Em 2026 = 2021 AND 2026.
ANO_INICIO_REF = 2021
_ano_ref = date.today().year
ANOS_REF = list(range(ANO_INICIO_REF, _ano_ref + 1))
N_ANOS = len(ANOS_REF)

# Pesos de recencia para EORCAM.
# EORCAM mede execucao orcamentaria anual; por isso usa apenas exercicios
# fechados. Em 2026 = 2021..2025, com 2025 recebendo o maior peso.
_ultimo_ano_eorcam = _ano_ref - 1
ANOS_EORCAM_REF = list(
    range(max(ANO_INICIO_REF, _ultimo_ano_eorcam - 4), _ultimo_ano_eorcam + 1)
)
_PESOS_EORCAM_BASE = [0.40, 0.25, 0.20, 0.10, 0.05]
PESOS_EORCAM_ANO = {
    ano: peso
    for ano, peso in zip(
        range(_ultimo_ano_eorcam, _ultimo_ano_eorcam - len(_PESOS_EORCAM_BASE), -1),
        _PESOS_EORCAM_BASE,
    )
    if ano in ANOS_EORCAM_REF
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
LIMIAR_AUTONOMIA_CRIT = 0.08  # baseline Nordeste; overrides regionais via helper
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

LIMIAR_AUTONOMIA_CRIT_POR_REGIAO = {
    REGION_NORTHEAST: 0.0500,
    REGION_NORTH: 0.0530,
    REGION_CENTER_WEST: 0.0750,
    REGION_SOUTH: 0.0780,
    REGION_SOUTHEAST: 0.0660,
}

SIGMOID_AUTONOMIA_POR_REGIAO = {
    REGION_NORTHEAST: {
        "micro": (0.0296, 98.6),
        "pequeno": (0.0276, 77.9),
        "médio": (0.0318, 96.2),
        "grande": (0.0228, 306.2),
    },
    REGION_NORTH: {
        "micro": (0.0314, 98.6),
        "pequeno": (0.0293, 77.9),
        "médio": (0.0337, 96.2),
        "grande": (0.0242, 306.2),
    },
    REGION_CENTER_WEST: {
        "micro": (0.0444, 98.6),
        "pequeno": (0.0414, 77.9),
        "médio": (0.0476, 96.2),
        "grande": (0.0342, 306.2),
    },
    REGION_SOUTH: {
        "micro": (0.0463, 98.6),
        "pequeno": (0.0432, 77.9),
        "médio": (0.0498, 96.2),
        "grande": (0.0357, 306.2),
    },
    REGION_SOUTHEAST: {
        "micro": (0.0390, 98.6),
        "pequeno": (0.0364, 77.9),
        "médio": (0.0419, 96.2),
        "grande": (0.0300, 306.2),
    },
}

# Overrides por UF
# Estrutura:
# OVERRIDES_UF = {
#     "CE": {
#         "pesos": {"lliq": 33, "rproc": 17},  # substitui apenas o que mudar
#         "limiar_autonomia_crit": 0.0810,      # ajuste fino opcional do limiar
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


def get_limiar_autonomia_crit(uf: str) -> float:
    """
    Retorna o limiar de autonomia critica por UF, resolvido via regiao.
    Permite override fino por UF sem alterar o template regional.
    """
    uf_upper = uf.upper()
    uf_override = OVERRIDES_UF.get(uf_upper, {}).get("limiar_autonomia_crit")
    if uf_override is not None:
        return float(uf_override)
    regiao = get_region_for_uf(uf_upper)
    return float(LIMIAR_AUTONOMIA_CRIT_POR_REGIAO[regiao])


def get_sigmoid_autonomia(uf: str, porte: str) -> tuple:
    """
    Retorna (mu, k) da sigmoid de Autonomia para a UF e porte informados.
    Resolucao: override por UF > template regional > baseline Nordeste.
    """
    uf_upper = uf.upper()
    uf_overrides = OVERRIDES_UF.get(uf_upper, {}).get("sigmoid_autonomia", {})
    if porte in uf_overrides:
        return uf_overrides[porte]

    regiao = get_region_for_uf(uf_upper)
    region_params = SIGMOID_AUTONOMIA_POR_REGIAO.get(regiao, SIGMOID_AUTONOMIA_DEFAULT)
    return region_params.get(porte, SIGMOID_AUTONOMIA_DEFAULT[porte])

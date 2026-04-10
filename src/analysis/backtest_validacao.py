"""
backtest_validacao.py - Validacao walk-forward do Score de Solvencia v7.0

Estrategia:
  Para cada par de anos consecutivos (T0, T1), calcula o score com dados
  disponiveis em T0 e usa rproc_pct observado em T1 como variavel de
  desfecho. Isso replica a situacao real de uso do score: prever
  comportamento futuro a partir de informacao presente.

Dois regimes de dados:
  Era Parcial  (2020->2021, 2021->2022, 2022->2023)
    lliq ausente - RGF Anexo 05 nao coletado para esse periodo.
    Apenas 55% dos pesos ativos (eorcam + qsiconfi + rproc).

  Era Completa (2023->2024, 2024->2025)
    Score pleno. Todos os componentes ativos exceto CAUC e Autonomia
    (ver limitacoes abaixo). 75% dos pesos ativos.

Modos de execucao:
  1. Analise por UF
     python src/analysis/backtest_validacao.py --uf PB
     python src/analysis/backtest_validacao.py --uf BA

  2. Analise agregada de todas as UFs disponiveis
     python src/analysis/backtest_validacao.py --geral

  3. Filtrar por regime de dados
     python src/analysis/backtest_validacao.py --uf PB --pares completa
     python src/analysis/backtest_validacao.py --uf PB --pares parcial
     python src/analysis/backtest_validacao.py --geral --pares completa
     python src/analysis/backtest_validacao.py --geral --pares parcial

  4. Analise de sensibilidade para circularidade de RPproc
     python src/analysis/backtest_validacao.py --uf PB --sem-rproc
     python src/analysis/backtest_validacao.py --geral --sem-rproc

  5. Analise de sensibilidade para anos atipicos
     python src/analysis/backtest_validacao.py --uf PB --excluir-t0 2020
     python src/analysis/backtest_validacao.py --uf PB --excluir-t0 2020 2021
     python src/analysis/backtest_validacao.py --geral --excluir-t0 2020

  6. Combinacoes de filtros
     python src/analysis/backtest_validacao.py --uf PB --pares completa --sem-rproc
     python src/analysis/backtest_validacao.py --geral --pares completa --excluir-t0 2020
     python src/analysis/backtest_validacao.py --geral --pares parcial --sem-rproc

Saida:
  data/analysis/<UF>/backtest_pares_<uf>.csv
  data/analysis/<UF>/backtest_resumo_<uf>.txt
  data/analysis/geral/backtest_pares_geral.csv
  data/analysis/geral/backtest_resumo_geral.txt
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

SRC_ROOT = Path(__file__).resolve().parent.parent
ROOT = SRC_ROOT.parent
sys.path.insert(0, str(SRC_ROOT))

from utils.paths import get_paths

ANALYSIS_ROOT = ROOT / "data" / "analysis"
ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
REQUIRED_COLUMNS = {
    "cod_ibge", "ano", "instituicao", "populacao", "entregou_rreo",
    "eorcam", "rproc_pct", "periodo_rgf"
}


# Anos com ruido estrutural externo conhecido.
ANOS_ATIPICOS = {
    2020: "COVID - repasses emergenciais LC 173/2020 distorcem eorcam e lliq"
}


def _normalizar_entregou_rreo(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["entregou_rreo"] = df["entregou_rreo"].map(
        {True: True, False: False, "True": True, "False": False}
    ).fillna(False)
    return df


def carregar_siconfi_uf(uf: str) -> pd.DataFrame:
    uf = uf.upper()
    paths = get_paths(uf)
    caminho = paths["processed"] / f"siconfi_indicadores_{uf.lower()}.csv"
    if not caminho.exists():
        raise FileNotFoundError(f"[ERRO] {caminho} nao encontrado.")

    df = pd.read_csv(caminho, dtype={"cod_ibge": str})
    faltantes = sorted(REQUIRED_COLUMNS - set(df.columns))
    if faltantes:
        raise ValueError(
            f"[ERRO] {caminho} nao segue o contrato anual esperado. "
            f"Colunas ausentes: {', '.join(faltantes)}"
        )
    df = _normalizar_entregou_rreo(df)
    df["uf"] = uf
    return df


def listar_ufs_disponiveis() -> list[str]:
    processed_root = ROOT / "data" / "processed"
    if not processed_root.exists():
        return []

    ufs = []
    for pasta in sorted(processed_root.iterdir()):
        if not pasta.is_dir():
            continue
        uf = pasta.name.upper()
        caminho = pasta / f"siconfi_indicadores_{uf.lower()}.csv"
        if caminho.exists():
            ufs.append(uf)
    return ufs


def get_analysis_dir(geral: bool, uf: str | None = None) -> Path:
    pasta = "geral" if geral else str(uf).upper()
    analysis_dir = ANALYSIS_ROOT / pasta
    analysis_dir.mkdir(parents=True, exist_ok=True)
    return analysis_dir


def carregar_siconfi_geral() -> tuple[pd.DataFrame, list[str], list[str]]:
    ufs = listar_ufs_disponiveis()
    if not ufs:
        raise FileNotFoundError(
            "[ERRO] Nenhum siconfi_indicadores_<uf>.csv encontrado em data/processed/<UF>."
        )

    frames = []
    ignoradas = []
    carregadas = []
    for uf in ufs:
        try:
            frames.append(carregar_siconfi_uf(uf))
            carregadas.append(uf)
        except ValueError:
            ignoradas.append(uf)

    if not frames:
        raise ValueError(
            "[ERRO] Nenhuma UF possui siconfi_indicadores_<uf>.csv no contrato anual esperado."
        )

    return pd.concat(frames, ignore_index=True), carregadas, ignoradas


def score_lliq(lliq):
    """
    Curva linear por segmentos - v7.0.
    Retorna (norm 0.0-1.0, flag_suspeito).
    """
    if pd.isna(lliq):
        return None, False

    suspeito = lliq < -0.50
    if suspeito:
        lliq = -0.50

    if lliq >= 0.35:
        return 1.00, suspeito
    if lliq >= 0.10:
        return round(0.60 + (lliq - 0.10) / 0.25 * 0.40, 4), suspeito
    if lliq >= 0.00:
        return round(0.35 + (lliq / 0.10) * 0.25, 4), suspeito
    return round(max(0.0, (lliq + 0.50) / 0.50 * 0.35), 4), suspeito


def score_eorcam(eorcam_pct):
    """Execucao orcamentaria - zona ideal 90-105%."""
    if pd.isna(eorcam_pct):
        return None
    e = eorcam_pct
    if 90.0 <= e <= 105.0:
        return 1.00
    if 105.0 < e <= 120.0:
        return 1.00 - (e - 105.0) / 15.0 * 0.50
    if e > 120.0:
        return 0.50
    if e >= 70.0:
        return (e - 70.0) / 20.0
    return 0.00


def eorcam_ponderado(df_mun, ano_t):
    """
    Media ponderada dos ultimos 5 anos de eorcam disponiveis ate T.
    Pesos decrescentes: 40, 25, 20, 10, 5.
    """
    pesos_rel = [40, 25, 20, 10, 5]
    anos_disp = sorted(
        df_mun[(df_mun["ano"] <= ano_t) & df_mun["eorcam"].notna()]["ano"].unique(),
        reverse=True,
    )
    total_peso = total_pond = 0.0
    for i, ano in enumerate(anos_disp[:5]):
        p = pesos_rel[i]
        total_pond += p * df_mun.loc[df_mun["ano"] == ano, "eorcam"].values[0]
        total_peso += p
    return total_pond / total_peso if total_peso > 0 else None


def score_qsiconfi(anos_entregues, max_anos):
    """Proporcao de anos com RREO entregue dentro da janela 2020-T."""
    return min(anos_entregues / max_anos, 1.0) if max_anos > 0 else 0.0


def score_rproc(n_cronicos):
    """
    Penalizacao por cronicidade de restos a pagar processados (> 3%).
    """
    tabela = {0: 1.00, 1: 0.75, 2: 0.50, 3: 0.30, 4: 0.10}
    return tabela.get(n_cronicos, 0.00)


# Espelho de scorers/config.py - manter sincronizado a cada versao.
PESOS = dict(lliq=35, cauc=10, eorcam=15, qsiconfi=15, autonomia=10, rproc=15)


def calcular_score(lliq_n, eorcam_n, qsiconfi_n, rproc_n,
                   cauc_n=0.0, autonomia_n=0.5,
                   incluir_rproc=True):
    """
    Agrega os componentes normalizados no score final (0-100).

    Componentes ausentes (None) ou explicitamente excluidos sao removidos
    e seus pesos redistribuidos proporcionalmente entre os ativos.
    """
    componentes = {
        "lliq": (lliq_n, PESOS["lliq"]),
        "cauc": (1 - cauc_n, PESOS["cauc"]),
        "eorcam": (eorcam_n, PESOS["eorcam"]),
        "qsiconfi": (qsiconfi_n, PESOS["qsiconfi"]),
        "autonomia": (autonomia_n, PESOS["autonomia"]),
        "rproc": (rproc_n, PESOS["rproc"]),
    }
    excluir = set()
    if lliq_n is None:
        excluir.add("lliq")
    if not incluir_rproc:
        excluir.add("rproc")

    ativos = {k: v for k, v in componentes.items() if k not in excluir}
    ativos = {k: (0.5 if v is None else v, p) for k, (v, p) in ativos.items()}

    peso_total = sum(p for _, p in ativos.values())
    score = sum(v * p for v, p in ativos.values()) / peso_total * 100
    era = "completa" if lliq_n is not None else "parcial"
    return round(score, 2), era


def classificar(score):
    """Limiares v7.0: >=80 Baixo | >=60 Medio | >=40 Alto | <40 Critico."""
    if score >= 80:
        return "BAIXO"
    if score >= 60:
        return "MEDIO"
    if score >= 40:
        return "ALTO"
    return "CRITICO"


PARES_ANOS = [
    (2020, 2021),
    (2021, 2022),
    (2022, 2023),
    (2023, 2024),
    (2024, 2025),
]


def construir_pares(df, incluir_rproc=True, excluir_t0=None):
    """
    Para cada par (T0, T1) e cada municipio com dados em ambos os anos,
    calcula o score com informacao disponivel em T0 e registra rproc_pct
    de T1 como desfecho.
    """
    excluir_t0 = set(excluir_t0 or [])

    parciais_2025 = set(df.loc[(df["ano"] == 2025) & df["periodo_rgf"].isna(), "cod_ibge"])

    registros = []
    for t0, t1 in PARES_ANOS:
        if t0 in excluir_t0:
            continue

        df_t0 = df[df["ano"] == t0].set_index("cod_ibge")
        df_t1 = df[df["ano"] == t1].set_index("cod_ibge")

        for cod in set(df_t0.index) & set(df_t1.index):
            row_t0 = df_t0.loc[cod]
            row_t1 = df_t1.loc[cod]
            rproc_t1 = row_t1["rproc_pct"]

            if t1 == 2025 and cod in parciais_2025:
                continue
            if pd.isna(rproc_t1):
                continue

            df_mun = df[df["cod_ibge"] == cod]

            eorcam_w = eorcam_ponderado(df_mun, t0)
            eorcam_n = score_eorcam(eorcam_w)

            lliq_raw = row_t0.get("lliq", np.nan)
            lliq_raw = None if pd.isna(lliq_raw) else lliq_raw
            lliq_n, suspeito = score_lliq(lliq_raw)

            anos_janela = list(range(2020, t0 + 1))
            anos_entregues = int(df_mun[
                df_mun["ano"].isin(anos_janela) & (df_mun["entregou_rreo"] == True)
            ].shape[0])
            qsiconfi_n = score_qsiconfi(anos_entregues, len(anos_janela))

            n_cronicos = int((
                df_mun[(df_mun["ano"] < t0) & df_mun["rproc_pct"].notna()]["rproc_pct"] > 3.0
            ).sum())
            rproc_n = score_rproc(n_cronicos)

            score, era = calcular_score(
                lliq_n,
                eorcam_n,
                qsiconfi_n,
                rproc_n,
                cauc_n=0.0,
                autonomia_n=0.5,
                incluir_rproc=incluir_rproc,
            )

            registros.append({
                "uf": row_t0.get("uf"),
                "cod_ibge": cod,
                "municipio": row_t0["instituicao"],
                "populacao": row_t0["populacao"],
                "ano_t0": t0,
                "ano_t1": t1,
                "era": era,
                "score_t0": score,
                "classe_t0": classificar(score),
                "lliq_raw": lliq_raw,
                "lliq_norm": lliq_n,
                "eorcam_w": round(eorcam_w, 2) if eorcam_w is not None else None,
                "eorcam_norm": round(eorcam_n, 4) if eorcam_n is not None else None,
                "qsiconfi_norm": round(qsiconfi_n, 4),
                "n_cronicos_t0": n_cronicos,
                "rproc_norm": round(rproc_n, 4),
                "rproc_t0": row_t0["rproc_pct"],
                "rproc_t1": rproc_t1,
                "dado_suspeito": suspeito,
            })

    return pd.DataFrame(registros)


def analise_spearman(pares, label):
    """Correlacao ordinal entre score_T0 e rproc_T1."""
    r, p = stats.spearmanr(pares["score_t0"], pares["rproc_t1"])
    return {"label": label, "n": len(pares), "r": round(r, 4), "p": round(p, 4)}


def analise_roc(pares, label, threshold=3.0):
    """
    AUC-ROC para o evento binario rproc_T1 > threshold.
    """
    try:
        from sklearn.metrics import roc_auc_score
    except ImportError:
        return {"label": label, "auc": "sklearn nao instalado"}

    y_true = (pares["rproc_t1"] > threshold).astype(int)
    if y_true.sum() < 3:
        return {"label": label, "auc": "n_positivos insuficiente (< 3)"}

    auc = roc_auc_score(y_true, 100 - pares["score_t0"])
    return {
        "label": label,
        "n": len(pares),
        "n_positivos": int(y_true.sum()),
        "pct_positivos": round(100 * y_true.mean(), 1),
        "auc": round(auc, 4),
    }


def tabela_desfecho_por_classe(pares):
    """
    Para cada classe de risco em T0: n, mediana de rproc_T1
    e proporcao que cruzou o limiar de 3% em T1.
    """
    linhas = []
    for classe in ["BAIXO", "MEDIO", "ALTO", "CRITICO"]:
        sub = pares[pares["classe_t0"] == classe]["rproc_t1"]
        if len(sub) == 0:
            continue
        linhas.append({
            "classe": classe,
            "n": len(sub),
            "mediana_rproc_t1": round(sub.median(), 2),
            "pct_cronicos_t1": round(100 * (sub > 3.0).mean(), 1),
        })
    return pd.DataFrame(linhas)


def _resumo_por_uf(pares: pd.DataFrame) -> pd.DataFrame:
    return (
        pares.groupby("uf")
        .agg(
            n_pares=("score_t0", "count"),
            municipios=("cod_ibge", "nunique"),
            score_med=("score_t0", "mean"),
            rproc_t1_med=("rproc_t1", "median"),
        )
        .reset_index()
        .sort_values("uf")
    )


def _forca_spearman(r: float) -> str:
    ar = abs(r)
    if ar >= 0.30:
        return "forte"
    if ar >= 0.10:
        return "moderado"
    return "fraco"


def _forca_auc(auc: float) -> str:
    if auc >= 0.80:
        return "forte"
    if auc >= 0.70:
        return "moderado"
    if auc >= 0.60:
        return "fraco"
    return "baixo"


def _leitura_executiva(r: float | None, auc: float | None) -> str:
    if r is None and auc is None:
        return "amostra insuficiente para leitura confiavel"
    if r is not None and auc is not None:
        if abs(r) >= 0.30 and auc >= 0.70:
            return "score ordena bem o risco futuro e discrimina de forma consistente"
        if abs(r) >= 0.20 and auc >= 0.65:
            return "score tem sinal claro e desempenho moderado"
        if abs(r) >= 0.10 and auc >= 0.60:
            return "score tem algum sinal, mas com discriminacao limitada"
        return "score apresenta sinal fraco ou instavel"
    if auc is not None:
        return "leitura baseada apenas em discriminacao binaria"
    return "leitura baseada apenas em correlacao ordinal"


def _metricas_principais(pares: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    if "era" in pares.columns:
        completa = pares[pares["era"] == "completa"]
        if len(completa) >= 30:
            return "Era completa", completa
    return "Total", pares


def gerar_relatorio(pares, incluir_rproc, excluir_t0=None, escopo="UF PB", ufs=None):
    excluir_t0 = set(excluir_t0 or [])
    ufs = list(ufs or [])
    L = []
    w = L.append

    label_principal, base_principal = _metricas_principais(pares)
    spearman_principal = analise_spearman(base_principal, label_principal) if len(base_principal) >= 3 else None
    auc_principal = analise_roc(base_principal, label_principal) if len(base_principal) >= 3 else None
    r_principal = spearman_principal["r"] if spearman_principal else None
    auc_valor = auc_principal["auc"] if auc_principal and isinstance(auc_principal["auc"], float) else None
    positivos_total = int((pares["rproc_t1"] > 3.0).sum()) if "rproc_t1" in pares.columns else 0
    municipios = pares["cod_ibge"].nunique() if "cod_ibge" in pares.columns else 0

    w("=" * 70)
    w("BACKTEST WALK-FORWARD - SCORE DE SOLVENCIA SOLVELICITA v7.0")
    w(f"Escopo: {escopo}")
    if ufs:
        w(f"UFs: {', '.join(ufs)}")
    w("=" * 70)

    w("RESUMO EXECUTIVO")
    w(f"  Pares validos   : {len(pares)}")
    w(f"  Municipios      : {municipios}")
    w(f"  Positivos T1    : {positivos_total} ({100 * positivos_total / len(pares):.1f}%)" if len(pares) else "  Positivos T1    : 0")
    w(f"  Base principal  : {label_principal}")
    if spearman_principal:
        w(
            f"  Spearman        : {spearman_principal['r']:+.4f} "
            f"({_forca_spearman(spearman_principal['r'])})"
        )
    if auc_principal:
        if isinstance(auc_principal["auc"], float):
            w(
                f"  AUC             : {auc_principal['auc']:.4f} "
                f"({_forca_auc(auc_principal['auc'])})"
            )
        else:
            w(f"  AUC             : {auc_principal['auc']}")
    w(f"  Leitura         : {_leitura_executiva(r_principal, auc_valor)}")
    w("")

    w("PREMISSAS")
    w(f"  RPproc          : {'ativo' if incluir_rproc else 'desativado (--sem-rproc)'}")
    w("  CAUC            : neutro (0.0) - sem serie historica")
    w("  Autonomia       : neutra (0.5) - sem serie historica no siconfi")
    if excluir_t0:
        for ano in sorted(excluir_t0):
            nota = ANOS_ATIPICOS.get(ano, "excluido via --excluir-t0")
            w(f"  T0 excluido     : {ano} ({nota})")
    w("")

    if "uf" in pares.columns and pares["uf"].nunique() > 1:
        w("RESULTADO POR UF")
        for uf, sub in pares.groupby("uf"):
            res_s = analise_spearman(sub, uf)
            res_a = analise_roc(sub, uf)
            positivos = int((sub["rproc_t1"] > 3.0).sum())
            linha = (
                f"  {uf}  n={len(sub):4d}  positivos={positivos:3d}  "
                f"spearman={res_s['r']:+.4f}"
            )
            if isinstance(res_a["auc"], float):
                linha += f"  auc={res_a['auc']:.4f}"
            else:
                linha += f"  auc={res_a['auc']}"
            w(linha)
        w("")

        w("COBERTURA POR UF")
        for _, row in _resumo_por_uf(pares).iterrows():
            w(
                f"  {row['uf']}  pares={int(row['n_pares']):4d}  "
                f"municipios={int(row['municipios']):4d}  "
                f"score_med={row['score_med']:.1f}  desfecho_med={row['rproc_t1_med']:.2f}%"
            )
        w("")

    w("METRICAS PRINCIPAIS")
    for label, sub in [
        ("Era completa", pares[pares["era"] == "completa"]),
        ("Era parcial ", pares[pares["era"] == "parcial"]),
        ("Total       ", pares),
    ]:
        if len(sub) == 0:
            continue
        if label.strip() == "Era parcial" and len(sub) < 30:
            continue
        res_s = analise_spearman(sub, label)
        res_a = analise_roc(sub, label)
        positivos = int((sub["rproc_t1"] > 3.0).sum())
        linha = (
            f"  {label}  n={len(sub):4d}  positivos={positivos:4d}  "
            f"spearman={res_s['r']:+.4f}"
        )
        if isinstance(res_a["auc"], float):
            linha += f"  auc={res_a['auc']:.4f} ({_forca_auc(res_a['auc'])})"
        else:
            linha += f"  auc={res_a['auc']}"
        w(linha)

    w("")
    w("GRADIENTE POR CLASSE")
    for label, sub in [
        ("Era completa", pares[pares["era"] == "completa"]),
        ("Era parcial ", pares[pares["era"] == "parcial"]),
    ]:
        if len(sub) == 0:
            continue
        if label.strip() == "Era parcial" and len(sub) < 30:
            continue
        w(f"  {label}:")
        for _, row in tabela_desfecho_por_classe(sub).iterrows():
            w(
                f"    {row['classe']:7s}  n={int(row['n']):4d}  "
                f"mediana={row['mediana_rproc_t1']:5.2f}%  "
                f"cronicos_t1={row['pct_cronicos_t1']:5.1f}%"
            )
        w("")

    completa = pares[pares["era"] == "completa"].copy()
    if len(completa) > 0:
        w("ERROS EXTREMOS (ERA COMPLETA)")
        w("  Falsos positivos: classificados como ALTO/CRITICO, rproc_T1 < 1%")
        fp = completa[
            completa["classe_t0"].isin(["ALTO", "CRITICO"])
            & (completa["rproc_t1"] < 1.0)
        ][["uf", "municipio", "ano_t0", "score_t0", "rproc_t1"]]
        fp = fp.sort_values(["score_t0", "rproc_t1"], ascending=[False, True]).head(8)
        for _, r in fp.iterrows():
            uf_tag = f"[{r.uf}] " if pd.notna(r.get("uf")) else ""
            w(f"    {uf_tag}{r.municipio:<26s}  score={r.score_t0:.1f}  rproc_t1={r.rproc_t1:.2f}%")
        if fp.empty:
            w("    nenhum caso encontrado")

        w("  Falsos negativos: classificados como BAIXO/MEDIO, rproc_T1 > 5%")
        fn = completa[
            completa["classe_t0"].isin(["BAIXO", "MEDIO"])
            & (completa["rproc_t1"] > 5.0)
        ][["uf", "municipio", "ano_t0", "score_t0", "rproc_t1"]]
        fn = fn.sort_values(["rproc_t1", "score_t0"], ascending=[False, False]).head(8)
        for _, r in fn.iterrows():
            uf_tag = f"[{r.uf}] " if pd.notna(r.get("uf")) else ""
            w(f"    {uf_tag}{r.municipio:<26s}  score={r.score_t0:.1f}  rproc_t1={r.rproc_t1:.2f}%")
        if fn.empty:
            w("    nenhum caso encontrado")

        w("")

    w("=" * 70)
    w("LIMITACOES DA VALIDACAO")
    w("  1. CAUC e Autonomia sem serie historica - 20% dos pesos neutralizados.")
    w("     O AUC real do score completo e provavelmente superior ao reportado.")
    w("  2. RPproc tem circularidade parcial com o desfecho.")
    w("     Rode --sem-rproc e compare os AUCs para quantificar o efeito.")
    w("  3. O backtest segue PB-first na calibracao original das premissas.")
    w("  4. 2020 pode carregar ruido estrutural por COVID.")
    w("     Use --excluir-t0 2020 para analise de sensibilidade.")
    w("=" * 70)
    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser(
        description="Backtest walk-forward - Score de Solvencia SolveLicita v7.0"
    )
    parser.add_argument("--uf", default="PB", help="UF da analise quando nao usar --geral")
    parser.add_argument("--geral", action="store_true",
                        help="Concatena todos os siconfi_indicadores_<uf>.csv disponiveis")
    parser.add_argument("--pares", choices=["completa", "parcial", "todos"],
                        default="todos")
    parser.add_argument("--sem-rproc", action="store_true",
                        help="Remove RPproc do score para isolar circularidade com o desfecho")
    parser.add_argument("--excluir-t0", nargs="+", type=int, default=[],
                        metavar="ANO",
                        help="Exclui pares cujo T0 seja um desses anos (ex: --excluir-t0 2020)")
    args = parser.parse_args()

    if args.geral:
        df, ufs, ignoradas = carregar_siconfi_geral()
        escopo = "geral"
        tag_saida = "geral"
        analysis_dir = get_analysis_dir(True)
    else:
        uf = args.uf.upper()
        df = carregar_siconfi_uf(uf)
        ufs = [uf]
        ignoradas = []
        escopo = f"UF {uf}"
        tag_saida = uf.lower()
        analysis_dir = get_analysis_dir(False, uf)

    print(
        f"[OK] {len(df)} registros | {df['cod_ibge'].nunique()} municipios | "
        f"ufs={','.join(ufs)} | anos: {sorted(df['ano'].unique())}"
    )
    if ignoradas:
        print(f"[OK] UFs ignoradas por contrato incompativel: {', '.join(ignoradas)}")
    if args.excluir_t0:
        print(f"     T0 excluidos: {args.excluir_t0}")

    pares = construir_pares(df, incluir_rproc=not args.sem_rproc,
                            excluir_t0=args.excluir_t0)

    if args.pares == "completa":
        pares = pares[pares["era"] == "completa"].copy()
    elif args.pares == "parcial":
        pares = pares[pares["era"] == "parcial"].copy()

    print(
        f"[OK] {len(pares)} pares | completa={(pares['era'] == 'completa').sum()} "
        f"| parcial={(pares['era'] == 'parcial').sum()}"
    )

    mods = ("_sem_rproc" if args.sem_rproc else "") + (
        f"_ex{'_'.join(str(a) for a in sorted(args.excluir_t0))}" if args.excluir_t0 else ""
    )
    csv_path = analysis_dir / f"backtest_pares_{tag_saida}{mods}.csv"
    txt_path = analysis_dir / f"backtest_resumo_{tag_saida}{mods}.txt"

    pares.to_csv(csv_path, index=False)
    relatorio = gerar_relatorio(
        pares,
        incluir_rproc=not args.sem_rproc,
        excluir_t0=args.excluir_t0,
        escopo=escopo,
        ufs=ufs,
    )
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(relatorio)

    print(f"[OK] CSV  -> {csv_path}")
    print(f"[OK] TXT  -> {txt_path}")
    print()
    print(relatorio)


if __name__ == "__main__":
    main()

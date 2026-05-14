"""
Coletor experimental do Ranking da Qualidade da Informacao Contabil e Fiscal
no SICONFI.

Fonte oficial:
    https://ranking-municipios.tesouro.gov.br/static/data/down_loads/municipios_bspn.zip

Este coletor e uma prova de viabilidade. Ele baixa o CSV anual publicado pelo
Tesouro, filtra uma UF e salva um arquivo local em data/tmp, sem publicar no
BigQuery e sem alterar o score.

Rodar:
    python src/collectors/experimental/siconfi_quality_ranking.py --uf PB
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.collectors.municipios import carregar_municipios
from src.config.settings import PROJECT_ROOT


SOURCE_URL = (
    "https://ranking-municipios.tesouro.gov.br"
    "/static/data/down_loads/municipios_bspn.zip"
)

RAW_COLUMNS = [
    "ID_ENTE",
    "NOME_ENTE",
    "UF",
    "VA_EXERCICIO",
    "TOTAL",
    "DIM-I",
    "DIM-II",
    "DIM-III",
    "DIM-IV",
    "PER_ACERTOS",
    "NO_ICF",
    "POS_RANKING",
]

OUTPUT_COLUMNS = [
    "uf",
    "cod_ibge",
    "municipio",
    "exercicio",
    "conceito_icf",
    "percentual_acertos",
    "posicao_ranking",
    "total_pontos",
    "dim_i",
    "dim_ii",
    "dim_iii",
    "dim_iv",
]


def _parse_decimal_br(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.strip().str.replace(",", ".", regex=False),
        errors="coerce",
    )


def _normalizar_ranking(df: pd.DataFrame) -> pd.DataFrame:
    missing = [col for col in RAW_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            "CSV do Ranking SICONFI sem colunas esperadas: "
            + ", ".join(missing)
        )

    out = df[RAW_COLUMNS].copy()
    out = out.rename(
        columns={
            "ID_ENTE": "cod_ibge",
            "NOME_ENTE": "municipio",
            "UF": "uf",
            "VA_EXERCICIO": "exercicio",
            "TOTAL": "total_pontos",
            "DIM-I": "dim_i",
            "DIM-II": "dim_ii",
            "DIM-III": "dim_iii",
            "DIM-IV": "dim_iv",
            "PER_ACERTOS": "percentual_acertos",
            "NO_ICF": "conceito_icf",
            "POS_RANKING": "posicao_ranking",
        }
    )

    out["uf"] = out["uf"].astype(str).str.upper().str.strip()
    out["cod_ibge"] = (
        out["cod_ibge"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(7)
    )
    out["municipio"] = (
        out["municipio"]
        .astype(str)
        .str.replace(r"\s+-\s+[A-Z]{2}$", "", regex=True)
        .str.strip()
    )
    out["exercicio"] = pd.to_numeric(out["exercicio"], errors="coerce").astype("Int64")
    out["conceito_icf"] = out["conceito_icf"].astype(str).str.upper().str.strip()
    out["posicao_ranking"] = pd.to_numeric(
        out["posicao_ranking"], errors="coerce"
    ).astype("Int64")

    for col in ["percentual_acertos", "total_pontos", "dim_i", "dim_ii", "dim_iii", "dim_iv"]:
        out[col] = _parse_decimal_br(out[col])

    out = (
        out.dropna(subset=["uf", "cod_ibge", "exercicio", "conceito_icf"])
        .sort_values(["uf", "cod_ibge", "exercicio"])
        .reset_index(drop=True)
    )
    return out[OUTPUT_COLUMNS]


def baixar_ranking_municipios(source_url: str = SOURCE_URL) -> pd.DataFrame:
    response = requests.get(source_url, timeout=90)
    response.raise_for_status()

    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(
                f"ZIP do Ranking SICONFI deveria conter 1 CSV; encontrou {len(csv_names)}."
            )
        with zf.open(csv_names[0]) as fh:
            raw = pd.read_csv(fh, sep=";", dtype=str, encoding="utf-8-sig")

    return _normalizar_ranking(raw)


def coletar_uf(uf: str, *, output_dir: Path | None = None) -> pd.DataFrame:
    uf = uf.upper().strip()
    ranking = baixar_ranking_municipios()
    df_uf = ranking[ranking["uf"] == uf].copy()
    if df_uf.empty:
        raise ValueError(f"Nenhum registro do Ranking SICONFI para UF={uf}.")

    municipios = carregar_municipios(uf, prefer_local=True)
    esperados = set(municipios["cod_ibge"].astype(str).str.zfill(7))
    encontrados = set(df_uf["cod_ibge"].astype(str).str.zfill(7))
    faltantes = sorted(esperados - encontrados)

    out_dir = output_dir or (
        PROJECT_ROOT / "data" / "tmp" / "siconfi_quality_ranking" / uf
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"siconfi_quality_ranking_{uf.lower()}.csv"
    df_uf.to_csv(out_path, index=False, encoding="utf-8")

    latest_year = int(df_uf["exercicio"].max())
    latest = df_uf[df_uf["exercicio"] == latest_year]

    print("\nRanking SICONFI qualidade - prova de viabilidade")
    print(f"  UF                 : {uf}")
    print(f"  Fonte              : {SOURCE_URL}")
    print(f"  Anos disponiveis   : {sorted(df_uf['exercicio'].astype(int).unique().tolist())}")
    print(f"  Municipios esperados: {len(esperados)}")
    print(f"  Municipios achados : {df_uf['cod_ibge'].nunique()}")
    print(f"  Faltantes          : {len(faltantes)}")
    if faltantes:
        print(f"  Faltantes amostra  : {', '.join(faltantes[:10])}")
    print(f"  Ano mais recente   : {latest_year}")
    print(f"  Registros no ano   : {len(latest)}")
    print("\n  Distribuicao NO_ICF no ano mais recente:")
    print(latest["conceito_icf"].value_counts(dropna=False).sort_index().to_string())
    print("\n  Percentual de acertos no ano mais recente:")
    print(latest["percentual_acertos"].describe().round(4).to_string())
    print(f"\n  CSV salvo em       : {out_path}")

    return df_uf


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Coleta experimental do Ranking SICONFI de qualidade por UF."
    )
    parser.add_argument("--uf", default="PB", help="UF a coletar. Padrao: PB.")
    args = parser.parse_args()
    coletar_uf(args.uf)


if __name__ == "__main__":
    main()

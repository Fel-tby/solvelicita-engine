"""
Coletor do Ranking da Qualidade da Informacao Contabil e Fiscal no SICONFI.

O ranking e publicado por edicao, mas os arquivos identificam o exercicio dos
dados avaliados. Exemplo: Ranking 2025 = VA_EXERCICIO 2024.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.collectors.municipios import carregar_municipios
from src.scorers.config import ICF_FATORES, ICF_FATOR_SEM_REGISTRO
from src.utils.bigquery_loader import publish_raw_replace_slice
from src.utils.paths import get_artifact_path


FINAL_SOURCE_URL = (
    "https://ranking-municipios.tesouro.gov.br"
    "/static/data/down_loads/municipios_bspn.zip"
)

PREVIO_2026_SOURCE_URL = (
    "https://cdn.tesouro.gov.br/sistemas-internos/apex/producao/sistemas/thot/"
    "arquivos/publicacoes/54595_2487593/anexos/28207_913108/"
    "Resultado%20Pr%C3%A9vio%2008-05-26%201.csv"
)

STATUS_FINAL = "FINAL"
STATUS_PREVIO = "PREVIO_OFICIAL"

DF_ESTADO_ENTE = "53"
DF_MUNICIPIO_COD_IBGE = "5300108"

RAW_FINAL_COLUMNS = [
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

BASE_OUTPUT_COLUMNS = [
    "uf",
    "cod_ibge",
    "municipio",
    "exercicio",
    "edicao_ranking",
    "status_icf",
    "conceito_icf",
    "fator_icf",
    "percentual_acertos",
    "posicao_ranking",
    "total_pontos",
    "dim_i",
    "dim_ii",
    "dim_iii",
    "dim_iv",
    "fonte_url",
]

KEY_COLS = ["uf", "cod_ibge", "exercicio"]


def _baixar_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def _parse_decimal_br(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text in {"-", "NA", "N/A"}:
        return None
    return float(text.replace(".", "").replace(",", ".") if "," in text else text)


def _normalizar_percentual(value) -> float | None:
    parsed = _parse_decimal_br(value)
    if parsed is None:
        return None
    return parsed / 100 if parsed > 1.5 else parsed


def _conceito_por_percentual(percentual: float | None) -> str:
    if percentual is None:
        return "SEM_ICF"
    if percentual >= 0.95:
        return "A"
    if percentual >= 0.85:
        return "B"
    if percentual >= 0.75:
        return "C"
    if percentual >= 0.65:
        return "D"
    return "E"


def fator_por_conceito(conceito: str | None) -> float:
    if conceito is None:
        return ICF_FATOR_SEM_REGISTRO
    return float(ICF_FATORES.get(str(conceito).upper().strip(), ICF_FATOR_SEM_REGISTRO))


def _normalizar_cod_ibge(value) -> str:
    text = str(value).strip().replace(".0", "")
    if text == DF_ESTADO_ENTE:
        return DF_MUNICIPIO_COD_IBGE
    return text.zfill(7)


def _uf_por_cod_ibge(cod_ibge: str) -> str:
    prefix = str(cod_ibge).zfill(7)[:2]
    return {
        "11": "RO",
        "12": "AC",
        "13": "AM",
        "14": "RR",
        "15": "PA",
        "16": "AP",
        "17": "TO",
        "21": "MA",
        "22": "PI",
        "23": "CE",
        "24": "RN",
        "25": "PB",
        "26": "PE",
        "27": "AL",
        "28": "SE",
        "29": "BA",
        "31": "MG",
        "32": "ES",
        "33": "RJ",
        "35": "SP",
        "41": "PR",
        "42": "SC",
        "43": "RS",
        "50": "MS",
        "51": "MT",
        "52": "GO",
        "53": "DF",
    }[prefix]


def _normalizar_conceito(value, percentual: float | None) -> str:
    text = str(value or "").upper().strip()
    for token in ("A", "B", "C", "D", "E"):
        if text.startswith(token):
            return token
    return _conceito_por_percentual(percentual)


def baixar_ranking_final(source_url: str = FINAL_SOURCE_URL) -> pd.DataFrame:
    data = _baixar_bytes(source_url)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(
                f"ZIP do Ranking SICONFI deveria conter 1 CSV; encontrou {len(csv_names)}."
            )
        with zf.open(csv_names[0]) as fh:
            try:
                raw = pd.read_csv(fh, sep=";", dtype=str, encoding="utf-8-sig")
            except UnicodeDecodeError:
                fh.seek(0)
                raw = pd.read_csv(fh, sep=";", dtype=str, encoding="latin1")

    missing = [col for col in RAW_FINAL_COLUMNS if col not in raw.columns]
    if missing:
        raise ValueError("CSV final do Ranking SICONFI sem colunas: " + ", ".join(missing))

    out = raw[RAW_FINAL_COLUMNS].copy()
    out["cod_ibge"] = out["ID_ENTE"].map(_normalizar_cod_ibge)
    out["uf"] = out["UF"].fillna("").astype(str).str.upper().str.strip()
    out.loc[out["cod_ibge"] == DF_MUNICIPIO_COD_IBGE, "uf"] = "DF"
    out["municipio"] = (
        out["NOME_ENTE"]
        .astype(str)
        .str.replace(r"\s+-\s+[A-Z]{2}$", "", regex=True)
        .str.strip()
    )
    out["exercicio"] = pd.to_numeric(out["VA_EXERCICIO"], errors="coerce").astype("Int64")
    out["edicao_ranking"] = out["exercicio"] + 1
    out["status_icf"] = STATUS_FINAL
    out["percentual_acertos"] = out["PER_ACERTOS"].map(_normalizar_percentual)
    out["conceito_icf"] = [
        _normalizar_conceito(conceito, percentual)
        for conceito, percentual in zip(out["NO_ICF"], out["percentual_acertos"])
    ]
    out["fator_icf"] = out["conceito_icf"].map(fator_por_conceito)
    out["posicao_ranking"] = pd.to_numeric(out["POS_RANKING"], errors="coerce").astype("Int64")

    for source_col, target_col in [
        ("TOTAL", "total_pontos"),
        ("DIM-I", "dim_i"),
        ("DIM-II", "dim_ii"),
        ("DIM-III", "dim_iii"),
        ("DIM-IV", "dim_iv"),
    ]:
        out[target_col] = out[source_col].map(_parse_decimal_br)

    out["fonte_url"] = source_url
    return out[BASE_OUTPUT_COLUMNS].dropna(subset=["uf", "cod_ibge", "exercicio"])


def baixar_ranking_previo_2026(source_url: str = PREVIO_2026_SOURCE_URL) -> pd.DataFrame:
    data = _baixar_bytes(source_url)
    text = data.decode("latin1")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames or "Ente" not in reader.fieldnames or "Nome_ente" not in reader.fieldnames:
        raise ValueError("CSV previo do Ranking SICONFI nao tem colunas Ente/Nome_ente.")

    verificacoes = [col for col in reader.fieldnames if col not in {"Ente", "Nome_ente"}]
    rows = []
    for row in reader:
        ente = str(row.get("Ente", "")).strip()
        if ente == DF_ESTADO_ENTE:
            cod_ibge = DF_MUNICIPIO_COD_IBGE
        elif ente.isdigit() and len(ente) == 7:
            cod_ibge = ente
        else:
            continue

        valores = [_parse_decimal_br(row.get(col)) for col in verificacoes]
        valores_validos = [valor for valor in valores if valor is not None]
        percentual = (
            round(sum(valores_validos) / len(valores_validos), 6)
            if valores_validos
            else None
        )
        conceito = _conceito_por_percentual(percentual)
        rows.append(
            {
                "uf": _uf_por_cod_ibge(cod_ibge),
                "cod_ibge": cod_ibge,
                "municipio": "Distrito Federal" if cod_ibge == DF_MUNICIPIO_COD_IBGE else row["Nome_ente"],
                "exercicio": 2025,
                "edicao_ranking": 2026,
                "status_icf": STATUS_PREVIO,
                "conceito_icf": conceito,
                "fator_icf": fator_por_conceito(conceito),
                "percentual_acertos": percentual,
                "posicao_ranking": None,
                "total_pontos": sum(valores_validos) if valores_validos else None,
                "dim_i": None,
                "dim_ii": None,
                "dim_iii": None,
                "dim_iv": None,
                "fonte_url": source_url,
            }
        )

    return pd.DataFrame(rows, columns=BASE_OUTPUT_COLUMNS)


def baixar_ranking_completo(*, incluir_previo: bool = True) -> pd.DataFrame:
    frames = [baixar_ranking_final()]
    if incluir_previo:
        frames.append(baixar_ranking_previo_2026())

    frames = [frame for frame in frames if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=BASE_OUTPUT_COLUMNS)

    out = pd.concat(frames, ignore_index=True)
    out["_status_priority"] = out["status_icf"].map({STATUS_FINAL: 0, STATUS_PREVIO: 1}).fillna(9)
    out = (
        out.sort_values(["uf", "cod_ibge", "exercicio", "_status_priority"])
        .drop_duplicates(["uf", "cod_ibge", "exercicio"], keep="first")
        .drop(columns="_status_priority")
        .reset_index(drop=True)
    )
    return out[BASE_OUTPUT_COLUMNS]


def _publicar_bq(df_uf: pd.DataFrame, uf: str) -> None:
    for exercicio, lote in sorted(df_uf.groupby("exercicio"), key=lambda item: int(item[0])):
        print(f"  [BQ] Publicando siconfi_icf {uf} exercicio={int(exercicio)}...")
        publish_raw_replace_slice(
            lote,
            table="siconfi_icf",
            uf=uf,
            key_cols=KEY_COLS,
            slice_cols=["exercicio"],
        )


def coletar_uf(
    uf: str,
    *,
    incluir_previo: bool = True,
    publicar: bool = True,
) -> pd.DataFrame:
    uf = uf.upper().strip()
    ranking = baixar_ranking_completo(incluir_previo=incluir_previo)
    df_uf = ranking[ranking["uf"] == uf].copy()
    if df_uf.empty:
        raise ValueError(f"Nenhum registro do Ranking SICONFI ICF para UF={uf}.")

    municipios = carregar_municipios(uf, prefer_local=True)
    esperados = set(municipios["cod_ibge"].astype(str).str.zfill(7))
    encontrados = set(df_uf["cod_ibge"].astype(str).str.zfill(7))
    faltantes = sorted(esperados - encontrados)

    csv_path = get_artifact_path(uf, "siconfi_icf")
    df_uf.to_csv(csv_path, index=False, encoding="utf-8")

    print("\nRanking SICONFI ICF")
    print(f"  UF               : {uf}")
    print(f"  Anos disponiveis : {sorted(df_uf['exercicio'].astype(int).unique().tolist())}")
    print(f"  Status           : {', '.join(sorted(df_uf['status_icf'].dropna().unique()))}")
    print(f"  Municipios esper.: {len(esperados)}")
    print(f"  Municipios achados: {df_uf['cod_ibge'].nunique()}")
    print(f"  Faltantes        : {len(faltantes)}")
    if faltantes:
        print(f"  Faltantes amostra: {', '.join(faltantes[:10])}")
    print(f"  CSV local        : {csv_path}")

    if publicar:
        _publicar_bq(df_uf, uf)

    return df_uf


def run(uf: str = "PB") -> None:
    coletar_uf(uf, incluir_previo=True, publicar=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta Ranking SICONFI ICF por UF.")
    parser.add_argument("--uf", default="PB")
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--no-publish", action="store_true")
    args = parser.parse_args()
    coletar_uf(
        args.uf,
        incluir_previo=not args.no_preview,
        publicar=not args.no_publish,
    )


if __name__ == "__main__":
    main()

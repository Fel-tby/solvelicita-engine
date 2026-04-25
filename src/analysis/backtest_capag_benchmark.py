"""
Benchmark CAPAG vs. rproc_pct futuro.

Replica a estrutura walk-forward do backtest de validacao, mas usando a
classificacao CAPAG oficial em T0 como score concorrente e rproc_pct em T1
como desfecho.

Uso principal:
  python src/analysis/backtest_capag_benchmark.py --nordeste

Saidas:
  data/analysis/capag_benchmark/capag_ne_backtest_auc_pares.csv
  data/analysis/capag_benchmark/capag_ne_backtest_auc_resumo.txt
"""

from __future__ import annotations

import argparse
import re
import unicodedata
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "data" / "analysis" / "capag_benchmark"
PROCESSED_DIR = ROOT / "data" / "processed"

NORDESTE = ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]

CAPAG_FILES = {
    2020: {
        "name": "capag_2021_ab2020.xlsx",
        "url": (
            "https://www.tesourotransparente.gov.br/ckan/dataset/"
            "9ff93162-409e-48b5-91d9-cf645a47fdfc/resource/"
            "10387f66-f44d-4096-811c-58e68503100a/download/"
            "capag-municipios---novembro-2021.xlsx"
        ),
    },
    2021: {
        "name": "capag_2022_ab2021.xlsx",
        "url": (
            "https://www.tesourotransparente.gov.br/ckan/dataset/"
            "9ff93162-409e-48b5-91d9-cf645a47fdfc/resource/"
            "86636c19-b38a-4b9e-8fff-30fc4208dd04/download/"
            "capag-municipios-2022.xlsx"
        ),
    },
    2022: {
        "name": "capag_2023_ab2022.xlsx",
        "url": (
            "https://www.tesourotransparente.gov.br/ckan/dataset/"
            "9ff93162-409e-48b5-91d9-cf645a47fdfc/resource/"
            "31ed778a-9115-419c-b18e-c9131a978aef/download/"
            "capag-municipios-2023.xlsx"
        ),
    },
    2023: {
        "name": "capag_2024_ab2023.xlsx",
        "url": (
            "https://www.tesourotransparente.gov.br/ckan/dataset/"
            "9ff93162-409e-48b5-91d9-cf645a47fdfc/resource/"
            "30c5fc20-634d-4558-9d45-01645b501deb/download/"
            "20241015capag-municipios.xlsx"
        ),
    },
    2024: {
        "name": "capag_2025_ab2024.xlsx",
        "url": (
            "https://www.tesourotransparente.gov.br/ckan/dataset/"
            "9ff93162-409e-48b5-91d9-cf645a47fdfc/resource/"
            "046f7fcf-a742-4787-9768-dbb10747d55d/download/"
            "capag-municipios-posicao-2025-nov-09---processamento-2025-nov-10.xlsx"
        ),
    },
}

CAPAG_RISK = {"A+": 0, "A": 1, "B+": 2, "B": 3, "C": 4}
CAPAG_RISK_WITH_D = {**CAPAG_RISK, "D": 5}
CAPAG_RISK_WITH_NO_GRADE = {**CAPAG_RISK_WITH_D, "N.D.": 5, "N.E.": 5}

XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OFFICE_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def normalize_key(value: object) -> str:
    text = "" if value is None else str(value)
    text = "".join(
        ch
        for ch in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(ch) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "", text)


def sheet_priority(name: str) -> int:
    normalized = normalize_key(name)
    if "previa" in normalized and "capag" in normalized:
        return 0
    if "capag" in normalized:
        return 1
    return 2


def column_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    index = 0
    for char in letters:
        index = index * 26 + ord(char) - 64
    return index - 1


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(t.text or "" for t in shared_item.iter(f"{XML_NS}t"))
        for shared_item in root.findall(f"{XML_NS}si")
    ]


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "s":
        value = cell.find(f"{XML_NS}v")
        if value is None or value.text is None:
            return ""
        return shared_strings[int(value.text)]
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(f"{XML_NS}t"))
    value = cell.find(f"{XML_NS}v")
    return value.text if value is not None and value.text is not None else ""


def workbook_sheets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relmap = {
        rel.attrib["Id"]: "xl/" + rel.attrib["Target"].lstrip("/")
        for rel in rels
    }
    return [
        (sheet.attrib["name"], relmap[sheet.attrib[f"{OFFICE_REL_NS}id"]])
        for sheet in workbook.find(f"{XML_NS}sheets")
    ]


def iter_sheet_rows(
    archive: zipfile.ZipFile, sheet_path: str, shared_strings: list[str]
):
    root = ET.fromstring(archive.read(sheet_path))
    for row in root.findall(f".//{XML_NS}sheetData/{XML_NS}row"):
        values: list[str] = []
        for cell in row.findall(f"{XML_NS}c"):
            index = column_index(cell.attrib.get("r", "A1"))
            while len(values) <= index:
                values.append("")
            values[index] = cell_value(cell, shared_strings)
        yield values


def find_capag_column(header_keys: list[str], year_base: int) -> int | None:
    preferred = [
        "capag",
        f"capag{year_base + 1}",
        "capagoficial",
        "classificacaocapag",
    ]
    for target in preferred:
        for index, key in enumerate(header_keys):
            if key == target:
                return index

    for index, key in enumerate(header_keys):
        if re.fullmatch(r"capag\d{4}", key or ""):
            return index

    candidates = [
        index
        for index, key in enumerate(header_keys)
        if "capag" in key and "rebaixada" not in key and "origem" not in key
    ]
    return candidates[-1] if candidates else None


def find_column(
    header_keys: list[str],
    exacts: list[str] | None = None,
    contains: list[str] | None = None,
) -> int | None:
    exacts = exacts or []
    contains = contains or []
    for candidate in exacts:
        normalized = normalize_key(candidate)
        for index, key in enumerate(header_keys):
            if key == normalized:
                return index
    for candidate in contains:
        normalized = normalize_key(candidate)
        for index, key in enumerate(header_keys):
            if normalized in key:
                return index
    return None


def find_header_and_rows(path: Path, year_base: int):
    with zipfile.ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        sheets = sorted(workbook_sheets(archive), key=lambda x: (sheet_priority(x[0]), x[0]))

        for sheet_name, sheet_path in sheets:
            rows = list(iter_sheet_rows(archive, sheet_path, shared_strings))
            for row_index, row in enumerate(rows[:40]):
                header_keys = [normalize_key(value) for value in row]
                has_code = any(
                    key
                    in {
                        "codigomunicipiocompleto",
                        "codibge",
                        "codigoibge",
                        "codmunicipio",
                    }
                    for key in header_keys
                )
                has_uf = any(key == "uf" for key in header_keys)
                has_capag = find_capag_column(header_keys, year_base) is not None
                if has_code and has_uf and has_capag:
                    return sheet_name, row, rows[row_index + 1 :]

    raise RuntimeError(f"Nao encontrei cabecalho CAPAG em {path}")


def extract_capag(path: Path, year_base: int, ufs: set[str]) -> pd.DataFrame:
    sheet_name, header, rows = find_header_and_rows(path, year_base)
    header_keys = [normalize_key(value) for value in header]

    code_index = find_column(
        header_keys,
        exacts=["Código Município Completo", "Cod.IBGE", "Cod IBGE", "cod_ibge"],
        contains=["codibge", "codigoibge", "codigomunicipio"],
    )
    municipio_index = find_column(
        header_keys,
        exacts=["Nome_Município", "Município", "Instituição"],
        contains=["nomemunicipio", "instituicao"],
    )
    uf_index = find_column(header_keys, exacts=["UF"])
    capag_index = find_capag_column(header_keys, year_base)
    nota1_index = find_column(header_keys, exacts=["Nota 1", "Nota_1"])
    nota2_index = find_column(header_keys, exacts=["Nota 2", "Nota_2"])
    nota3_index = find_column(header_keys, exacts=["Nota 3", "Nota_3"])

    if code_index is None or uf_index is None or capag_index is None:
        raise RuntimeError(f"Layout CAPAG incompativel em {path.name}: {header[:20]}")

    records = []
    for row in rows:
        if max(code_index, uf_index, capag_index) >= len(row):
            continue

        uf = str(row[uf_index]).strip().upper()
        if uf not in ufs:
            continue

        code = re.sub(r"\D", "", str(row[code_index]))
        if not code:
            continue

        capag = str(row[capag_index]).strip().upper().replace(" ", "")
        if not capag:
            continue

        records.append(
            {
                "cod_ibge": code.zfill(7),
                "municipio_capag": (
                    row[municipio_index]
                    if municipio_index is not None and municipio_index < len(row)
                    else ""
                ),
                "uf": uf,
                "ano_t0": year_base,
                "capag": capag,
                "capag_risk": CAPAG_RISK.get(capag),
                "nota1": (
                    row[nota1_index]
                    if nota1_index is not None and nota1_index < len(row)
                    else ""
                ),
                "nota2": (
                    row[nota2_index]
                    if nota2_index is not None and nota2_index < len(row)
                    else ""
                ),
                "nota3": (
                    row[nota3_index]
                    if nota3_index is not None and nota3_index < len(row)
                    else ""
                ),
                "sheet": sheet_name,
                "arquivo": path.name,
            }
        )

    return pd.DataFrame(records)


def ensure_capag_files(download_missing: bool = True) -> dict[int, Path]:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for year_base, spec in CAPAG_FILES.items():
        path = ANALYSIS_DIR / spec["name"]
        if not path.exists() or path.stat().st_size < 1000:
            if not download_missing:
                raise FileNotFoundError(f"Arquivo CAPAG ausente: {path}")
            print(f"[OK] baixando {path.name}")
            urllib.request.urlretrieve(spec["url"], path)
        paths[year_base] = path
    return paths


def load_siconfi(ufs: list[str]) -> pd.DataFrame:
    frames = []
    for uf in ufs:
        path = PROCESSED_DIR / uf / f"siconfi_indicadores_{uf.lower()}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Arquivo SICONFI ausente: {path}")
        df = pd.read_csv(path, dtype={"cod_ibge": str})
        missing = {"cod_ibge", "instituicao", "ano", "rproc_pct"} - set(df.columns)
        if missing:
            raise ValueError(f"{path} sem colunas: {sorted(missing)}")
        frames.append(df[["cod_ibge", "instituicao", "ano", "rproc_pct"]].assign(uf=uf))
    return pd.concat(frames, ignore_index=True)


def build_pairs(capag: pd.DataFrame, siconfi: pd.DataFrame) -> pd.DataFrame:
    outcomes = siconfi.rename(
        columns={
            "ano": "ano_t1",
            "instituicao": "municipio",
            "uf": "uf_siconfi",
            "rproc_pct": "rproc_t1",
        }
    )
    pairs = capag.copy()
    pairs["ano_t1"] = pairs["ano_t0"] + 1
    pairs = pairs.merge(
        outcomes[["cod_ibge", "ano_t1", "municipio", "uf_siconfi", "rproc_t1"]],
        on=["cod_ibge", "ano_t1"],
        how="inner",
    )
    pairs["evento_cronico_t1"] = pairs["rproc_t1"] > 3.0
    return pairs


def auc_for_map(pairs: pd.DataFrame, score_map: dict[str, int]) -> dict[str, object]:
    valid = pairs[pairs["rproc_t1"].notna()].copy()
    valid["risk_score"] = valid["capag"].map(score_map)
    valid = valid[valid["risk_score"].notna()].copy()
    if valid["evento_cronico_t1"].nunique() < 2:
        auc = None
    else:
        auc = roc_auc_score(
            valid["evento_cronico_t1"].astype(int),
            valid["risk_score"].astype(float),
        )
    return {
        "n": len(valid),
        "eventos": int(valid["evento_cronico_t1"].sum()),
        "pct_eventos": round(100 * valid["evento_cronico_t1"].mean(), 1)
        if len(valid)
        else 0.0,
        "auc": round(float(auc), 4) if auc is not None else None,
    }


def format_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "  nenhum registro"
    return df.to_string(index=False)


def generate_report(
    pairs: pd.DataFrame,
    ufs: list[str],
    capag: pd.DataFrame,
    excluded_t0: list[int],
) -> str:
    principal = auc_for_map(pairs, CAPAG_RISK)
    with_d = auc_for_map(pairs, CAPAG_RISK_WITH_D)
    no_grade_high = auc_for_map(pairs, CAPAG_RISK_WITH_NO_GRADE)

    valid_principal = pairs[pairs["rproc_t1"].notna() & pairs["capag"].isin(CAPAG_RISK)]
    by_uf = (
        valid_principal.groupby("uf")
        .agg(
            pares=("cod_ibge", "count"),
            eventos=("evento_cronico_t1", "sum"),
            taxa_evento=("evento_cronico_t1", "mean"),
        )
        .reset_index()
    )
    by_uf["taxa_evento"] = (100 * by_uf["taxa_evento"]).round(1)

    by_year = (
        valid_principal.groupby("ano_t0")
        .agg(
            pares=("cod_ibge", "count"),
            eventos=("evento_cronico_t1", "sum"),
            taxa_evento=("evento_cronico_t1", "mean"),
        )
        .reset_index()
    )
    by_year["taxa_evento"] = (100 * by_year["taxa_evento"]).round(1)

    order = pd.DataFrame(
        {"capag": ["A+", "A", "B+", "B", "C"], "ord": [0, 1, 2, 3, 4]}
    )
    by_grade = (
        valid_principal.groupby("capag")
        .agg(
            pares=("cod_ibge", "count"),
            eventos=("evento_cronico_t1", "sum"),
            taxa_evento=("evento_cronico_t1", "mean"),
        )
        .reset_index()
        .merge(order, on="capag", how="left")
        .sort_values("ord")
        .drop(columns=["ord"])
    )
    by_grade["taxa_evento"] = (100 * by_grade["taxa_evento"]).round(1)

    no_grade = (
        pairs[pairs["capag_risk"].isna() & pairs["rproc_t1"].notna()]
        .groupby("capag")
        .agg(pares=("cod_ibge", "count"), eventos=("evento_cronico_t1", "sum"))
        .reset_index()
        .sort_values("capag")
    )

    sheets = (
        capag.groupby(["ano_t0", "sheet"])
        .size()
        .reset_index(name="linhas")
        .sort_values(["ano_t0", "sheet"])
    )

    lines = []
    write = lines.append
    write("=" * 72)
    write("BENCHMARK CAPAG - NORDESTE")
    write("=" * 72)
    write(f"UFs: {', '.join(ufs)}")
    if excluded_t0:
        write(f"T0 excluidos: {', '.join(str(year) for year in excluded_t0)}")
    write("Desfecho: rproc_pct em T1 > 3%")
    write("Score concorrente: classificacao CAPAG em T0")
    write("Escala principal: A+=0, A=1, B+=2, B=3, C=4")
    write("")
    write("RESULTADO PRINCIPAL")
    write(f"  Pares unidos CAPAG x SICONFI : {len(pairs)}")
    write(f"  Pares validos A+..C          : {principal['n']}")
    write(f"  Eventos cronicos T1          : {principal['eventos']} ({principal['pct_eventos']}%)")
    write(f"  AUC CAPAG                    : {principal['auc']:.4f}")
    write("")
    write("SENSIBILIDADES")
    write(
        f"  Inclui D como pior que C     : n={with_d['n']} "
        f"eventos={with_d['eventos']} auc={with_d['auc']:.4f}"
    )
    write(
        f"  n.d./n.e. como alto risco    : n={no_grade_high['n']} "
        f"eventos={no_grade_high['eventos']} auc={no_grade_high['auc']:.4f}"
    )
    write("")
    write("COBERTURA POR UF")
    write(format_table(by_uf))
    write("")
    write("COBERTURA POR ANO T0")
    write(format_table(by_year))
    write("")
    write("EVENTOS POR CAPAG")
    write(format_table(by_grade))
    write("")
    write("CAPAG SEM NOTA EXCLUIDAS DA AUC PRINCIPAL")
    write(format_table(no_grade))
    write("")
    write("ABAS USADAS")
    write(format_table(sheets))
    write("=" * 72)
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark CAPAG T0 contra rproc_pct T1 > 3%."
    )
    parser.add_argument("--nordeste", action="store_true", help="Usa AL, BA, CE, MA, PB, PE, PI, RN e SE.")
    parser.add_argument("--ufs", nargs="+", help="Lista de UFs alternativa.")
    parser.add_argument(
        "--excluir-t0",
        nargs="+",
        type=int,
        default=[],
        metavar="ANO",
        help="Exclui pares cujo T0 seja um desses anos (ex: --excluir-t0 2020).",
    )
    parser.add_argument("--no-download", action="store_true", help="Nao baixa XLSX CAPAG ausentes.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.ufs:
        ufs = [uf.upper() for uf in args.ufs]
    elif args.nordeste:
        ufs = NORDESTE
    else:
        ufs = ["PB"]

    capag_paths = ensure_capag_files(download_missing=not args.no_download)
    capag_frames = []
    for year_base, path in capag_paths.items():
        extracted = extract_capag(path, year_base, set(ufs))
        print(f"[OK] CAPAG ano-base {year_base}: {len(extracted)} linhas")
        capag_frames.append(extracted)
    capag = pd.concat(capag_frames, ignore_index=True)

    siconfi = load_siconfi(ufs)
    pairs = build_pairs(capag, siconfi)
    if args.excluir_t0:
        pairs = pairs[~pairs["ano_t0"].isin(args.excluir_t0)].copy()
        capag = capag[~capag["ano_t0"].isin(args.excluir_t0)].copy()

    tag = "ne" if ufs == NORDESTE else "_".join(uf.lower() for uf in ufs)
    if args.excluir_t0:
        tag += "_ex" + "_".join(str(year) for year in sorted(args.excluir_t0))
    csv_path = ANALYSIS_DIR / f"capag_{tag}_backtest_auc_pares.csv"
    txt_path = ANALYSIS_DIR / f"capag_{tag}_backtest_auc_resumo.txt"

    pairs.to_csv(csv_path, index=False, encoding="utf-8-sig")
    report = generate_report(pairs, ufs, capag, sorted(args.excluir_t0))
    txt_path.write_text(report, encoding="utf-8")

    print(f"[OK] CSV -> {csv_path}")
    print(f"[OK] TXT -> {txt_path}")
    print()
    print(report)


if __name__ == "__main__":
    main()

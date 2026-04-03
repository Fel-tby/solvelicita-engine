"""
Generate frontend GeoJSON assets for a given UF.

This script converts a municipal boundary source file into the
`frontend/public/{uf}_geo.geojson` format expected by the Next.js app.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_PUBLIC = ROOT / "frontend" / "public"
DEFAULT_SOURCE_ROOT = ROOT / "data" / "raw" / "geo"
IBGE_BASE_URL = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais"

UF_TO_CD = {
    "AC": "12",
    "AL": "27",
    "AP": "16",
    "AM": "13",
    "BA": "29",
    "CE": "23",
    "DF": "53",
    "ES": "32",
    "GO": "52",
    "MA": "21",
    "MT": "51",
    "MS": "50",
    "MG": "31",
    "PA": "15",
    "PB": "25",
    "PR": "41",
    "PE": "26",
    "PI": "22",
    "RJ": "33",
    "RN": "24",
    "RS": "43",
    "RO": "11",
    "RR": "14",
    "SC": "42",
    "SP": "35",
    "SE": "28",
    "TO": "17",
}

MUNICIPIO_ID_CANDIDATES = [
    "CD_MUN",
    "CD_MUN_7",
    "codigo_ibge",
    "cod_ibge",
    "id",
]

MUNICIPIO_NAME_CANDIDATES = [
    "NM_MUN",
    "nome",
    "name",
    "NOME",
    "municipio",
]

UF_SIGLA_CANDIDATES = [
    "SIGLA_UF",
    "UF",
    "uf",
    "sg_uf",
]

UF_CODIGO_CANDIDATES = [
    "CD_UF",
    "codigo_uf",
    "cod_uf",
]

SOURCE_EXTENSIONS = (".shp", ".gpkg", ".geojson", ".json")


def _find_column(columns: list[str], candidates: list[str]) -> str | None:
    lookup = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    return None


def _import_geopandas():
    try:
        import geopandas as gpd  # type: ignore
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "geopandas is required to generate GeoJSON assets. "
            "Install project dependencies or run the script with the project venv."
        ) from exc
    return gpd


def _import_requests():
    try:
        import requests  # type: ignore
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "requests is required to download the IBGE source automatically. "
            "Install project dependencies or run the script with the project venv."
        ) from exc
    return requests


def _candidate_score(path: Path, uf: str) -> tuple[int, int, str]:
    stem = path.stem.lower()
    score = 0

    if stem == uf.lower():
        score += 50
    if uf.lower() in stem:
        score += 20
    if "municip" in stem:
        score += 10
    if "malha" in stem:
        score += 8
    if path.suffix.lower() == ".shp":
        score += 5

    return (-score, len(str(path)), str(path).lower())


def _resolve_default_source(uf: str) -> Path:
    source_dir = DEFAULT_SOURCE_ROOT / uf.upper()
    source_dir.mkdir(parents=True, exist_ok=True)

    candidates = [
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS
    ]

    if not candidates:
        _download_ibge_source(uf, source_dir)
        candidates = [
            path
            for path in source_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS
        ]

    if not candidates:
        raise FileNotFoundError(
            f"No supported source file found in {source_dir} after download.\n"
            "Supported extensions: .shp, .gpkg, .geojson, .json"
        )

    return sorted(candidates, key=lambda path: _candidate_score(path, uf))[0]


def _ibge_download_candidates(uf: str) -> list[tuple[int, str]]:
    current_year = datetime.now().year
    candidates: list[tuple[int, str]] = []

    for year in range(current_year, 2020, -1):
        candidates.append(
            (
                year,
                f"{IBGE_BASE_URL}/municipio_{year}/UFs/{uf}/{uf}_Municipios_{year}.zip",
            )
        )

    uf_lower = uf.lower()
    for year in range(2020, 2009, -1):
        candidates.append(
            (
                year,
                f"{IBGE_BASE_URL}/municipio_{year}/UFs/{uf}/{uf_lower}_municipios.zip",
            )
        )

    return candidates


def _download_file(url: str, target: Path) -> None:
    requests = _import_requests()
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    handle.write(chunk)


def _download_ibge_source(uf: str, target_dir: Path) -> None:
    requests = _import_requests()
    last_error: Exception | None = None

    for year, url in _ibge_download_candidates(uf):
        zip_path = target_dir / f"{uf}_Municipios_{year}.zip"
        print(f"Downloading official IBGE municipal mesh for {uf} ({year})...")

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
                temp_path = Path(temp_file.name)

            try:
                _download_file(url, temp_path)
                zip_path.write_bytes(temp_path.read_bytes())
            finally:
                temp_path.unlink(missing_ok=True)

            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(target_dir)

            print(f"Source downloaded to {zip_path}")
            return
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                last_error = exc
                continue
            last_error = exc
            break
        except Exception as exc:
            last_error = exc
            break

    raise FileNotFoundError(
        f"Could not download the municipal mesh for {uf} from IBGE. "
        f"Last error: {last_error}"
    )


def _load_source(source: Path, layer: str | None):
    gpd = _import_geopandas()
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")
    if source.is_dir():
        raise ValueError("Source must be a file, not a directory.")
    kwargs = {"layer": layer} if layer else {}
    return gpd.read_file(source, **kwargs)


def _filter_by_uf(gdf, uf: str):
    columns = list(gdf.columns)

    sigla_col = _find_column(columns, UF_SIGLA_CANDIDATES)
    if sigla_col:
        filtered = gdf[gdf[sigla_col].astype(str).str.upper() == uf].copy()
        if not filtered.empty:
            return filtered

    codigo_col = _find_column(columns, UF_CODIGO_CANDIDATES)
    uf_codigo = UF_TO_CD.get(uf)
    if codigo_col and uf_codigo:
        filtered = gdf[gdf[codigo_col].astype(str).str.zfill(2) == uf_codigo].copy()
        if not filtered.empty:
            return filtered

    id_col = _find_column(columns, MUNICIPIO_ID_CANDIDATES)
    if id_col and uf_codigo:
        filtered = gdf[gdf[id_col].astype(str).str.zfill(7).str.startswith(uf_codigo)].copy()
        if not filtered.empty:
            return filtered

    return gdf.copy()


def _normalize_columns(
    gdf,
    id_column: str | None,
    name_column: str | None,
):
    columns = list(gdf.columns)

    resolved_id = id_column or _find_column(columns, MUNICIPIO_ID_CANDIDATES)
    resolved_name = name_column or _find_column(columns, MUNICIPIO_NAME_CANDIDATES)

    if not resolved_id:
        raise ValueError(
            "Could not detect municipality id column. "
            "Use --id-column to specify it explicitly."
        )
    if not resolved_name:
        raise ValueError(
            "Could not detect municipality name column. "
            "Use --name-column to specify it explicitly."
        )

    output = gdf[[resolved_id, resolved_name, "geometry"]].copy()
    output = output.rename(columns={resolved_id: "id", resolved_name: "name"})
    output["id"] = output["id"].astype(str).str.extract(r"(\d{7})", expand=False)
    output["name"] = output["name"].astype(str).str.strip()
    output["description"] = output["name"]

    missing_ids = output["id"].isna().sum()
    if missing_ids:
        raise ValueError(f"Found {missing_ids} features without a valid 7-digit municipality id.")

    return output[["id", "name", "description", "geometry"]]


def _validate_output(gdf, uf: str) -> None:
    if gdf.empty:
        raise ValueError(f"No features found for UF {uf}.")

    duplicated = gdf["id"].duplicated()
    if duplicated.any():
        duplicates = ", ".join(gdf.loc[duplicated, "id"].tolist()[:10])
        raise ValueError(f"Duplicate municipality ids found: {duplicates}")

    invalid = ~gdf["id"].astype(str).str.fullmatch(r"\d{7}")
    if invalid.any():
        sample = ", ".join(gdf.loc[invalid, "id"].astype(str).tolist()[:10])
        raise ValueError(f"Invalid municipality ids found: {sample}")

    if gdf.geometry.is_empty.any():
        raise ValueError("Empty geometries found in source data.")


def _write_geojson(gdf, output_path: Path) -> None:
    payload = json.loads(gdf.to_json(drop_id=True, ensure_ascii=False))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def build_geojson_asset(
    uf: str,
    source: Path | None = None,
    output: Path | None = None,
    layer: str | None = None,
    id_column: str | None = None,
    name_column: str | None = None,
) -> Path:
    normalized_uf = uf.upper()
    if normalized_uf not in UF_TO_CD:
        raise ValueError(f"Unsupported UF: {uf}")

    source_path = source or _resolve_default_source(normalized_uf)

    gdf = _load_source(source_path, layer=layer)
    filtered = _filter_by_uf(gdf, normalized_uf)
    normalized = _normalize_columns(filtered, id_column=id_column, name_column=name_column)

    if normalized.crs is not None and normalized.crs.to_epsg() != 4326:
        normalized = normalized.to_crs(4326)

    _validate_output(normalized, normalized_uf)

    output_path = output or (FRONTEND_PUBLIC / f"{normalized_uf.lower()}_geo.geojson")
    _write_geojson(normalized, output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate frontend/public/{uf}_geo.geojson. "
            "If no local source is found in data/raw/geo/{UF}/, the script downloads "
            "the official municipal mesh from IBGE automatically."
        )
    )
    parser.add_argument("--uf", required=True, help="Target UF, e.g. RN")
    parser.add_argument(
        "--source",
        help=(
            "Optional path to the source file. If omitted, the script looks inside "
            "data/raw/geo/{UF}/ automatically."
        ),
    )
    parser.add_argument(
        "--output",
        help="Optional output path. Default: frontend/public/{uf}_geo.geojson",
    )
    parser.add_argument(
        "--layer",
        help="Optional layer name for sources that contain multiple layers, such as GPKG.",
    )
    parser.add_argument(
        "--id-column",
        help="Optional explicit municipality id column.",
    )
    parser.add_argument(
        "--name-column",
        help="Optional explicit municipality name column.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = build_geojson_asset(
        uf=args.uf,
        source=Path(args.source).expanduser().resolve() if args.source else None,
        output=Path(args.output).expanduser().resolve() if args.output else None,
        layer=args.layer,
        id_column=args.id_column,
        name_column=args.name_column,
    )
    print(f"GeoJSON generated: {output_path}")


if __name__ == "__main__":
    main()

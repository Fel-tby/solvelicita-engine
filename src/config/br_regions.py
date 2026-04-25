from __future__ import annotations

REGION_NORTH = "NORTE"
REGION_NORTHEAST = "NORDESTE"
REGION_CENTER_WEST = "CENTRO_OESTE"
REGION_SOUTHEAST = "SUDESTE"
REGION_SOUTH = "SUL"

REGIAO_POR_UF: dict[str, str] = {
    "AC": REGION_NORTH,
    "AL": REGION_NORTHEAST,
    "AM": REGION_NORTH,
    "AP": REGION_NORTH,
    "BA": REGION_NORTHEAST,
    "CE": REGION_NORTHEAST,
    "DF": REGION_CENTER_WEST,
    "ES": REGION_SOUTHEAST,
    "GO": REGION_CENTER_WEST,
    "MA": REGION_NORTHEAST,
    "MG": REGION_SOUTHEAST,
    "MS": REGION_CENTER_WEST,
    "MT": REGION_CENTER_WEST,
    "PA": REGION_NORTH,
    "PB": REGION_NORTHEAST,
    "PE": REGION_NORTHEAST,
    "PI": REGION_NORTHEAST,
    "PR": REGION_SOUTH,
    "RJ": REGION_SOUTHEAST,
    "RN": REGION_NORTHEAST,
    "RO": REGION_NORTH,
    "RR": REGION_NORTH,
    "RS": REGION_SOUTH,
    "SC": REGION_SOUTH,
    "SE": REGION_NORTHEAST,
    "SP": REGION_SOUTHEAST,
    "TO": REGION_NORTH,
}


def get_region_for_uf(uf: str) -> str:
    normalized = uf.strip().upper()
    try:
        return REGIAO_POR_UF[normalized]
    except KeyError as exc:
        raise ValueError(f"UF sem regiao configurada: {uf!r}") from exc

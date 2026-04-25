import pytest

from src.config.br_regions import REGIAO_POR_UF, get_region_for_uf


def test_regiao_por_uf_cobre_27_ufs():
    assert len(REGIAO_POR_UF) == 27


def test_get_region_for_uf_normaliza_case():
    assert get_region_for_uf("pb") == "NORDESTE"
    assert get_region_for_uf("Sp") == "SUDESTE"


def test_get_region_for_uf_rejeita_uf_invalida():
    with pytest.raises(ValueError, match="UF sem regiao configurada"):
        get_region_for_uf("XX")

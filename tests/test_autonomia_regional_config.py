from src.config.br_regions import get_region_for_uf
from src.scorers.config import (
    get_limiar_autonomia_crit,
    get_sigmoid_autonomia,
)


def test_get_region_for_uf_covers_all_regions():
    assert get_region_for_uf("PB") == "NORDESTE"
    assert get_region_for_uf("PA") == "NORTE"
    assert get_region_for_uf("GO") == "CENTRO_OESTE"
    assert get_region_for_uf("SP") == "SUDESTE"
    assert get_region_for_uf("RS") == "SUL"


def test_get_limiar_autonomia_crit_varia_por_regiao():
    assert get_limiar_autonomia_crit("PB") == 0.0500
    assert get_limiar_autonomia_crit("PA") == 0.0530
    assert get_limiar_autonomia_crit("GO") == 0.0750
    assert get_limiar_autonomia_crit("SP") == 0.0660
    assert get_limiar_autonomia_crit("RS") == 0.0780


def test_get_sigmoid_autonomia_usa_template_regional():
    assert get_sigmoid_autonomia("PB", "micro") == (0.0296, 98.6)
    assert get_sigmoid_autonomia("PA", "micro") == (0.0314, 98.6)
    assert get_sigmoid_autonomia("GO", "micro") == (0.0444, 98.6)
    assert get_sigmoid_autonomia("SP", "micro") == (0.0390, 98.6)
    assert get_sigmoid_autonomia("RS", "micro") == (0.0463, 98.6)

import io
import zipfile
from pathlib import Path

import pandas as pd

from src.collectors import siconfi_icf


def _zip_final_csv() -> bytes:
    csv = (
        "ID_ENTE;NOME_ENTE;UF;VA_EXERCICIO;TOTAL;DIM-I;DIM-II;DIM-III;DIM-IV;PER_ACERTOS;NO_ICF;POS_RANKING\n"
        "2500106;AGUA BRANCA - PB;PB;2024;95,0;20;20;20;35;95,0;A;1\n"
        "53;DISTRITO FEDERAL;DF;2024;85,0;20;20;20;25;85,0;B;2\n"
    ).encode("utf-8")
    buff = io.BytesIO()
    with zipfile.ZipFile(buff, "w") as zf:
        zf.writestr("municipios.csv", csv)
    return buff.getvalue()


def test_baixar_ranking_final_normaliza_exercicio_e_df(monkeypatch):
    monkeypatch.setattr(siconfi_icf, "_baixar_bytes", lambda _url: _zip_final_csv())

    df = siconfi_icf.baixar_ranking_final("https://teste/final.zip")

    pb = df[df["cod_ibge"] == "2500106"].iloc[0]
    assert pb["exercicio"] == 2024
    assert pb["edicao_ranking"] == 2025
    assert pb["conceito_icf"] == "A"
    assert pb["fator_icf"] == 1.0
    assert "5300108" in set(df["cod_ibge"])


def test_coletar_uf_salva_csv_e_publica_replace_slice(monkeypatch, tmp_path):
    ranking = pd.DataFrame(
        [
            {
                "uf": "PB",
                "cod_ibge": "2500106",
                "municipio": "Agua Branca",
                "exercicio": 2024,
                "edicao_ranking": 2025,
                "status_icf": "FINAL",
                "conceito_icf": "B",
                "fator_icf": 0.95,
                "percentual_acertos": 0.9,
                "posicao_ranking": 1,
                "total_pontos": 90.0,
                "dim_i": None,
                "dim_ii": None,
                "dim_iii": None,
                "dim_iv": None,
                "fonte_url": "https://teste",
            }
        ]
    )
    chamadas = []

    monkeypatch.setattr(siconfi_icf, "baixar_ranking_completo", lambda incluir_previo=True: ranking)
    monkeypatch.setattr(
        siconfi_icf,
        "carregar_municipios",
        lambda uf, prefer_local=True: pd.DataFrame([{"cod_ibge": "2500106"}]),
    )
    monkeypatch.setattr(
        siconfi_icf,
        "get_artifact_path",
        lambda uf, artifact_key: Path(tmp_path) / f"{artifact_key}_{uf.lower()}.csv",
    )
    monkeypatch.setattr(
        siconfi_icf,
        "publish_raw_replace_slice",
        lambda df, **kwargs: chamadas.append((df.copy(), kwargs)),
    )

    out = siconfi_icf.coletar_uf("PB")

    assert len(out) == 1
    assert (tmp_path / "siconfi_icf_pb.csv").exists()
    assert chamadas[0][1]["table"] == "siconfi_icf"
    assert chamadas[0][1]["key_cols"] == siconfi_icf.KEY_COLS
    assert chamadas[0][1]["slice_cols"] == ["exercicio"]

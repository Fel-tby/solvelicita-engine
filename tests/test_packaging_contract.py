import importlib
from pathlib import Path
import tomllib


def test_pyproject_declara_pacote_e_entrypoint_do_pipeline():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "solvelicita"
    assert pyproject["project"]["scripts"]["solvelicita-pipeline"] == "pipeline:main"
    assert pyproject["tool"]["setuptools"]["py-modules"] == ["pipeline"]
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == ["src", "src.*"]


def test_imports_centrais_funcionam_com_caminhos_de_pacote():
    modulos = [
        "pipeline",
        "src.config.settings",
        "src.jobs.pipeline_jobs",
        "src.collectors.municipios",
        "src.engine.solvency",
        "src.processors.dca_postprocessor",
        "src.scorers.lliq_scorer",
        "src.utils.paths",
        "src.utils.supabase_sync",
    ]

    for nome in modulos:
        modulo = importlib.import_module(nome)
        assert modulo is not None

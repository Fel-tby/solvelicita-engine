import sys
import types

fake_supabase = types.ModuleType("supabase")
fake_supabase.Client = object
fake_supabase.create_client = lambda *_args, **_kwargs: object()
sys.modules.setdefault("supabase", fake_supabase)

from src.utils.supabase_sync import _sanitizar


def test_sanitizar_converte_rproc_historico_json_para_payload_jsonb():
    registro = _sanitizar(
        {
            "cod_ibge": "2507507",
            "rproc_historico_json": (
                '[{"ano":2021,"rproc_pct":0.04,"rrestos_processados":1029086.39,'
                '"receita_realizada":2623327120.85,"cronico":false}]'
            ),
        }
    )

    assert registro["rproc_historico_json"] == [
        {
            "ano": 2021,
            "rproc_pct": 0.04,
            "rrestos_processados": 1029086.39,
            "receita_realizada": 2623327120.85,
            "cronico": False,
        }
    ]


def test_sanitizar_rproc_historico_vazio_como_array():
    registro = _sanitizar({"rproc_historico_json": ""})

    assert registro["rproc_historico_json"] == []

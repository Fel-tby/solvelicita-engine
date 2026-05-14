"""
tests/test_scorers.py
Testa cada scorer com dados reais dos fixtures.

Municípios presentes nos fixtures e por que foram escolhidos:
    2500304 Alagoa Grande -> entrega todos os anos presentes na janela, rproc crônico (2021-22),
                             eorcam anômalo (152% em 2022), CAUC REGULAR
    2500502 Alagoinha     -> lliq alto (0.60 em 2023), eorcam abaixo de 70% (2020),
                             rproc crônico só em 2022 (4.86%)
    2500205 Aguiar        -> eorcam muito alto (127% em 2024), CAUC com pendência grave
    2500106 Água Branca   -> nunca entregou RREO — testa ausência total de dados

Rodar:
    pytest tests/test_scorers.py -v
"""

import sys
from pathlib import Path
from io import StringIO
from datetime import date
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from scorers.lliq_scorer     import pontuar_lliq
from scorers.autonomia_scorer import pontuar_autonomia
from scorers.eorcam_scorer   import pontuar_eorcam, calcular as calcular_eorcam
from scorers.cauc_scorer     import pontuar_ccauc,  calcular as calcular_cauc
from scorers.qsiconfi_scorer import calcular as calcular_qsiconfi
from scorers.rproc_scorer    import pontuar_rproc_cronico, calcular as calcular_rproc
from scorers.config          import PESOS

SICONFI_SAMPLE_CSV = """cod_ibge,instituicao,ano,populacao,receita_prevista,receita_realizada,despesa_liquidada,rrestos_nao_processados,rrestos_processados,dcl_apos_rp_total,dcl_apos_rp_rpps,dcl_pre_rp_total,dcl_pre_rp_rpps,periodicidade_rgf,periodo_rgf,entregou_rreo,eorcam,rrestos_nproc_pct,rproc_pct,deficit_pct,lliq,lliq_bruta,lliq_parcial
2500205,Aguiar,2020,5026,31228823.06,22154403.54,24663269.82,50881.25,37361.38,,,,,Q,3,True,70.94,0.23,0.17,11.32,,,False
2500205,Aguiar,2021,5026,27170172.0,21985892.18,22006809.82,31620.65,31811.38,,,,,Q,3,True,80.92,0.14,0.14,0.1,,,False
2500205,Aguiar,2022,5026,39194503.14,29941928.76,27016311.88,391164.5,75359.94,,,,,Q,3,True,76.39,1.31,0.25,-9.77,,,False
2500205,Aguiar,2023,5026,44724868.67,33235145.7,29774567.73,594388.08,,5407772.21,,5466160.8,,Q,3,True,74.31,1.79,,-10.41,0.162712,5407772.21,False
2500205,Aguiar,2024,5026,38120821.0,48479451.51,49384324.95,594388.08,,4112344.08,,4175182.27,,Q,3,True,127.17,1.23,,1.87,0.084827,4112344.08,False
2500205,Aguiar,2025,5026,49831389.0,56853298.56,53342475.24,,,7934302.96,,8272496.36,,Q,3,True,114.09,,,-6.18,0.139557,7934302.96,False
2500304,Alagoa Grande,2020,26655,55710132.5,62570485.56,63225260.48,29895.33,2554758.34,,,,,Q,3,True,112.31,0.05,4.08,1.05,,,False
2500304,Alagoa Grande,2021,26655,57381436.35,70466566.45,66158320.86,30085.33,2740314.77,,,,,Q,3,True,122.8,0.04,3.89,-6.11,,,False
2500304,Alagoa Grande,2022,26655,60250508.16,92007567.87,76925696.88,32199.63,2879015.2,,,,,Q,3,True,152.71,0.03,3.13,-16.39,,,False
2500304,Alagoa Grande,2023,26655,98707630.0,97772595.43,92539710.44,1462200.15,2917029.47,23398176.92,,24381143.91,,Q,3,True,99.05,1.5,2.98,-5.35,0.239312,23398176.92,False
2500304,Alagoa Grande,2024,26655,104423000.0,119311499.15,137149400.28,2348.3,1880323.09,8007645.59,,8010515.59,,Q,3,True,114.26,0.0,1.58,14.95,0.067115,8007645.59,False
2500304,Alagoa Grande,2025,26655,132247698.64,139896516.24,127856748.86,2870.0,53572.17,26510203.86,,26639511.51,,Q,3,True,105.78,0.0,0.04,-8.61,0.189499,26510203.86,False
2500502,Alagoinha,2020,14140,59229509.52,41021632.09,38834200.33,36681.18,105378.95,,,,,Q,3,True,69.26,0.09,0.26,-5.33,,,False
2500502,Alagoinha,2021,14140,57313255.11,45461651.43,47644113.35,453218.18,171762.1,,,,,Q,3,True,79.32,1.0,0.38,4.8,,,False
2500502,Alagoinha,2022,14140,63136104.17,51082030.59,44528676.79,522800.53,2480287.5,,,,,Q,3,True,80.91,1.02,4.86,-12.83,,,False
2500502,Alagoinha,2023,14140,79603969.33,56209570.2,57832931.26,317684.87,1570531.61,33760334.14,,33816554.34,,Q,3,True,70.61,0.57,2.79,2.89,0.600615,33760334.14,False
2500502,Alagoinha,2024,14140,102118055.65,82145201.16,85164560.24,133107.59,2367628.74,26190867.17,,26209047.27,,Q,3,True,80.44,0.16,2.88,3.68,0.318836,26190867.17,False
2500502,Alagoinha,2025,14140,91299956.0,84669721.33,85241931.39,313661.85,911040.34,20051419.31,,20125610.51,,Q,3,True,92.74,0.37,1.08,0.68,0.236819,20051419.31,False
2500106,Água Branca,2020,12000,,,,,,,,,,,,False,,,,,,,False
2500106,Água Branca,2021,12000,,,,,,,,,,,,False,,,,,,,False
2500106,Água Branca,2022,12000,,,,,,,,,,,,False,,,,,,,False
2500106,Água Branca,2023,12000,,,,,,,,,,,,False,,,,,,,False
2500106,Água Branca,2024,12000,,,,,,,,,,,,False,,,,,,,False
2500106,Água Branca,2025,12000,,,,,,,,,,,,False,,,,,,,False
"""

CAUC_SAMPLE_CSV = """cod_ibge,municipio,bloqueado,qtd_pendencias,pendencias,data_pesquisa,data_coleta,fonte
2500106,Água Branca,True,10,Regularidade Fiscal (RFB) | SIOPS (Saúde) | SIOPE (Educação) | SIOPE Complementar | SICONV/TRANSFEREGOV Prestação de Contas | CADIN | SICONFI RREO | SICONFI PCASP | SICONFI DCASP | SICONFI MCASP,06/03/2026,2026-03-08,CKAN-TesouroTransparente
2500205,Aguiar,True,9,Regularidade Fiscal (RFB) | Regularidade Trabalhista (TST) | SIOPE Complementar | SICONV/TRANSFEREGOV Prestação de Contas | CADIN | SICONFI RREO | SICONFI PCASP | SICONFI DCASP | SICONFI MCASP,06/03/2026,2026-03-08,CKAN-TesouroTransparente
2500304,Alagoa Grande,False,0,REGULAR,06/03/2026,2026-03-08,CKAN-TesouroTransparente
2500502,Alagoinha,True,8,Regularidade Trabalhista (TST) | SIOPE Complementar | CADIN | SISTN (Garantias) | SICONFI RREO | SICONFI PCASP | SICONFI DCASP | SICONFI MCASP,06/03/2026,2026-03-08,CKAN-TesouroTransparente
"""

MUNICIPIOS_SAMPLE_CSV = """cod_ibge,ente,populacao,cnpj
2500106,Água Branca,12000,08098206000116
2500205,Aguiar,5026,08098207000172
2500304,Alagoa Grande,27000,08098208000128
2500502,Alagoinha,8000,08098210000110
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def carregar_siconfi() -> pd.DataFrame:
    df = pd.read_csv(StringIO(SICONFI_SAMPLE_CSV), dtype={"cod_ibge": str})
    df["entregou_rreo"] = df["entregou_rreo"].astype(str).str.lower() == "true"
    df["lliq_parcial"]  = df["lliq_parcial"].astype(str).str.lower() == "true"
    return df

def carregar_cauc() -> pd.DataFrame:
    return pd.read_csv(StringIO(CAUC_SAMPLE_CSV), dtype={"cod_ibge": str})

def carregar_municipios() -> pd.DataFrame:
    return pd.read_csv(StringIO(MUNICIPIOS_SAMPLE_CSV), dtype={"cod_ibge": str})


# ══════════════════════════════════════════════════════════════════════════════
# LLIQ — Liquidez Líquida
# ══════════════════════════════════════════════════════════════════════════════

class TestLliq:

    # ── Regras da curva v7.0 ──────────────────────────────────────────────────
    # >= 0.35           -> 1.00
    # 0.10 – 0.35       -> linear 0.60 -> 1.00
    # 0.00 – 0.10       -> linear 0.35 -> 0.60
    # -0.50 – 0.00      -> quadrático  0 -> 0.35

    def test_lliq_acima_035_retorna_maximo(self):
        """Lliq >= 0.35 -> score 1.0 (teto v7.0)."""
        assert pontuar_lliq(0.35) == 1.0
        assert pontuar_lliq(0.50) == 1.0

    def test_lliq_zero_retorna_ponto_base(self):
        """Lliq = 0.0 -> score 0.35 (ponto de inflexão da curva v7.0)."""
        assert pontuar_lliq(0.0) == 0.35

    def test_lliq_negativo_moderado_entre_0_e_035(self):
        """-0.50 < Lliq < 0 -> curva quadrática, resultado entre 0 e 0.35."""
        resultado = pontuar_lliq(-0.25)
        assert 0.0 < resultado < 0.35

    def test_lliq_extremo_negativo_capado_em_zero(self):
        """Lliq < -0.50 é capado antes do cálculo — nunca retorna negativo."""
        assert pontuar_lliq(-0.99) == 0.0
        assert pontuar_lliq(-10.0) == 0.0

    def test_lliq_ausente_retorna_none(self):
        """Dado ausente não deve produzir score."""
        assert pontuar_lliq(None) is None
        assert pontuar_lliq(float("nan")) is None

    # ── Casos reais dos fixtures ──────────────────────────────────────────────

    def test_alagoinha_2023_lliq_alto(self):
        """Alagoinha 2023: lliq=0.60 -> zona máxima (>= 0.35 -> 1.0)."""
        assert pontuar_lliq(0.600615) == 1.0

    def test_alagoa_grande_2024_lliq_baixo(self):
        """Alagoa Grande 2024: lliq=0.067 -> zona 0.00-0.10, entre 0.35 e 0.60."""
        resultado = pontuar_lliq(0.067115)
        assert 0.35 < resultado < 0.60

    def test_aguiar_2023_lliq_razoavel(self):
        """Aguiar 2023: lliq=0.163 -> zona 0.10-0.35, entre 0.65 e 0.75."""
        resultado = pontuar_lliq(0.162712)
        assert 0.65 < resultado < 0.75

    def test_contrib_nunca_excede_peso(self):
        """contrib_lliq nunca ultrapassa o peso configurado."""
        from scorers.lliq_scorer import calcular
        result = calcular(carregar_siconfi(), carregar_municipios())
        assert (result["contrib_lliq"] <= PESOS["lliq"]).all()
        assert (result["contrib_lliq"] >= 0).all()


# ══════════════════════════════════════════════════════════════════════════════
# EORCAM — Execução Orçamentária
# ══════════════════════════════════════════════════════════════════════════════

class TestEorcam:

    def test_zona_saudavel_retorna_maximo(self):
        """90% <= execução <= 105% -> score 1.0 (zona ótima)."""
        assert pontuar_eorcam(90.0)  == 1.0
        assert pontuar_eorcam(100.0) == 1.0
        assert pontuar_eorcam(105.0) == 1.0

    def test_excesso_anomalo_teto_05(self):
        """execução > 120% -> teto 0.5 (arrecadação não sustentável)."""
        assert pontuar_eorcam(121.0) == 0.5
        assert pontuar_eorcam(200.0) == 0.5

    def test_excesso_moderado_decai_linearmente(self):
        """105% < execução <= 120% -> decaimento linear entre 0.5 e 1.0."""
        resultado = pontuar_eorcam(112.5)
        assert 0.5 < resultado < 1.0

    def test_zona_atencao_proporcional(self):
        """70% <= execução < 90% -> proporcional entre 0 e 1.0."""
        resultado = pontuar_eorcam(80.0)
        assert 0.0 < resultado < 1.0

    def test_colapso_arrecadacao_retorna_zero(self):
        """execução < 70% -> 0.0 (colapso de arrecadação)."""
        assert pontuar_eorcam(69.9) == 0.0
        assert pontuar_eorcam(0.0)  == 0.0

    def test_ausente_retorna_none(self):
        assert pontuar_eorcam(None) is None

    def test_alagoa_grande_2022_anomalo(self):
        """Alagoa Grande 2022: eorcam=152.71 -> teto 0.5."""
        assert pontuar_eorcam(152.71) == 0.5

    def test_alagoinha_2020_colapso(self):
        """Alagoinha 2020: eorcam=69.26 -> abaixo de 70%, retorna 0.0."""
        assert pontuar_eorcam(69.26) == 0.0

    def test_aguiar_2024_anomalo(self):
        """Aguiar 2024: eorcam=127.17 -> teto 0.5."""
        assert pontuar_eorcam(127.17) == 0.5

    def test_agua_branca_sem_rreo_nao_aparece(self):
        """Água Branca nunca entregou RREO — não deve aparecer no resultado."""
        result = calcular_eorcam(carregar_siconfi())
        assert "2500106" not in result["cod_ibge"].values

    def test_contrib_dentro_do_peso(self):
        """contrib_eorcam em [0, PESOS["eorcam"]] para todos os municípios."""
        result = calcular_eorcam(carregar_siconfi())
        assert (result["contrib_eorcam"] >= 0).all()
        assert (result["contrib_eorcam"] <= PESOS["eorcam"]).all()


# ══════════════════════════════════════════════════════════════════════════════
# CAUC — Risco de Bloqueio Federal
# ══════════════════════════════════════════════════════════════════════════════

def test_eorcam_ignora_ano_corrente_por_ser_exercicio_aberto():
    """EORCAM nao usa o ano corrente porque o RREO ainda e parcial."""
    ano_corrente = date.today().year
    df = pd.DataFrame(
        [
            {
                "cod_ibge": "9999999",
                "ano": ano_corrente - 1,
                "entregou_rreo": True,
                "eorcam": 100.0,
            },
            {
                "cod_ibge": "9999999",
                "ano": ano_corrente,
                "entregou_rreo": True,
                "eorcam": 15.0,
            },
        ]
    )

    result = calcular_eorcam(df)

    assert result.loc[0, "eorcam_raw"] == pytest.approx(100.0)
    assert result.loc[0, "contrib_eorcam"] == PESOS["eorcam"]


class TestCauc:

    def test_regular_sem_penalidade(self):
        """REGULAR -> ccauc = 0.0 -> contribuição máxima."""
        assert pontuar_ccauc("REGULAR") == 0.0

    def test_pendencia_grave_zera(self):
        """Pendência grave isolada -> ccauc = 1.0 -> contrib = 0."""
        assert pontuar_ccauc("Regularidade Fiscal (RFB)") == 1.0
        assert pontuar_ccauc("Adimplência TCU")           == 1.0
        assert pontuar_ccauc("CADIN")                      == 1.0

    def test_grave_misturada_ainda_zera(self):
        """Uma grave entre moderadas -> ainda zera (gatilho punitivo)."""
        assert pontuar_ccauc("Regularidade Fiscal (RFB) | Regularidade FGTS") == 1.0

    def test_so_moderadas_penalidade_proporcional(self):
        """Só moderadas -> ccauc proporcional, teto 0.5."""
        resultado = pontuar_ccauc("Regularidade FGTS | Regularidade Trabalhista (TST)")
        assert 0.0 < resultado <= 0.5

    def test_ausente_pior_caso(self):
        """Dado ausente -> ccauc = 1.0 (município não rastreável = pior caso)."""
        assert pontuar_ccauc(None)          == 1.0
        assert pontuar_ccauc(float("nan")) == 1.0

    def test_agua_branca_contrib_zero(self):
        """Água Branca tem RFB + CADIN (graves) -> contrib = 0."""
        result = calcular_cauc(carregar_cauc())
        mun = result[result["cod_ibge"] == "2500106"].iloc[0]
        assert mun["contrib_ccauc"] == 0.0

    def test_aguiar_contrib_zero(self):
        """Aguiar também tem RFB -> contrib = 0."""
        result = calcular_cauc(carregar_cauc())
        mun = result[result["cod_ibge"] == "2500205"].iloc[0]
        assert mun["contrib_ccauc"] == 0.0

    def test_alagoa_grande_contrib_maxima(self):
        """Alagoa Grande está REGULAR -> contrib_ccauc = PESOS["ccauc"]."""
        result = calcular_cauc(carregar_cauc())
        mun = result[result["cod_ibge"] == "2500304"].iloc[0]
        assert mun["contrib_ccauc"] == PESOS["ccauc"]

    def test_alagoinha_contrib_zero(self):
        """Alagoinha tem CADIN nas pendências — CADIN é grave -> contrib = 0."""
        result = calcular_cauc(carregar_cauc())
        mun = result[result["cod_ibge"] == "2500502"].iloc[0]
        assert mun["contrib_ccauc"] == 0.0

    def test_contrib_sempre_dentro_do_peso(self):
        """contrib_ccauc em [0, PESOS["ccauc"]] para todos."""
        result = calcular_cauc(carregar_cauc())
        assert (result["contrib_ccauc"] >= 0).all()
        assert (result["contrib_ccauc"] <= PESOS["ccauc"]).all()


# ══════════════════════════════════════════════════════════════════════════════
# QSICONFI — Qualidade de Transparência
# ══════════════════════════════════════════════════════════════════════════════

class TestQsiconfi:

    def test_entregou_todos_os_anos(self):
        """Alagoa Grande entregou 5/6 anos na janela 2021-2026 do fixture."""
        result = calcular_qsiconfi(carregar_siconfi())
        mun = result[result["cod_ibge"] == "2500304"].iloc[0]
        assert mun["anos_entregues"]   == 5
        assert mun["qsiconfi"]         == pytest.approx(5 / 6)
        assert mun["contrib_qsiconfi"] == pytest.approx(12.5)

    def test_sem_rreo_aparece_com_zero_anos(self):
        """Água Branca nunca entregou RREO -> anos_entregues=0, contrib=0.
        A exclusão acontece no classifier (anos_entregues == 0 -> Sem Dados)."""
        result = calcular_qsiconfi(carregar_siconfi())
        mun = result[result["cod_ibge"] == "2500106"].iloc[0]
        assert mun["anos_entregues"]   == 0
        assert mun["contrib_qsiconfi"] == 0.0

    def test_contrib_dentro_do_peso(self):
        """contrib_qsiconfi em [0, 15]."""
        result = calcular_qsiconfi(carregar_siconfi())
        assert (result["contrib_qsiconfi"] >= 0).all()
        assert (result["contrib_qsiconfi"] <= PESOS["qsiconfi"]).all()


class TestAutonomiaRegional:

    def test_mesma_autonomia_recebe_nota_mais_alta_no_nordeste_que_no_sul(self):
        resultado_ne = pontuar_autonomia(0.08, 8_000, "PB")
        resultado_sul = pontuar_autonomia(0.08, 8_000, "RS")

        assert resultado_ne is not None
        assert resultado_sul is not None
        assert resultado_ne > resultado_sul

    def test_mesma_autonomia_recebe_nota_mais_alta_no_nordeste_que_no_sudeste(self):
        resultado_ne = pontuar_autonomia(0.08, 30_000, "PB")
        resultado_se = pontuar_autonomia(0.08, 30_000, "SP")

        assert resultado_ne is not None
        assert resultado_se is not None
        assert resultado_ne > resultado_se


# ══════════════════════════════════════════════════════════════════════════════
# RPROC — Cronicidade de Restos a Pagar
# ══════════════════════════════════════════════════════════════════════════════

class TestRproc:

    def test_zero_anos_cronicos(self):
        assert pontuar_rproc_cronico(0) == 1.00

    def test_1_ano_cronico(self):
        assert pontuar_rproc_cronico(1) == 0.75

    def test_2_anos_cronicos(self):
        assert pontuar_rproc_cronico(2) == 0.50

    def test_3_anos_cronicos(self):
        assert pontuar_rproc_cronico(3) == 0.30

    def test_4_anos_cronicos(self):
        assert pontuar_rproc_cronico(4) == 0.10

    def test_5_ou_mais_retorna_zero(self):
        """5+ anos crônicos -> 0.0 (também ativa cap no classifier)."""
        assert pontuar_rproc_cronico(5) == 0.00
        assert pontuar_rproc_cronico(6) == 0.00

    def test_alagoa_grande_2_anos_cronicos(self):
        """Alagoa Grande: na janela 2021-2026, rproc_pct > 3% em 2021 e 2022."""
        result = calcular_rproc(carregar_siconfi())
        mun = result[result["cod_ibge"] == "2500304"].iloc[0]
        assert mun["n_anos_cronicos"] == 2

    def test_alagoinha_1_ano_cronico(self):
        """Alagoinha: só 2022 está acima de 3% (4.86) -> n_anos_cronicos = 1."""
        result = calcular_rproc(carregar_siconfi())
        mun = result[result["cod_ibge"] == "2500502"].iloc[0]
        assert mun["n_anos_cronicos"] == 1

    def test_contrib_dentro_do_peso(self):
        """contrib_rproc em [0, PESOS["rproc"]]."""
        result = calcular_rproc(carregar_siconfi())
        assert (result["contrib_rproc"] >= 0).all()
        assert (result["contrib_rproc"] <= PESOS["rproc"]).all()

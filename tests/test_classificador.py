import json
import os
from types import SimpleNamespace

import pandas as pd
import pytest

from insp import Classificador, Memoria, avaliar
from insp.texto import extrair

AQUI = os.path.dirname(__file__)


@pytest.fixture(scope="module")
def clf():
    return Classificador()


@pytest.mark.parametrize("texto,classe,regra", [
    ("VALVULA, GAVETA; ACO CARBONO; DIAMETRO NOMINAL 12 POL; CLASSE 150", "Z02", "125.1"),
    ("VALVULA, ESFERA; ACO INOXIDAVEL AISI 316; DIAMETRO 3 POL; ROSCA NPT", "Z03", "125.2"),
    ("VALVULA, ESFERA; LATAO; DIAMETRO 1/2 POL; PARA AGUA", "Z09", "125.4"),
    ("VALVULA, SOLENOIDE; 2 VIAS; BOBINA 24 VCC", "Z09", "126"),
    ("ROLAMENTO, RIGIDO DE ESFERAS; DESIGNACAO 6205 2RS C3", "Z03", "110"),
    ("ANEL, VEDACAO O-RING; BORRACHA NITRILICA NBR; DIAMETRO INTERNO 50 mm", "Z09", "3.4"),
    ("RELE, PROTECAO; DIFERENCIAL ANSI 87; TENSAO AUXILIAR 125 VCC", "Z03", "107.1"),
    ("CABO, ACO; ALMA DE ACO; DIAMETRO 12,7 mm; CARGA DE RUPTURA 12 t", "Z04", "127"),
    ("PARAFUSO, SEXTAVADO; ACO CARBONO; M12 X 50 mm; ZINCADO", "Z09", "93.2"),
    ("PARA-RAIOS, OXIDO DE ZINCO; TENSAO NOMINAL 138 KV", "Z02", "94.1"),
    ("PARA-RAIOS, DISTRIBUICAO; TENSAO NOMINAL 15 KV", "Z04", "94.2"),
    ("TRANSFORMADOR, CORRENTE; RELACAO 600-5 A; TENSAO 15 KV", "Z02", "123.1"),
    ("MOLA, HELICOIDAL COMPRESSAO; ACO MOLA; DIAMETRO DO ARAME 3 mm", "Z03", "87.1"),
    ("TINTA, EPOXI; ESQUEMA DE PINTURA SMMA.DT; COR CINZA", "Z04", "118.1"),
    ("FILTRO, AR; PARA CAMINHAO", "Z09", "43.2"),  # ambíguo 43 x 54: ambos Z09
    ("CAIXA, PASSAGEM; CONCRETO ARMADO; PARA INSTALACOES ELETRICAS", "Z09", "22"),
])
def test_sistema1_regras(clf, texto, classe, regra):
    r = clf.classificar(texto, modo="s1")
    assert (r.classe, r.regra_id) == (classe, regra), r.justificativa


def test_atributos():
    a = extrair("VALVULA; DIAMETRO 1 1/2 POL; 16 BAR; 13,8 KV; DUREZA 70 SHORE A; 20 A 22,5 mm")
    assert a.polegadas == pytest.approx(1.5)
    assert a.bar == 16 and a.kv == pytest.approx(13.8) and a.shore == 70
    assert a.ampere is None  # "20 A 22,5" é faixa, não corrente


def test_baixa_confianca_sem_llm_marca_revisao(clf):
    r = clf.classificar("TERMINAL, ELETRICO COMPRESSAO; TIPO ANEL; COBRE", modo="auto")
    assert r.sistema == "S1 (sem LLM)" and r.revisar


class _LLMFalso:
    """Cliente no formato OpenAI que devolve uma resposta fixa e guarda o prompt."""
    def __init__(self, resposta: dict):
        self.resposta, self.prompts = resposta, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.prompts.append(kw["messages"])
        msg = SimpleNamespace(content=json.dumps(self.resposta))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_s2_acionado_e_classe_conferida_com_a_base():
    llm = _LLMFalso({"familia_id": "184", "regra_id": "184", "classe": "Z03", "confianca": 0.9,
                     "justificativa": "interruptor"})
    clf = Classificador(client=llm, limiar=0.99)
    r = clf.classificar("INTERRUPTOR, HORARIO; TIPO SEMANAL; 10 A; 220 V")
    assert r.sistema == "S2" and llm.prompts
    assert r.classe == "Z09"  # a regra 184 define Z09; a base prevalece sobre o LLM
    assert r.revisar and "prevalece a base" in r.justificativa


def test_s2_nao_acionado_quando_s1_confiante():
    llm = _LLMFalso({})
    r = Classificador(client=llm).classificar("VALVULA, GAVETA; DIAMETRO NOMINAL 12 POL")
    assert r.sistema == "S1" and not llm.prompts


def test_amostra_e_memoria():
    df = pd.read_csv(os.path.join(AQUI, "amostra.csv"))
    mem = Memoria.de_dataframe(df)
    clf = Classificador(memoria=mem)
    out = clf.classificar_df(df, "Texto_PT", "Codigo_Material", modo="s1")
    m = avaliar(out)
    assert m["itens"] == 10
    aceitos = out[~out["insp_revisar"]]
    assert (aceitos["insp_classe"] == aceitos["Classe_Inspecao_Atual"]).all()

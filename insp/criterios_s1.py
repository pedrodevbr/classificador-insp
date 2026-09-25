"""Predicados do Sistema 1 para os subitens (nível 2) da base.

Cada subitem vira um predicado sobre os atributos extraídos do Texto_PT.
- Predicados "objetivo": limiares numéricos ou sinalizadores (kV, pol, marca, desenho...).
- Predicados "palavra-chave": presença de termos distintivos do subitem.
- Predicados "residual": subitens "Demais ...", sempre atendidos quando alcançados.

Os subitens são avaliados na ordem da base; o primeiro atendido define a classe.
Os predicados escritos à mão abaixo sobrepõem a derivação automática.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .base import Regra
from .texto import Atributos, tokens, contem_seq

OBJETIVO, PALAVRA, RESIDUAL = "objetivo", "palavra-chave", "residual"

GENERICAS = {"marca", "modelo", "desenho", "referencia", "sem referencia", "justificativa",
             "sem desenho", "catalogo", "uso geral", "acessorio", "material", "projeto"}


@dataclass
class Contexto:
    codigo: str | None = None


Pred = Callable[[Atributos, Contexto], bool]


def _nucleo_eh(a: Atributos, *nomes: str) -> bool:
    alvo = {tokens(n)[0] for n in nomes if tokens(n)}
    return bool(a.nucleo) and a.nucleo[0] in alvo


def _codigo_em(ctx: Contexto, *codigos: str) -> bool:
    return bool(ctx.codigo) and str(ctx.codigo).lstrip("0") in codigos


def _acessorio(a: Atributos, *principais: str) -> bool:
    """Item cujo núcleo não é o equipamento principal (ex.: 'SUPORTE, PARA-RAIOS')."""
    return not _nucleo_eh(a, *principais) or a.tem("acessorio", "suporte", "caixa ligacao", "contador descarga")


P: dict[str, tuple[Pred, str]] = {
    # Anéis
    "3.1": (lambda a, c: a.tem("anel coletor", "coletor") and (a.tem("unidade geradora", "ug", "gerador") or a.kv is not None), OBJETIVO),
    "3.2": (lambda a, c: a.tem("desgaste") and a.tem("turbina", "rotor") and (a.diametro_mm or 0) > 2000, OBJETIVO),
    "3.3": (lambda a, c: a.tem("anticorona", "anel protecao", "anel equalizador"), PALAVRA),
    "3.4": (lambda a, c: a.tem("oring"), PALAVRA),
    "3.5": (lambda a, c: a.tem("fluido", "temperatura servico", "temperatura trabalho", "pressao maxima", "pressao trabalho"), OBJETIVO),
    "3.6": (lambda a, c: a.tem("desgaste"), PALAVRA),
    "3.7": (lambda a, c: a.tem("oleodinamico", "servomotor", "comporta", "vertedouro", "munhao"), PALAVRA),
    "3.8": (lambda a, c: a.tem("disjuntor", "seccionadora", "gis", "sf6"), PALAVRA),
    "3.9": (lambda a, c: a.tem("segmento"), PALAVRA),
    "3.10": (lambda a, c: a.tem("vedacao", "raspador", "feltro") and a.tem("aplicacao", "equipamento", "valvula", "bomba", "cilindro"), PALAVRA),
    "3.11": (lambda a, c: a.tem("espacador", "anel guia", "encosto", "elastico", "trava") and a.tem("aplicacao", "equipamento"), PALAVRA),
    "3.12": (lambda a, c: a.norma, OBJETIVO),
    "3.13": (lambda a, c: a.tem("lmr", "lista material reserva"), PALAVRA),
    "3.14": (lambda a, c: a.tem("vedacao") and a.tem("nao circular", "plano", "retangular", "quadrada"), PALAVRA),
    "3.15": (lambda a, c: a.tem("aco", "aluminio", "bronze", "inox", "inoxidavel", "pvc", "poliester", "feltro", "delrin"), PALAVRA),
    # Baterias
    "7.1": (lambda a, c: a.tem("servico auxiliar", "servicos auxiliares") or (a.tem("eletrolito") and not a.tem("seca", "descarregada")), OBJETIVO),
    "7.2": (lambda a, c: a.tem("seca", "descarregada", "eletrolito separado"), PALAVRA),
    "7.3": (lambda a, c: a.tem("estacionaria", "banco bateria", "nobreak", "vrla"), PALAVRA),
    "7.4": (lambda a, c: a.tem("pocket"), PALAVRA),
    "7.5": (lambda a, c: a.tem("automotiva", "veiculo", "partida"), PALAVRA),
    "7.6": (lambda a, c: a.tem("tracionaria", "empilhadeira", "carro eletrico"), PALAVRA),
    "7.7": (lambda a, c: _nucleo_eh(a, "pilha") and a.tem("alcalina") or a.tem("aa", "aaa"), PALAVRA),
    "7.8": (lambda a, c: a.tem("recarregavel", "nimh", "litio", "ion litio"), PALAVRA),
    # Bombas
    "9.1": (lambda a, c: _codigo_em(c, "108120", "108138", "709135", "709136", "99309"), OBJETIVO),
    "9.2": (lambda a, c: not _nucleo_eh(a, "bomba") and a.tem("selo", "anel", "diafragma", "rotor", "impelidor") and not a.marca_modelo, OBJETIVO),
    "9.3": (lambda a, c: not _nucleo_eh(a, "bomba") and a.marca_modelo, OBJETIVO),
    "9.4": (lambda a, c: _nucleo_eh(a, "bomba"), OBJETIVO),
    # Buchas mecânicas
    "13.1": (lambda a, c: a.tem("cobre", "inox", "inoxidavel"), OBJETIVO),
    "13.2": (lambda a, c: a.desenho or a.tem("tolerancia", "embalagem"), OBJETIVO),
    # Buchas de passagem / isoladores
    "14.1": (lambda a, c: not _acessorio(a, "bucha", "isolador") and (a.kv or 0) > 45, OBJETIVO),
    "14.2": (lambda a, c: not _acessorio(a, "bucha", "isolador"), OBJETIVO),
    "14.3": (lambda a, c: _acessorio(a, "bucha", "isolador"), OBJETIVO),
    # Cabos de dados
    "15.1": (lambda a, c: a.tem("conector", "hdmi", "usb", "patch cord", "rj45"), PALAVRA),
    "15.2": (lambda a, c: a.tem("utp", "ftp") and not a.marca_modelo, OBJETIVO),
    "16.1": (lambda a, c: a.tem("opgw"), PALAVRA),
    "18.1": (lambda a, c: a.tem("chi", "odcecd"), PALAVRA),
    "20.1": (lambda a, c: a.tem("projeto", "lance", "trecho"), PALAVRA),
    "23.1": (lambda a, c: a.tem("banco", "fator potencia", "kvar"), PALAVRA),
    "30.1": (lambda a, c: _nucleo_eh(a, "torre") and a.tem("completa"), PALAVRA),
    "30.2": (lambda a, c: a.tem("esfera sinalizacao", "baliza"), PALAVRA),
    "30.3": (lambda a, c: a.desenho, OBJETIVO),
    "31.1": (lambda a, c: a.tem("motocompressor"), PALAVRA),
    "31.2": (lambda a, c: a.tem("hermetico", "semihermetico", "scroll"), PALAVRA),
    "31.3": (lambda a, c: _nucleo_eh(a, "compressor") and a.marca_modelo, OBJETIVO),
    "31.4": (lambda a, c: not _nucleo_eh(a, "compressor") or a.tem("kit", "reparo", "acessorio"), OBJETIVO),
    "43.1": (lambda a, c: a.tem("filtro ar", "elemento filtrante ar", "area industrial")
             and not a.tem("arcondicionado", "automovel", "caminhao", "veiculo", "automotivo", "guindaste"), PALAVRA),
    "45.1": (lambda a, c: a.tem("rigido", "galvanizado"), PALAVRA),
    "45.2": (lambda a, c: a.tem("corrugado", "flexivel"), PALAVRA),
    "45.3": (lambda a, c: a.tem("junta expansao", "dilatacao"), PALAVRA),
    "46.1": (lambda a, c: a.tem("grau", "carga ruptura", "carga trabalho"), OBJETIVO),
    "49.1": (lambda a, c: _codigo_em(c, "516023", "703625") or a.tem("unidade geradora", "gerador"), OBJETIVO),
    "54.1": (lambda a, c: a.tem("fumaca", "mascara"), PALAVRA),
    "54.2": (lambda a, c: a.tem("automovel", "caminhao", "guindaste", "veiculo", "automotivo"), PALAVRA),
    "58.1": (lambda a, c: a.tem("smdt", "industrial", "trilho din", "automacao"), PALAVRA),
    "68.1": (lambda a, c: a.tem("smildt"), OBJETIVO),
    "70.1": (lambda a, c: a.tem("smildt"), OBJETIVO),
    "71.1": (lambda a, c: a.tem("membrana", "bolsa", "barramento blindado", "tc", "tp", "transformador"), PALAVRA),
    "71.2": (lambda a, c: a.tem("ensaio isolacao", "resistencia isolacao"), PALAVRA),
    "71.3": (lambda a, c: a.tem("circunferencial") and a.shore is None, OBJETIVO),
    "71.4": (lambda a, c: a.desenho and a.certificado, OBJETIVO),
    "72.1": (lambda a, c: a.tem("papelao", "ptfe", "grafitado", "teflon"), PALAVRA),
    "72.2": (lambda a, c: a.tem("secao circular", "cordao", "redonda"), PALAVRA),
    "72.3": (lambda a, c: a.tem("nao circular", "plana", "retangular"), PALAVRA),
    "72.4": (lambda a, c: a.tem("area industrial"), PALAVRA),
    "72.5": (lambda a, c: a.desenho, OBJETIVO),
    "72.6": (lambda a, c: a.tem("metalica", "cobre", "bronze", "inox", "inoxidavel"), PALAVRA),
    "72.7": (lambda a, c: a.tem("dresser"), PALAVRA),
    "72.8": (lambda a, c: a.tem("carretel"), PALAVRA),
    "74.1": (lambda a, c: a.tem("led"), PALAVRA),
    "75.1": (lambda a, c: a.tem("led"), PALAVRA),
    "80.1": (lambda a, c: a.tem("protecao", "epi", "raspa", "vaqueta", "isolante", "nitrilica", "latex", "seguranca"), PALAVRA),
    "82.1": (lambda a, c: a.tem("hidraulica", "pneumatica", "pressao trabalho", "ensaio isolacao", "ar comprimido", "oleo"), PALAVRA),
    "87.1": (lambda a, c: a.desenho or (a.arame_mm or 0) > 1.5, OBJETIVO),
    "87.2": (lambda a, c: _codigo_em(c, "710968", "263710") or a.tem("constante elastica", "composicao quimica"), OBJETIVO),
    "88.1": (lambda a, c: a.tem("projeto", "especificacao tecnica") or (a.kw or 0) >= 132, OBJETIVO),
    "93.1": (lambda a, c: a.tem("inspecao") or a.certificado, OBJETIVO),
    "94.1": (lambda a, c: not _acessorio(a, "pararaio") and (a.kv or 0) > 45, OBJETIVO),
    "94.2": (lambda a, c: not _acessorio(a, "pararaio"), OBJETIVO),
    "94.3": (lambda a, c: _acessorio(a, "pararaio"), OBJETIVO),
    "100.1": (lambda a, c: a.tem("industrial", "60309") or "ip6" in a.texto_norm or "ip4" in a.texto_norm, PALAVRA),
    "106.1": (lambda a, c: a.tem("monumental", "barragem"), PALAVRA),
    "106.2": (lambda a, c: a.tem("40 w", "40w", "2x40") , PALAVRA),
    "106.3": (lambda a, c: a.tem("eletronico"), PALAVRA),
    # Relés: ANSI + palavras-chave
    "107.1": (lambda a, c: bool(a.ansi & {50, 51, 67, 87}) or a.tem("sobrecorrente", "subcorrente", "diferencial"), PALAVRA),
    "107.2": (lambda a, c: a.tem("multifuncao", "numerico", "ied"), PALAVRA),
    "107.3": (lambda a, c: bool(a.ansi & {25, 81}) or a.tem("frequencia", "sincronismo"), PALAVRA),
    "107.4": (lambda a, c: 86 in a.ansi or a.tem("bloqueio", "lockout"), PALAVRA),
    "107.5": (lambda a, c: a.tem("temporizador", "tempo", "ciclico", "timer"), PALAVRA),
    "107.6": (lambda a, c: a.tem("termico", "sobrecarga", "termistor", "ptc", "temperatura"), PALAVRA),
    "107.7": (lambda a, c: bool(a.ansi & {27, 59, 64}) or a.tem("sobretensao", "subtensao", "tensao residual"), PALAVRA),
    "107.8": (lambda a, c: a.tem("supervisao", "monitor", "falta fase", "sequencia fase"), PALAVRA),
    "107.9": (lambda a, c: a.tem("auxiliar", "multiplicador"), PALAVRA),
    "107.10": (lambda a, c: a.tem("miniatura", "interface", "plug in", "base plugavel"), PALAVRA),
    "107.11": (lambda a, c: a.tem("biestavel", "latch", "retencao"), PALAVRA),
    "107.12": (lambda a, c: a.tem("reed", "ampola"), PALAVRA),
    "109.1": (lambda a, c: a.marca_modelo, OBJETIVO),
    "109.2": (lambda a, c: a.desenho, OBJETIVO),
    "116.1": (lambda a, c: a.marca_modelo and not a.tem("mecanico", "bulbo", "capilar"), OBJETIVO),
    "116.2": (lambda a, c: not a.tem("mecanico", "bulbo", "capilar"), OBJETIVO),
    "116.3": (lambda a, c: True, OBJETIVO),
    "118.1": (lambda a, c: a.tem("industrial", "smmadt", "esquema pintura", "epoxi", "poliuretano", "petrobras"), PALAVRA),
    "122.1": (lambda a, c: (a.kv or 0) > 13.8 and (a.kva or 0) > 50, OBJETIVO),
    "123.1": (lambda a, c: not _acessorio(a, "transformador", "tc", "tp", "tpc") and ((a.kv or 0) >= 13.8 or (a.kva or 0) >= 25), OBJETIVO),
    "123.2": (lambda a, c: not _acessorio(a, "transformador", "tc", "tp", "tpc") and a.exatidao is not None and a.exatidao < 0.3, OBJETIVO),
    "123.3": (lambda a, c: not _acessorio(a, "transformador", "tc", "tp", "tpc"), OBJETIVO),
    "123.4": (lambda a, c: True, OBJETIVO),
    "124.1": (lambda a, c: _nucleo_eh(a, "transmissor") and a.tem("pressao"), OBJETIVO),
    "124.2": (lambda a, c: not _nucleo_eh(a, "transmissor") or a.tem("manifold", "suporte", "acessorio"), OBJETIVO),
    # Válvulas
    "125.1": (lambda a, c: (a.polegadas or 0) >= 10, OBJETIVO),
    "125.2": (lambda a, c: (a.tem("inox", "inoxidavel") and (a.polegadas or 0) > 2) or a.tem("pneumatica", "seguranca", "alivio")
              or (a.bar or 0) > 10, OBJETIVO),
    "125.3": (lambda a, c: a.tem("certificado material") or (a.tem("sede", "haste", "obturador") and a.norma), OBJETIVO),
    "128.1": (lambda a, c: a.tem("aco carbono", "schedule", "sch", "a106", "a53") and not a.tem("pvc", "cobre", "aluminio"), OBJETIVO),
    "140.1": (lambda a, c: a.tem("corona"), PALAVRA),
    "140.2": (lambda a, c: a.tem("disjuntor", "seccionadora"), PALAVRA),
    "155.1": (lambda a, c: a.tem("cabo") and a.desenho, OBJETIVO),
    "168.1": (lambda a, c: a.tem("blindado", "potencia", "termocontratil") or (a.kv or 0) >= 1, OBJETIVO),
    "175.1": (lambda a, c: a.tem("quimico", "reagente", "solucao", "acido", "formol", "fosfato"), PALAVRA),
    "192.1": (lambda a, c: a.shore is None and not a.tem("dureza"), OBJETIVO),
    "192.2": (lambda a, c: True, OBJETIVO),
}


# Subitens que, embora não comecem com "Demais", são o caso residual da família.
RESIDUAIS = {"6.2", "16.2", "20.2", "46.2", "58.2", "74.2", "75.2", "80.2", "88.2", "93.2",
             "100.2", "118.2", "122.2", "155.2", "168.2", "175.2"}


def predicado(regra: Regra, familia: Regra) -> tuple[Pred, str]:
    """Retorna (predicado, tipo) para um subitem, com derivação automática se não houver override."""
    if regra.id in P:
        return P[regra.id]
    nome = regra.subgrupo.lower()
    if regra.id in RESIDUAIS or nome.startswith("demais") or "demais" in nome:
        return (lambda a, c: True), RESIDUAL
    if "sem justificativa de marca" in nome or "sem marca/modelo" in nome:
        return (lambda a, c: not a.marca_modelo), OBJETIVO
    if "com justificativa de marca" in nome or "com marca/modelo" in nome:
        return (lambda a, c: a.marca_modelo), OBJETIVO
    if "sem desenho" in nome:
        return (lambda a, c: not a.desenho), OBJETIVO
    if "com desenho" in nome or "conforme desenho" in nome:
        return (lambda a, c: a.desenho), OBJETIVO
    fam_kw = {tuple(tokens(k)) for k in familia.palavras_pt}
    distintivas = [tokens(k) for k in regra.palavras_pt
                   if k.lower() not in GENERICAS and tuple(tokens(k)) not in fam_kw and tokens(k)]
    return (lambda a, c: any(contem_seq(a.toks, d) for d in distintivas)), PALAVRA

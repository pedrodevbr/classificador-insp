"""Sistema 1 — classificação rápida, determinística e explicável.

1. Identifica a família pelo substantivo-núcleo do Texto_PT (casamento de frases).
2. Percorre os subitens da família na ordem da base; o primeiro predicado atendido
   define a classe.
3. (Opcional) Consulta precedentes rotulados (histórico) por similaridade de texto.
4. Calcula uma confiança; abaixo do limiar o item é encaminhado ao Sistema 2.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .base import Base, Regra, ID_RESIDUAL
from .criterios_s1 import Contexto, predicado, OBJETIVO, PALAVRA, RESIDUAL
from .texto import Atributos, extrair, contem_seq


@dataclass
class CandidatoFamilia:
    id: str
    nome: str
    score: float
    frase: str
    onde: str  # 'inicio' | 'cabeca' | 'texto' | 'nucleo'


@dataclass
class ResultadoS1:
    classe: str | None
    regra_id: str | None
    confianca: float
    familia_id: str | None
    candidatos: list[CandidatoFamilia]
    atributos: Atributos
    trilha: list[str] = field(default_factory=list)
    precedentes: list[dict] = field(default_factory=list)

    @property
    def justificativa(self) -> str:
        return " | ".join(self.trilha)


def pontuar_familias(base: Base, a: Atributos, top: int = 5) -> list[CandidatoFamilia]:
    cands = []
    for fam in base.familias:
        melhor = None
        for frase, peso in base.frases[fam.id]:
            n = len(frase)
            if a.cabeca[:n] == frase:
                s, onde = 10 + 2 * n, "inicio"
            elif n >= 2 and contem_seq(a.cabeca, frase):
                s, onde = 5 + n, "cabeca"
            elif contem_seq(a.toks, frase):
                s, onde = 1 + 0.5 * n, "texto"
            elif a.nucleo and frase[0] == a.nucleo[0] and len(frase[0]) > 3:
                s, onde = 3.0, "nucleo"
            else:
                continue
            s *= peso
            if melhor is None or s > melhor.score:
                melhor = CandidatoFamilia(fam.id, fam.familia, s, " ".join(frase), onde)
        if melhor:
            cands.append(melhor)
    cands.sort(key=lambda c: c.score, reverse=True)
    return cands[:top]


def _conf_familia(cands: list[CandidatoFamilia]) -> float:
    if not cands:
        return 0.1
    c1 = cands[0]
    margem = c1.score - (cands[1].score if len(cands) > 1 else 0)
    if c1.onde == "inicio":
        return 0.95 if margem >= 1 else 0.6
    if c1.onde == "cabeca":
        return 0.75 if margem >= 1 else 0.5
    if c1.onde == "texto":
        return 0.35
    return 0.25


def aplicar_subitens(fam: Regra, a: Atributos, ctx: Contexto) -> tuple[Regra | None, str, list[str]]:
    """Retorna (regra atendida, tipo do predicado, trilha de avaliação)."""
    if not fam.filhos:
        return fam, OBJETIVO, [f"{fam.id} escopo único → {fam.classe}"]
    trilha = []
    for sub in fam.filhos:
        pred, tipo = predicado(sub, fam)
        try:
            ok = bool(pred(a, ctx))
        except Exception:  # predicado nunca deve derrubar a classificação
            ok = False
        if ok:
            trilha.append(f"{sub.id} '{sub.subgrupo}' atendido ({tipo}) → {sub.classe}")
            return sub, tipo, trilha
    trilha.append("nenhum subitem atendido")
    return None, "", trilha


class Sistema1:
    def __init__(self, base: Base, memoria=None):
        self.base = base
        self.memoria = memoria  # Memoria de precedentes (opcional)

    def classificar(self, texto_pt: str, codigo: str | None = None) -> ResultadoS1:
        a = extrair(texto_pt)
        ctx = Contexto(codigo=codigo)
        cands = pontuar_familias(self.base, a)
        conf_f = _conf_familia(cands)
        trilha: list[str] = []

        if not cands:
            res = self.base.regras[ID_RESIDUAL]
            trilha.append("nenhuma família reconhecida → residual 180 (peças sem desenho)")
            r = ResultadoS1(res.classe, res.id, 0.15, None, [], a, trilha)
            return self._com_precedentes(r, texto_pt, codigo)

        fam = self.base.regras[cands[0].id]
        trilha.append(f"família {fam.id} {fam.familia} (frase '{cands[0].frase}' em {cands[0].onde}, "
                      f"conf {conf_f:.2f})")
        regra, tipo, t_sub = aplicar_subitens(fam, a, ctx)
        trilha += t_sub
        if regra is None:
            r = ResultadoS1(None, None, conf_f * 0.3, fam.id, cands, a, trilha)
            return self._com_precedentes(r, texto_pt, codigo)

        conf_r = {OBJETIVO: 1.0, PALAVRA: 0.85, RESIDUAL: 0.85}.get(tipo, 0.5)
        r = ResultadoS1(regra.classe, regra.id, round(conf_f * conf_r, 3), fam.id, cands, a, trilha)
        return self._com_precedentes(r, texto_pt, codigo)

    def _com_precedentes(self, r: ResultadoS1, texto: str, codigo: str | None) -> ResultadoS1:
        if not self.memoria:
            return r
        r.precedentes = self.memoria.buscar(texto, excluir_codigo=codigo)
        fortes = [p for p in r.precedentes if p["similaridade"] >= 0.8]
        if fortes:
            classes = {p["classe"] for p in fortes}
            if r.classe in classes and len(classes) == 1:
                r.confianca = round(min(1.0, r.confianca + 0.15), 3)
                r.trilha.append(f"precedente(s) similares confirmam {r.classe}")
            elif r.classe not in classes:
                r.confianca = round(min(r.confianca, 0.5), 3)
                r.trilha.append(f"precedentes similares divergem ({', '.join(sorted(classes))})")
        return r

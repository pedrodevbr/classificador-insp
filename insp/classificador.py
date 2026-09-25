"""Orquestrador System 1 / System 2.

Modos:
- "s1":   só o Sistema 1 (sem custo de LLM).
- "s2":   Sistema 2 para todos os itens (S1 ainda roda para montar o contexto).
- "auto": Sistema 1; escala ao Sistema 2 quando a confiança < limiar.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, asdict
from typing import Callable

import pandas as pd

from .base import Base, carregar_base
from .memoria import Memoria
from .sistema1 import Sistema1
from .sistema2 import Sistema2, MODELO_PADRAO

LIMIAR_PADRAO = 0.75
log = logging.getLogger(__name__)


@dataclass
class Resultado:
    classe: str | None
    regra_id: str | None
    regra_desc: str | None
    sistema: str            # "S1" | "S2" | "S1 (S2 falhou)" | "S1 (sem LLM)"
    confianca: float
    revisar: bool
    justificativa: str
    classe_s1: str | None
    regra_s1: str | None
    conf_s1: float
    classe_s2: str | None = None
    regra_s2: str | None = None
    conf_s2: float | None = None
    familias_candidatas: str = ""
    atributos: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def cliente_openrouter(api_key: str | None = None):
    from openai import OpenAI
    key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    return OpenAI(base_url=os.getenv("INSP_LLM_BASE_URL", "https://openrouter.ai/api/v1"), api_key=key)


class Classificador:
    def __init__(self, base: Base | None = None, client=None, modelo: str = MODELO_PADRAO,
                 limiar: float = LIMIAR_PADRAO, memoria: Memoria | None = None):
        self.base = base or carregar_base()
        self.s1 = Sistema1(self.base, memoria)
        self.s2 = Sistema2(self.base, client, modelo) if client else None
        self.limiar = limiar

    def _desc(self, rid: str | None) -> str | None:
        r = self.base.regras.get(rid or "")
        return f"{r.familia} / {r.subgrupo}" if r else None

    def classificar(self, texto_pt: str, codigo: str | None = None, modo: str = "auto") -> Resultado:
        r1 = self.s1.classificar(texto_pt, codigo)
        cands = "; ".join(f"{c.id} {c.nome} ({c.score:.1f})" for c in r1.candidatos[:3])
        base = dict(classe_s1=r1.classe, regra_s1=r1.regra_id, conf_s1=r1.confianca,
                    familias_candidatas=cands, atributos=str(r1.atributos.resumo()))

        precisa_s2 = modo == "s2" or (modo == "auto" and (r1.confianca < self.limiar or r1.classe is None))
        if not precisa_s2:
            return Resultado(r1.classe, r1.regra_id, self._desc(r1.regra_id), "S1", r1.confianca,
                             r1.classe is None or r1.confianca < self.limiar, r1.justificativa, **base)
        if self.s2 is None:
            return Resultado(r1.classe, r1.regra_id, self._desc(r1.regra_id), "S1 (sem LLM)", r1.confianca,
                             True, r1.justificativa + " | baixa confiança: requer S2/revisão humana", **base)
        try:
            r2 = self.s2.classificar(texto_pt, r1)
        except Exception as e:  # falha de rede/modelo não pode perder o item
            log.warning("S2 falhou: %s", e)
            return Resultado(r1.classe, r1.regra_id, self._desc(r1.regra_id), "S1 (S2 falhou)", r1.confianca,
                             True, f"{r1.justificativa} | erro S2: {e}", **base)

        concorda = r2["classe"] == r1.classe
        revisar = r2["sem_regra"] or r2["classe"] is None or r2["confianca"] < 0.6 or bool(r2["alertas"])
        just = r2["justificativa"]
        if r2["alertas"]:
            just += " | ALERTAS: " + "; ".join(r2["alertas"])
        just += f" | S1 {'concorda' if concorda else 'divergia'} ({r1.classe}/{r1.regra_id})"
        return Resultado(r2["classe"], r2["regra_id"], self._desc(r2["regra_id"]), "S2", r2["confianca"],
                         revisar, just, classe_s2=r2["classe"], regra_s2=r2["regra_id"],
                         conf_s2=r2["confianca"], **base)

    def classificar_df(self, df: pd.DataFrame, col_texto: str = "Texto_PT", col_codigo: str | None = None,
                       modo: str = "auto", progresso: Callable[[int, int], None] | None = None) -> pd.DataFrame:
        linhas = []
        total = len(df)
        for i, (_, row) in enumerate(df.iterrows(), 1):
            cod = row.get(col_codigo) if col_codigo else None
            cod = None if pd.isna(cod) else str(cod).split(".")[0] if cod is not None else None
            texto = "" if pd.isna(row.get(col_texto)) else str(row.get(col_texto))
            linhas.append(self.classificar(texto, cod, modo).as_dict())
            if progresso:
                progresso(i, total)
        res = pd.DataFrame(linhas).add_prefix("insp_")
        return pd.concat([df.reset_index(drop=True), res], axis=1)


def avaliar(df: pd.DataFrame, col_real: str = "Classe_Inspecao_Atual") -> dict:
    """Métricas contra a classe atual (quando a planilha a contém)."""
    d = df[df[col_real].astype(str).str.match(r"^Z\d\d$")]
    if d.empty:
        return {}
    acerto = (d["insp_classe"] == d[col_real])
    out = {"itens": len(d), "acuracia": round(acerto.mean(), 3),
           "por_sistema": d.assign(ok=acerto).groupby("insp_sistema")["ok"].agg(["count", "mean"]).round(3).to_dict("index"),
           "revisar": int(d["insp_revisar"].sum())}
    s1 = d[d["insp_sistema"] == "S1"]
    if len(s1):
        out["acuracia_s1_aceitos"] = round((s1["insp_classe"] == s1[col_real]).mean(), 3)
    out["matriz"] = pd.crosstab(d[col_real], d["insp_classe"].fillna("—")).to_dict()
    return out

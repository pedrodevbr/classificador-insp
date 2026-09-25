"""Memória de precedentes: materiais já classificados, recuperados por similaridade.

Usada pelo Sistema 1 para reforçar/contestar a regra e pelo Sistema 2 como exemplos.
"""
from __future__ import annotations

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .texto import normalizar


class Memoria:
    def __init__(self, textos: list[str], classes: list[str], codigos: list[str] | None = None, k: int = 5):
        self.textos = textos
        self.classes = classes
        self.codigos = codigos or [""] * len(textos)
        self.k = k
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), preprocessor=normalizar,
                                   sublinear_tf=True)
        self.mat = self.vec.fit_transform(textos)

    @classmethod
    def de_dataframe(cls, df: pd.DataFrame, col_texto: str = "Texto_PT",
                     col_classe: str = "Classe_Inspecao_Atual", col_codigo: str | None = "Codigo_Material"):
        d = df[df[col_texto].notna() & df[col_classe].astype(str).str.match(r"^Z\d\d$")]
        cod = d[col_codigo].astype(str).tolist() if col_codigo and col_codigo in d else None
        return cls(d[col_texto].astype(str).tolist(), d[col_classe].astype(str).tolist(), cod)

    def buscar(self, texto: str, excluir_codigo: str | None = None) -> list[dict]:
        sims = cosine_similarity(self.vec.transform([texto]), self.mat)[0]
        ordem = sims.argsort()[::-1]
        out = []
        for i in ordem:
            if excluir_codigo and self.codigos[i] == str(excluir_codigo):
                continue
            out.append({"codigo": self.codigos[i], "classe": self.classes[i],
                        "similaridade": round(float(sims[i]), 3), "texto": self.textos[i][:300]})
            if len(out) >= self.k:
                break
        return out

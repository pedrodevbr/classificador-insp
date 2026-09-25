"""Carrega a base hierárquica de critérios (família > subitem) do Excel."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache

import pandas as pd

from .texto import tokens

CAMINHO_PADRAO = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dados", "criterios_inspecao.xlsx")

CLASSES = {
    "Z01": "Classe 1 — inspeção completa",
    "Z02": "Inspeção em fábrica / equipamento principal e de projeto",
    "Z03": "Inspeção no recebimento com verificação técnica dimensional, construtiva ou funcional",
    "Z04": "Inspeção no recebimento com exigência de certificado, ensaio ou documentação do fabricante",
    "Z09": "Sem inspeção técnica (conferência comercial no recebimento)",
}

ID_RESIDUAL = "180"  # peças mecânicas sem desenho (regra residual do Leia-me)

# Frases extras de identificação de família, para núcleos comuns no SAP que a base
# não lista como palavra-chave. Só entram na detecção de família, nunca nos subitens.
ALIASES: dict[str, list[str]] = {
    "3": ["anel vedacao", "oring", "anel"],
    "7": ["bateria", "pilha"],
    "13": ["bucha bronze", "bucha nylon", "casquilho"],
    "14": ["bucha passagem", "isolador", "bucha isoladora"],
    "15": ["cabo utp", "cabo rede", "patch cord", "cabo hdmi", "cabo usb"],
    "21": ["cabo potencia", "cabo forca", "cabo unipolar", "cabo isolado"],
    "22": ["caixa passagem", "caixa derivacao", "condulete"],
    "40": ["disjuntor"],
    "56": ["fita isolante", "fita adesiva", "fita autofusao"],
    "60": ["fusivel"],
    "64": ["conector aterramento", "grampo aterramento"],
    "76": ["lampada"],
    "88": ["motor eletrico", "motor inducao", "motor trifasico", "motor monofasico"],
    "94": ["pararaio"],
    "107": ["rele"],
    "110": ["rolamento"],
    "125": ["valvula", "registro"],
    "126": ["valvula solenoide", "eletrovalvula"],
    "127": ["cabo aco"],
    "129": ["cotovelo", "niple", "te", "curva tubo", "reducao", "uniao"],
    "132": ["alicate", "martelo", "chave fenda", "chave boca", "chave estrela", "broca", "serra"],
    "184": ["interruptor"],
}


@dataclass
class Regra:
    id: str
    nivel: int
    pai: str | None
    area: str
    familia: str
    subgrupo: str
    palavras_pt: list[str]
    palavras_es: list[str]
    regra_pt: str
    regra_es: str
    classe: str | None
    observacao: str = ""
    filhos: list["Regra"] = field(default_factory=list)

    @property
    def rotulo(self) -> str:
        return f"{self.id} — {self.familia} / {self.subgrupo}"

    def texto_llm(self) -> str:
        cl = self.classe or "—"
        kw = ", ".join(self.palavras_pt)
        return f"[{self.id}] {self.subgrupo} → {cl}\n    Regra: {self.regra_pt}\n    Palavras-chave: {kw}"


def _lista(v) -> list[str]:
    if not isinstance(v, str):
        return []
    # não quebrar decimais ("arame acima de 1,5 mm")
    return [p.strip() for p in re.split(r",(?!\d)", v) if p.strip()]


def _classe(row) -> str | None:
    for col in ("Classe final", "Classe"):
        v = row.get(col)
        if isinstance(v, str) and v.strip().upper().startswith("Z"):
            return v.strip().upper()
    return None


class Base:
    def __init__(self, regras: list[Regra]):
        self.regras = {r.id: r for r in regras}
        self.familias: list[Regra] = [r for r in regras if r.nivel == 1]
        for r in regras:
            if r.pai and r.pai in self.regras:
                self.regras[r.pai].filhos.append(r)
        self.frases = {f.id: self._frases_familia(f) for f in self.familias}

    def _frases_familia(self, fam: Regra) -> list[tuple[list[str], float]]:
        """Frases (tokens, peso) que identificam a família no texto."""
        # nome da família e aliases pesam mais que palavras-chave (desempate: "cabo de aço"
        # é família própria e também palavra-chave de Polias)
        frases: list[tuple[list[str], float]] = [(tokens(p), 1.1) for p in ALIASES.get(fam.id, [])]
        nome = fam.familia.split("(")[0]
        for parte in nome.replace("/", ",").replace(" e ", ",").split(","):
            if parte.strip():
                frases.append((tokens(parte), 1.1))
        for p in fam.palavras_pt:
            frases.append((tokens(p), 1.0))
        # palavras-chave de subitens ajudam a achar a família, com peso menor
        for filho in fam.filhos:
            for p in filho.palavras_pt:
                tk = tokens(p)
                if len(tk) >= 2:
                    frases.append((tk, 0.8))
        vistos, unicas = set(), []
        for tk, w in frases:
            # frases só com números/unidades ("5 mm", "500 kv") não identificam família
            if not any(len(t) >= 3 and t.isalpha() for t in tk):
                continue
            if tuple(tk) not in vistos:
                vistos.add(tuple(tk))
                unicas.append((tk, w))
        return unicas

    def indice_compacto(self) -> str:
        linhas = []
        for f in self.familias:
            if f.filhos:
                subs = "; ".join(f"{c.id} {c.subgrupo} ({c.classe})" for c in f.filhos)
                linhas.append(f"{f.id} {f.familia}: {subs}")
            else:
                linhas.append(f"{f.id} {f.familia} ({f.classe})")
        return "\n".join(linhas)

    def bloco_familia(self, fid: str) -> str:
        f = self.regras[fid]
        cab = f"FAMÍLIA {f.id} — {f.familia} [{f.area}]"
        if not f.filhos:
            return cab + "\n" + f.texto_llm()
        return cab + "\n" + "\n".join(c.texto_llm() for c in f.filhos)


@lru_cache(maxsize=4)
def carregar_base(caminho: str = CAMINHO_PADRAO) -> Base:
    df = pd.read_excel(caminho, sheet_name="Base_Hierarquica", dtype=str)
    regras = []
    for _, row in df.iterrows():
        rid = str(row["ID"]).strip()
        if not rid or rid == "nan":
            continue
        pai = row.get("ID pai")
        regras.append(Regra(
            id=rid,
            nivel=int(float(row["Nível"])),
            pai=str(pai).strip() if isinstance(pai, str) and pai.strip() else None,
            area=str(row.get("Área") or ""),
            familia=str(row.get("Família (nível 1)") or ""),
            subgrupo=str(row.get("Subgrupo / critério (nível 2)") or ""),
            palavras_pt=_lista(row.get("Palavras-chave (PT)")),
            palavras_es=_lista(row.get("Palabras clave (ES)")),
            regra_pt=str(row.get("Regra completa (PT)") or ""),
            regra_es=str(row.get("Regla completa (ES)") or ""),
            classe=_classe(row),
            observacao=str(row.get("Observações da revisão") or ""),
        ))
    return Base(regras)

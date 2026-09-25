"""Sistema 2 — raciocínio deliberado com LLM sobre as regras candidatas.

Recebe o Texto_PT, os atributos extraídos, a trilha do Sistema 1, as famílias
candidatas (com todos os subitens) e precedentes. Devolve regra, classe e
justificativa em JSON. A classe é conferida contra a regra citada.
"""
from __future__ import annotations

import json
import os
import re

from .base import Base, CLASSES
from .sistema1 import ResultadoS1

MODELO_PADRAO = os.getenv("INSP_LLM_MODEL", "x-ai/grok-4.1-fast")

INSTRUCOES = """Você é engenheiro de inspeção de materiais da ITAIPU Binacional.
Classifique o material na classe de inspeção usando EXCLUSIVAMENTE a base de critérios.

Método (obrigatório):
1) Identifique a família pelo substantivo-núcleo do descritivo (primeiro termo antes da vírgula)
   e pelo qualificador. Não confunda famílias por semelhança de palavras (ex.: prensa-cabo não é
   bucha mecânica; conector elétrico não é parafuso).
2) Percorra os subitens da família NA ORDEM apresentada; aplique a classe do PRIMEIRO critério
   integralmente atendido pelo texto. Não presuma informações ausentes.
3) Se nenhuma família se aplicar, use a regra residual 180 (peças mecânicas sem desenho, Z09)
   ou, se o material for claramente elétrico/crítico, indique a família mais análoga e marque
   "sem_regra": true.

Classes:
{classes}

Responda APENAS com JSON:
{{"familia_id": "...", "regra_id": "...", "classe": "Z0?", "confianca": 0.0-1.0,
  "sem_regra": false, "justificativa": "cite o critério e o trecho do texto que o atende"}}"""


def montar_prompt(base: Base, texto: str, s1: ResultadoS1, n_familias: int = 4) -> tuple[str, str]:
    classes = "\n".join(f"- {k}: {v}" for k, v in CLASSES.items() if k != "Z01")
    sistema = INSTRUCOES.format(classes=classes)

    ids = [c.id for c in s1.candidatos[:n_familias]]
    blocos = "\n\n".join(base.bloco_familia(i) for i in ids) if ids else "(nenhuma família candidata)"
    partes = [f"TEXTO_PT DO MATERIAL:\n{texto}",
              f"ATRIBUTOS EXTRAÍDOS: {json.dumps(s1.atributos.resumo(), ensure_ascii=False)}",
              f"ANÁLISE DO SISTEMA 1 (rápido, pode estar errado): classe={s1.classe} regra={s1.regra_id} "
              f"confiança={s1.confianca} | {s1.justificativa}",
              f"FAMÍLIAS CANDIDATAS (detalhadas):\n{blocos}"]
    if not s1.candidatos or s1.candidatos[0].onde in ("texto", "nucleo"):
        partes.append("ÍNDICE COMPLETO DA BASE (use se nenhuma candidata servir):\n" + base.indice_compacto())
    if s1.precedentes:
        ex = "\n".join(f"- [{p['classe']}] (sim {p['similaridade']}) {p['texto']}" for p in s1.precedentes)
        partes.append("PRECEDENTES JÁ CLASSIFICADOS (referência, não regra):\n" + ex)
    return sistema, "\n\n".join(partes)


def _json(texto: str) -> dict:
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)
        if m:
            return json.loads(m.group(0))
        raise


class Sistema2:
    def __init__(self, base: Base, client, modelo: str = MODELO_PADRAO):
        self.base = base
        self.client = client
        self.modelo = modelo

    def classificar(self, texto: str, s1: ResultadoS1) -> dict:
        sistema, usuario = montar_prompt(self.base, texto, s1)
        resp = self.client.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        out = _json(resp.choices[0].message.content)
        return self.validar(out)

    def validar(self, out: dict) -> dict:
        """Garante que a classe corresponde à regra citada (a base é a fonte da verdade)."""
        classe = str(out.get("classe") or "").strip().upper()
        rid = str(out.get("regra_id") or "").strip()
        regra = self.base.regras.get(rid)
        alertas = []
        if regra and regra.classe:
            if classe != regra.classe:
                alertas.append(f"LLM indicou {classe or '—'} mas a regra {rid} define {regra.classe}; "
                               "prevalece a base")
                classe = regra.classe
        elif regra and not regra.classe:
            alertas.append(f"regra {rid} é uma família sem classe própria; subitem não identificado")
        else:
            alertas.append(f"regra '{rid}' não existe na base")
        if classe not in CLASSES:
            alertas.append(f"classe inválida '{classe}'")
            classe = None
        try:
            conf = float(out.get("confianca", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        return {"classe": classe, "regra_id": rid if regra else None, "confianca": max(0.0, min(conf, 1.0)),
                "sem_regra": bool(out.get("sem_regra")) or regra is None,
                "justificativa": str(out.get("justificativa") or ""), "alertas": alertas}

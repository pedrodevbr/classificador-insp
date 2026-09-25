"""Normalização do Texto_PT e extração de atributos objetivos.

Os descritivos SAP seguem o padrão "NOME, QUALIFICADOR; ATRIBUTO VALOR; ...".
O primeiro segmento (antes de ',' ou ';') é o substantivo-núcleo do material e
o segundo segmento costuma ser o qualificador que define a família.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

STOPWORDS = {
    "de", "da", "do", "das", "dos", "para", "com", "e", "a", "o", "em", "na", "no",
    "nas", "nos", "tipo", "p", "c", "ou", "por", "ao", "as", "os", "um", "uma",
}

# Sinônimos/grafias que precisam virar um único token antes da tokenização.
_SUBSTITUICOES = [
    (r"\bo[\s\-']?rings?\b", "oring"),
    (r"\bno[\s\-]?breaks?\b", "nobreak"),
    (r"\bmoto[\s\-]compressor", "motocompressor"),
    (r"\bsemi[\s\-]hermetico", "semihermetico"),
    (r"\bpara[\s\-]raios?\b", "pararaio"),
    (r"\bporta[\s\-]escovas?\b", "portaescova"),
    (r"\bprensa[\s\-]cabos?\b", "prensa cabo"),
    (r"\bniquel[\s\-]cadmio\b", "nicd"),
    (r"\bchumbo[\s\-]acido\b", "chumboacido"),
    (r"\bsm\s*\.\s*dt\b", "smdt"),
    (r"\bsmil\s*\.\s*dt\b", "smildt"),
    (r"\bsmma\s*\.\s*dt\b", "smmadt"),
    (r"\bod\s*\.\s*cecd\b", "odcecd"),
    (r"\bar[\s\-]condicionado\b", "arcondicionado"),
]


def sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def singular(tok: str) -> str:
    """Stemming mínimo de plural em português (aplicado igual em texto e regras)."""
    if len(tok) <= 3 or tok.isdigit():
        return tok
    for suf, rep in (("oes", "ao"), ("aes", "ao"), ("eis", "el"), ("ais", "al"),
                     ("res", "r"), ("zes", "z"), ("ns", "m")):
        if tok.endswith(suf) and len(tok) > len(suf) + 2:
            return tok[: -len(suf)] + rep
    if tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, com sinônimos unificados."""
    t = sem_acento(str(texto or "")).lower()
    for padrao, rep in _SUBSTITUICOES:
        t = re.sub(padrao, rep, t)
    return t


def tokens(texto: str) -> list[str]:
    t = normalizar(texto)
    brutos = re.findall(r"[a-z0-9]+", t)
    return [singular(x) for x in brutos if x not in STOPWORDS]


def segmentos(texto: str) -> list[str]:
    return [s.strip() for s in re.split(r"[,;\n]", str(texto or "")) if s.strip()]


def contem_seq(hay: list[str], agulha: list[str]) -> bool:
    n = len(agulha)
    if n == 0:
        return False
    return any(hay[i:i + n] == agulha for i in range(len(hay) - n + 1))


# ---------------------------------------------------------------------------
# Extração de atributos numéricos e sinalizadores
# ---------------------------------------------------------------------------
_NUM = r"(\d+(?:[.,]\d+)?)"


def _f(x: str) -> float:
    return float(x.replace(".", "").replace(",", ".")) if re.fullmatch(r"\d{1,3}(\.\d{3})+", x) \
        else float(x.replace(",", "."))


def _valores(padrao: str, t: str) -> list[float]:
    out = []
    for m in re.finditer(padrao, t):
        try:
            out.append(_f(m.group(1)))
        except ValueError:
            pass
    return out


def _polegadas(t: str) -> list[float]:
    """Captura 10", 1 1/2", 3/4 POL, 2 POLEGADAS, DN 250 (mm → pol)."""
    vals = []
    frac = r"(\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?)"
    for m in re.finditer(frac + r"\s*(?:\"|''|pol\b|pol\.|polegadas?)", t):
        s = m.group(1).strip()
        try:
            if " " in s:
                inteiro, fr = s.split()
                a, b = fr.split("/")
                vals.append(float(inteiro) + float(a) / float(b))
            elif "/" in s:
                a, b = s.split("/")
                vals.append(float(a) / float(b))
            else:
                vals.append(_f(s))
        except (ValueError, ZeroDivisionError):
            pass
    for m in re.finditer(r"\bdn\s*" + _NUM, t):
        vals.append(_f(m.group(1)) / 25.4)
    return vals


@dataclass
class Atributos:
    texto_norm: str
    toks: list[str]
    nucleo: list[str]          # tokens do 1º segmento (substantivo-núcleo)
    cabeca: list[str]          # tokens do 1º + 2º segmentos
    kv: float | None = None
    ampere: float | None = None
    kw: float | None = None
    kva: float | None = None
    polegadas: float | None = None
    bar: float | None = None
    shore: float | None = None
    mm2: float | None = None
    diametro_mm: float | None = None
    arame_mm: float | None = None
    exatidao: float | None = None
    ansi: set[int] = field(default_factory=set)
    marca_modelo: bool = False
    desenho: bool = False
    norma: bool = False
    certificado: bool = False

    def tem(self, *termos: str) -> bool:
        """True se qualquer termo (frase normalizada) aparece no texto."""
        for termo in termos:
            seq = tokens(termo)
            if seq and contem_seq(self.toks, seq):
                return True
        return False

    def resumo(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()
             if k not in ("texto_norm", "toks", "nucleo", "cabeca") and v not in (None, False, set())}
        if "ansi" in d:
            d["ansi"] = sorted(d["ansi"])
        return d


def extrair(texto: str) -> Atributos:
    t = normalizar(texto)
    segs = segmentos(texto)
    nucleo = tokens(segs[0]) if segs else []
    cabeca = tokens(" ".join(segs[:2])) if segs else []
    a = Atributos(texto_norm=t, toks=tokens(texto), nucleo=nucleo, cabeca=cabeca)

    kv = _valores(_NUM + r"\s*kv\b", t)
    v = [x / 1000 for x in _valores(_NUM + r"\s*(?:v|vca|vcc|vac|vdc|volts?)\b", t)]
    a.kv = max(kv + v) if (kv or v) else None
    amp = _valores(_NUM + r"\s*(?:a|amperes?)\b(?!\s*\d)", t) + [x * 1000 for x in _valores(_NUM + r"\s*ka\b", t)]
    a.ampere = max(amp) if amp else None
    kw = _valores(_NUM + r"\s*kw\b", t) + [x * 0.7457 for x in _valores(_NUM + r"\s*(?:cv|hp)\b", t)]
    a.kw = max(kw) if kw else None
    kva = _valores(_NUM + r"\s*kva\b", t) + [x * 1000 for x in _valores(_NUM + r"\s*mva\b", t)]
    a.kva = max(kva) if kva else None
    pol = _polegadas(t)
    a.polegadas = max(pol) if pol else None
    bar = _valores(_NUM + r"\s*bar\b", t) + [x / 14.5 for x in _valores(_NUM + r"\s*psi\b", t)] \
        + [x * 10 for x in _valores(_NUM + r"\s*mpa\b", t) if "resistencia" not in t]
    a.bar = max(bar) if bar else None
    sh = _valores(_NUM + r"\s*(?:\+/?-\s*\d+\s*)?shore", t) + _valores(r"shore\s*a?\s*" + _NUM, t) \
        + _valores(r"dureza\s*(?:de\s*)?" + _NUM, t)
    a.shore = max(sh) if sh else None
    mm2 = _valores(_NUM + r"\s*mm2\b", t) + _valores(_NUM + r"\s*mm²", t)
    a.mm2 = max(mm2) if mm2 else None
    diam = _valores(r"diametro(?:\s+(?:externo|interno|nominal))?\s*(?:de\s*)?" + _NUM + r"\s*mm", t)
    a.diametro_mm = max(diam) if diam else None
    arame = _valores(r"(?:diametro\s+do\s+)?arame\s*(?:de\s*)?" + _NUM + r"\s*mm", t) \
        + _valores(r"fio\s*(?:de\s*)?" + _NUM + r"\s*mm", t)
    a.arame_mm = max(arame) if arame else None
    ex = _valores(r"(?:classe\s+de\s+)?exatidao\s*(?:de\s*)?" + _NUM, t)
    a.exatidao = min(ex) if ex else None
    a.ansi = {int(x) for x in re.findall(r"ansi\s*(\d{2})", t)}

    a.marca_modelo = bool(re.search(
        r"\b(marca|modelo|fabricante|referencia|ref\b|ref\.|part\s*number|p/n|catalogo|similar)", t))
    a.desenho = bool(re.search(r"\b(desenho|dwg|des\.|croqui|conforme\s+projeto)", t))
    a.norma = bool(re.search(r"\b(astm|sae|din|nbr|abnt|iso|aisi|iec|ieee|aws|asme|api)\b", t))
    a.certificado = bool(re.search(r"\b(certificad|ensaio|laudo|rastreabilidade)", t))
    return a

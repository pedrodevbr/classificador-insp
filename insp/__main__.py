"""CLI: python -m insp entrada.xlsx [-o saida.xlsx] [--modo auto|s1|s2] [--historico hist.xlsx]"""
import argparse
import json
import logging

import pandas as pd

from . import Classificador, Memoria, avaliar, cliente_openrouter
from .classificador import LIMIAR_PADRAO


def _ler(caminho: str) -> pd.DataFrame:
    return pd.read_csv(caminho) if caminho.lower().endswith(".csv") else pd.read_excel(caminho)


def main():
    ap = argparse.ArgumentParser(description="Classifica materiais (Texto_PT) em classes de inspeção.")
    ap.add_argument("entrada", nargs="?", help="planilha .xlsx/.csv com a coluna Texto_PT")
    ap.add_argument("-t", "--texto", help="classifica um único Texto_PT")
    ap.add_argument("-o", "--saida", help="arquivo de saída (.xlsx ou .csv)")
    ap.add_argument("--col-texto", default="Texto_PT")
    ap.add_argument("--col-codigo", default="Codigo_Material")
    ap.add_argument("--modo", choices=["auto", "s1", "s2"], default="auto")
    ap.add_argument("--limiar", type=float, default=LIMIAR_PADRAO, help="confiança mínima para aceitar o S1")
    ap.add_argument("--historico", help="planilha com Texto_PT + Classe_Inspecao_Atual (precedentes)")
    ap.add_argument("--modelo", help="modelo do LLM (OpenRouter)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    mem = Memoria.de_dataframe(_ler(args.historico)) if args.historico else None
    kw = {"modelo": args.modelo} if args.modelo else {}
    clf = Classificador(client=cliente_openrouter() if args.modo != "s1" else None,
                        limiar=args.limiar, memoria=mem, **kw)
    if args.modo != "s1" and clf.s2 is None:
        logging.warning("OPENROUTER_API_KEY ausente: itens de baixa confiança ficam marcados para revisão.")

    if args.texto:
        print(json.dumps(clf.classificar(args.texto, modo=args.modo).as_dict(), ensure_ascii=False, indent=2))
        return
    if not args.entrada:
        ap.error("informe a planilha de entrada ou --texto")

    df = _ler(args.entrada)
    col_cod = args.col_codigo if args.col_codigo in df.columns else None
    out = clf.classificar_df(df, args.col_texto, col_cod, args.modo,
                             progresso=lambda i, n: logging.info("item %d/%d", i, n) if i % 50 == 0 or i == n else None)
    if args.saida:
        (out.to_csv(args.saida, index=False) if args.saida.lower().endswith(".csv")
         else out.to_excel(args.saida, index=False))
        logging.info("resultado salvo em %s", args.saida)
    cols = [c for c in (col_cod, "insp_classe", "insp_regra_id", "insp_sistema", "insp_confianca", "insp_revisar") if c]
    print(out[cols].to_string(index=False))
    if "Classe_Inspecao_Atual" in out.columns:
        print(json.dumps(avaliar(out), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

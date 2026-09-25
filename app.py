import io
import os

import pandas as pd
import streamlit as st

from insp import Classificador, Memoria, avaliar, carregar_base, cliente_openrouter, CLASSES
from insp.classificador import LIMIAR_PADRAO
from insp.sistema2 import MODELO_PADRAO

st.set_page_config(page_title="Classificador de Inspeção", layout="wide")


def ler_planilha(arq) -> pd.DataFrame:
    return pd.read_csv(arq) if arq.name.lower().endswith(".csv") else pd.read_excel(arq)


def main():
    st.title("Classificador de Materiais — Classe de Inspeção")
    st.caption("Sistema 1 (regras rápidas e explicáveis) → Sistema 2 (LLM) quando a confiança é baixa. "
               "Entrada: Texto_PT.")

    st.sidebar.header("Configurações")
    api_key = st.sidebar.text_input("OpenRouter API Key", type="password", value=os.getenv("OPENROUTER_API_KEY", ""))
    modelo = st.sidebar.text_input("Modelo (Sistema 2)", MODELO_PADRAO)
    modo = st.sidebar.radio("Modo", ["auto", "s1", "s2"], format_func={
        "auto": "Auto (S1 → S2 se incerto)", "s1": "Só Sistema 1 (sem LLM)", "s2": "Sempre Sistema 2"}.get)
    limiar = st.sidebar.slider("Confiança mínima para aceitar o S1", 0.0, 1.0, LIMIAR_PADRAO, 0.05)
    hist = st.sidebar.file_uploader("Histórico classificado (opcional)", type=["xlsx", "csv"],
                                    help="Planilha com Texto_PT e Classe_Inspecao_Atual; vira base de precedentes.")
    if modo != "s1" and not api_key:
        st.sidebar.warning("Sem API key: itens de baixa confiança ficam marcados para revisão.")

    memoria = Memoria.de_dataframe(ler_planilha(hist)) if hist else None
    clf = Classificador(client=cliente_openrouter(api_key) if (api_key and modo != "s1") else None,
                        modelo=modelo, limiar=limiar, memoria=memoria)

    tab1, tab2, tab3 = st.tabs(["Individual", "Lote", "Base de critérios"])

    with tab1:
        texto = st.text_area("Texto_PT", "VALVULA, ESFERA; ACO INOXIDAVEL AISI 316; DIAMETRO 3 POL; ROSCA NPT", height=160)
        if st.button("Classificar", disabled=not texto.strip()):
            with st.spinner("Classificando..."):
                r = clf.classificar(texto, modo=modo)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Classe", r.classe or "—")
            c2.metric("Regra", r.regra_id or "—")
            c3.metric("Sistema", r.sistema)
            c4.metric("Confiança", f"{r.confianca:.2f}")
            if r.classe:
                st.info(f"**{r.classe}** — {CLASSES.get(r.classe, '')}\n\n{r.regra_desc or ''}")
            if r.revisar:
                st.warning("Recomenda-se revisão humana.")
            st.write("**Justificativa:**", r.justificativa)
            with st.expander("Detalhes (S1, S2, atributos)"):
                st.json(r.as_dict())

    with tab2:
        arq = st.file_uploader("Planilha (.xlsx/.csv)", type=["xlsx", "xls", "csv"])
        if arq:
            df = ler_planilha(arq)
            st.dataframe(df.head())
            cols = df.columns.tolist()
            col_texto = st.selectbox("Coluna do texto", cols, index=cols.index("Texto_PT") if "Texto_PT" in cols else 0)
            op_cod = ["(nenhuma)"] + cols
            col_cod = st.selectbox("Coluna do código do material (opcional)", op_cod,
                                   index=op_cod.index("Codigo_Material") if "Codigo_Material" in cols else 0)
            if st.button("Processar lote"):
                barra = st.progress(0.0)
                out = clf.classificar_df(df, col_texto, None if col_cod == "(nenhuma)" else col_cod, modo,
                                         progresso=lambda i, n: barra.progress(i / n, f"{i}/{n}"))
                st.success("Concluído")
                st.dataframe(out[[c for c in out.columns if c.startswith("insp_")] +
                                 ([col_cod] if col_cod in out.columns else [])])
                if "Classe_Inspecao_Atual" in out.columns:
                    st.subheader("Comparação com a classe atual")
                    st.json(avaliar(out))
                buf = io.BytesIO()
                out.to_excel(buf, index=False)
                st.download_button("Baixar resultado (.xlsx)", buf.getvalue(), "classificacao_inspecao.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab3:
        base = carregar_base()
        busca = st.text_input("Buscar família")
        for f in base.familias:
            if busca and busca.lower() not in f.familia.lower():
                continue
            with st.expander(f"{f.id} — {f.familia} ({f.area})"):
                st.text(base.bloco_familia(f.id))


if __name__ == "__main__":
    main()

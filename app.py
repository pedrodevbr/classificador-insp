import streamlit as st
import pandas as pd
from document_utils import extract_text_from_file
import os
from classificador import get_openrouter_client, get_llm_classification
st.set_page_config(page_title="Classificador de Materiais", layout="wide")

def main():
    st.title("Classificador de Materiais e Equipamentos - Inspeção")
    st.markdown("---")

    # Sidebar para Configurações
    st.sidebar.header("Configurações")
    api_key = st.sidebar.text_input("OpenRouter API Key", type="password", value=os.getenv("OPENROUTER_API_KEY", ""))
    
    if not api_key:
        st.warning("Por favor, insira sua API Key do OpenRouter na barra lateral.")
        st.stop()
        
    client = get_openrouter_client(api_key)

    # Abas para Modos de Operação
    tab1, tab2 = st.tabs(["Classificação Individual", "Processamento em Lote (Excel/CSV)"])

    # --- ABA 1: Individual ---
    with tab1:
        st.subheader("Análise Individual")
        
        # Opção de Entrada: Texto ou Arquivo
        input_method = st.radio("Método de Entrada:", ["Digitar Texto", "Upload de Documento (PDF/Doc)"], horizontal=True)
        
        desc_curta = ""
        texto_longo = ""
        
        if input_method == "Digitar Texto":
            desc_curta = st.text_input("Descrição Curta", "Rolamento 6205")
            texto_longo = st.text_area("Texto Longo (SAP)", "Rolamento rígido de esferas, folga C3, para motor elétrico.")
        else:
            doc_file = st.file_uploader("Carregue o documento técnico (PDF, DOCX, Imagem...)", type=["pdf", "docx", "png", "jpg", "jpeg"])
            if doc_file:
                with st.spinner("Extraindo texto do documento com Docling..."):
                    extracted_text = extract_text_from_file(doc_file)
                    st.success("Texto extraído!")
                    with st.expander("Ver texto extraído"):
                        st.markdown(extracted_text)
                    
                    # Usa o texto extraído como Texto Longo
                    texto_longo = extracted_text
                    desc_curta = st.text_input("Defina uma Descrição Curta para este item", value=doc_file.name)

        if st.button("Classificar Item", disabled=not (desc_curta and texto_longo)):
            with st.spinner("Consultando IA..."):
                result = get_llm_classification(client, desc_curta, texto_longo)
                
                st.success("Classificação Concluída!")
                st.json(result)
                
                if result.get("codigo_inspecao"):
                    st.info(f"**Código Sugerido:** {result['codigo_inspecao']}")
                if result.get("justificativa"):
                    st.write(f"**Justificativa:** {result['justificativa']}")

    # --- ABA 2: Lote ---
    with tab2:
        st.subheader("Upload de Arquivo")
        uploaded_file = st.file_uploader("Escolha um arquivo Excel ou CSV", type=["xlsx", "xls", "csv"])
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.write("Prévia dos Dados:")
                st.dataframe(df.head())
                
                # Seleção de Colunas
                cols = df.columns.tolist()
                col_desc = st.selectbox("Selecione a coluna de Descrição Curta", cols, index=0 if len(cols)>0 else None)
                col_long = st.selectbox("Selecione a coluna de Texto Longo", cols, index=1 if len(cols)>1 else 0)
                
                if st.button("Iniciar Processamento em Lote"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    def update_progress(current, total):
                        percent = int((current / total) * 100)
                        progress_bar.progress(percent)
                        status_text.text(f"Processando item {current} de {total}...")
                    
                    with st.spinner("Processando... Isso pode demorar um pouco."):
                        df_result = process_dataframe(
                            df, client, 
                            col_desc=col_desc, 
                            col_long=col_long,
                            progress_callback=update_progress
                        )
                    
                    st.success("Processamento Finalizado!")
                    st.dataframe(df_result)
                    
                    # Botão de Download
                    csv = df_result.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Baixar Resultados (CSV)",
                        data=csv,
                        file_name='classificacao_resultado.csv',
                        mime='text/csv',
                    )
                    
            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

if __name__ == "__main__":
    main()

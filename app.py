import streamlit as st
import pandas as pd
#from document_utils import generate_markdown_file
import os
from classificador import get_openrouter_client, get_llm_classification

st.set_page_config(page_title="Classificador de Materiais", layout="wide")

# --- Funções Utilitárias ---
def load_criterios():
    if not os.path.exists("criterios.md"):
        return "# Critérios de Classificação\nDefina as regras aqui..."
    with open("criterios.md", "r", encoding="utf-8") as f:
        return f.read()

def save_criterios(content):
    with open("criterios.md", "w", encoding="utf-8") as f:
        f.write(content)

def main():
    st.title("Classificador de Materiais e Equipamentos - Inspeção")
    st.markdown("---")

    # Sidebar para Configurações
    st.sidebar.header("Configurações")
    #api_key = st.sidebar.text_input("OpenRouter API Key", type="password", value=os.getenv("OPENROUTER_API_KEY", ""))
    api_key = "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"
    
    if not api_key:
        st.warning("Por favor, insira sua API Key do OpenRouter na barra lateral.")
        st.stop()
        
    client = get_openrouter_client(api_key)

    # Abas para Modos de Operação
    tab1, tab2, tab3 = st.tabs(["Classificação Individual","Report", "Editar criterios"])

    # --- ABA 1: Individual ---
    with tab1:
        st.subheader("Análise Individual")
        
        # Opção de Entrada: Texto ou Arquivo
        #input_method = st.radio("Método de Entrada:", ["Digitar Texto", "Upload de Documento (PDF/Doc)"], horizontal=True)
        input_method = st.radio("Método de Entrada:", ["Digitar Texto"], horizontal=True)

        desc_curta = ""
        texto_longo = ""
        
        if input_method == "Digitar Texto":
            desc_curta = st.text_input("Descrição Curta", "Rolamento 6205")
            texto_longo = st.text_area("Texto Longo (SAP)", "Rolamento rígido de esferas, folga C3, para motor elétrico.")
        #else:

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

    # --- EDITAR CRITÉRIOS ---
    with tab3:
        st.subheader("Configuração de Regras (criterios.md)")
        st.info("O conteúdo abaixo é enviado para a IA como guia para a classificação.")
        
        criterios_atuais = load_criterios()
        novo_conteudo = st.text_area("Editor de Markdown", value=criterios_atuais, height=500)
        
        if st.button("Salvar Critérios"):
            save_criterios(novo_conteudo)
            st.success("Arquivo 'criterios.md' atualizado com sucesso!") 


if __name__ == "__main__":
    main()


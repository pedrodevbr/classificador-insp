import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from classificador import get_llm_classification

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def classify_row_safe(client, desc, text_long, pbar=None):
    """Função wrapper com retry para classificação de uma linha."""
    try:
        result = get_llm_classification(client, desc, text_long)
        if pbar:
            pbar.update(1)
        return result
    except Exception as e:
        logging.error(f"Erro ao classificar item '{desc}': {e}")
        return {"codigo_inspecao": "ERRO", "justificativa": str(e)}

def process_dataframe(df, client, col_desc="Descrição", col_long="Texto Longo", progress_callback=None):
    """
    Processa um DataFrame pandas, adicionando colunas de classificação.
    
    Args:
        df: DataFrame input
        client: OpenAI client
        col_desc: Nome da coluna de descrição curta
        col_long: Nome da coluna de texto longo
        progress_callback: Função para atualizar barra de progresso (opcional)
    
    Returns:
        DataFrame processado
    """
    results = []
    
    total = len(df)
    
    # Criar uma cópia para não alterar o original durante a iteração se for view
    df_processed = df.copy()
    
    logging.info(f"Iniciando classificação de {total} itens...")

    for index, row in df.iterrows():
        desc = str(row.get(col_desc, ""))
        long_text = str(row.get(col_long, ""))
        
        # Chama a classificação
        classification = classify_row_safe(client, desc, long_text)
        
        results.append(classification)
        
        if progress_callback:
            progress_callback(index + 1, total)

    # Converter lista de dicts para DataFrame e concatenar
    df_results = pd.DataFrame(results)
    df_final = pd.concat([df_processed.reset_index(drop=True), df_results], axis=1)
    
    logging.info("Classificação concluída.")
    return df_final

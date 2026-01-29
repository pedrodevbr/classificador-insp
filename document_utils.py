import os
import tempfile
from docling.document_converter import DocumentConverter

def extract_text_from_file(uploaded_file):
    """
    Recebe um objeto UploadedFile do Streamlit e retorna o texto extraído usando Docling.
    """
    # Docling precisa de um caminho de arquivo, então salvamos temporariamente
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    try:
        converter = DocumentConverter()
        result = converter.convert(tmp_path)
        # Extrai o texto no formato markdown que preserva melhor a estrutura
        text_content = result.document.export_to_markdown()
        return text_content
    except Exception as e:
        return f"Erro ao processar documento: {str(e)}"
    finally:
        # Limpa o arquivo temporário
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

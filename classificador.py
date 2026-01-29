import os
import json
from openai import OpenAI

# Configuração Padrão
MODEL_NAME =  "x-ai/grok-4.1-fast"

def get_openrouter_client(api_key=None):
    """Retorna o cliente OpenAI configurado para OpenRouter."""
    if not api_key:
        api_key = "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"
    
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )

def load_criterios():
    """Carrega os critérios do arquivo md se existir, ou usa um placeholder."""
    try:
        with open('criterios.md', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "CRITÉRIOS NÃO ENCONTRADOS. POR FAVOR, FORNEÇA O ARQUIVO criterios.md."

def get_llm_classification(client, material_desc, long_text):
    """
    Envia os dados para a IA classificar com base na constante CRITERIOS_TEXTO.
    """
    criterios_texto = load_criterios()

    system_prompt = f"""
    Você é um Engenheiro Especialista em Inspeção de Materiais da ITAIPU Binacional.
    Sua tarefa é classificar materiais de estoque para definir o nível de inspeção de qualidade.
    
    UTILIZE ESTRITAMENTE OS SEGUINTES CRITÉRIOS:
    {criterios_texto}
    
    DEFINIÇÕES DE SAÍDA (CÓDIGOS):
    - "Z09": Não Aplicável
    - "Z04": Classe 3 com certificado (Uso obrigatório se o critério pedir "com certificado")
    - "Z03": Classe 3 (Inspeção padrão)
    - "Z02": Classe 2 (Inspeção na fábrica)
    - "Z01": Classe 1 (Inspeção completa)

    REGRAS DE DECISÃO:
    1. Analise a Descrição Curta e o Texto Longo.
    2. Encontre o grupo (ex: Rolamento, Válvula, Cabo) nos critérios acima.
    3. Verifique as condições específicas (tensão, diâmetro, material, se tem desenho).
    4. Se não encontrar o item específico, use a regra geral do grupo ou "Z09" se for item de baixo risco.
    
    Retorne APENAS um JSON válido.
    """

    user_prompt = f"""
    MATERIAL PARA CLASSIFICAR:

    Texto Longo (SAP): {long_text}
    
    Responda neste formato JSON exato:
    {{
        "codigo_inspecao": "Z??",
        "justificativa": "Cite a regra específica usada (ex: 'É um rolamento C3', 'É um cabo > 15kV')"
    }}
    """

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"codigo_inspecao": "ERRO", "justificativa": str(e)}

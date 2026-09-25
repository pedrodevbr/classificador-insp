# Classificador de Inspeção — System 1 / System 2

Classifica materiais industriais na **classe de inspeção** (Z02, Z03, Z04, Z09) a partir do **Texto_PT**,
usando a base hierárquica de critérios `dados/criterios_inspecao.xlsx` (aba `Base_Hierarquica`).

```
Texto_PT ──► SISTEMA 1 (rápido, determinístico) ──► confiança ≥ limiar? ──sim──► classe + regra
                 │                                        │
                 │                                       não
                 ▼                                        ▼
   1. família pelo substantivo-núcleo           SISTEMA 2 (LLM, deliberado)
   2. atributos (kV, pol, bar, Shore, mm²,      • recebe famílias candidatas com todos os subitens,
      marca/modelo, desenho, ANSI...)             atributos, trilha do S1 e precedentes
   3. subitens na ordem da base: o primeiro     • responde regra + classe + justificativa (JSON)
      critério atendido define a classe         • a classe é conferida com a regra citada
   4. precedentes similares (opcional)            (a base prevalece sobre o LLM)
```

- **Sistema 1** (`insp/sistema1.py`, `insp/criterios_s1.py`): sem custo, explicável (trilha regra a regra).
  Confiança alta quando a família aparece no início do descritivo e o subitem é decidido por critério objetivo.
- **Sistema 2** (`insp/sistema2.py`): acionado só nos itens incertos (família ausente/ambígua, nenhum subitem atendido,
  precedentes divergentes). Usa OpenRouter (`OPENROUTER_API_KEY`; modelo em `INSP_LLM_MODEL`).
- **Revisar**: marcado quando o S1 fica abaixo do limiar sem LLM disponível, quando o S2 não encontra regra,
  tem confiança < 0,6 ou quando a classe do LLM contradiz a regra citada.

## Uso

```bash
pip install -r requirements.txt

# um texto
python -m insp --texto "VALVULA, GAVETA; ACO CARBONO; DIAMETRO NOMINAL 12 POL" --modo s1

# planilha (coluna Texto_PT; Codigo_Material é opcional e habilita regras por código)
export OPENROUTER_API_KEY=...
python -m insp amostra.xlsx -o resultado.xlsx --modo auto --limiar 0.75 \
    --historico materiais_classificados.xlsx   # opcional: precedentes

# interface
streamlit run app.py
```

Modos: `s1` (só regras), `auto` (S1 → S2 se incerto), `s2` (LLM em todos os itens).
Se a planilha tiver `Classe_Inspecao_Atual`, o CLI imprime acurácia e matriz de confusão.

Colunas de saída (prefixo `insp_`): `classe`, `regra_id`, `regra_desc`, `sistema`, `confianca`, `revisar`,
`justificativa`, `classe_s1`, `regra_s1`, `conf_s1`, `classe_s2`, `regra_s2`, `conf_s2`,
`familias_candidatas`, `atributos`.

## Manutenção das regras

- Critérios, classes e ordem dos subitens: editar `dados/criterios_inspecao.xlsx`.
- Predicados objetivos (limiares numéricos, exclusões) dos subitens: `insp/criterios_s1.py` (dicionário `P`).
  Subitens sem predicado próprio usam derivação automática (palavras-chave distintivas, "com/sem marca",
  "com/sem desenho", "Demais …" = residual).
- Sinônimos de núcleo do SAP para detectar famílias: `ALIASES` em `insp/base.py`.

`criterios.md` e `legado.md` são as versões anteriores (texto) dos critérios, mantidas como referência.

## Testes

```bash
pytest -q
```

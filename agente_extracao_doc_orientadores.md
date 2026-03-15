# Agente de Extração e Organização de Documentos Orientadores

## Visão Geral

Este agente é responsável por processar PDFs da pasta `docOrientadores/`, extrair as informações pedagógicas estruturadas de cada documento e armazená-las em JSON organizado para consulta posterior pelo app de preenchimento automático de documentos.

---

## Estrutura esperada da pasta

```
docOrientadores/
├── FIS_EM_1serie.pdf
├── FIS_EM_2serie.pdf
├── MAT_EM_1serie.pdf
├── PORT_EF_9ano.pdf
└── ...
```

**Convenção de nomenclatura recomendada para os arquivos:**
`[DISCIPLINA]_[ETAPA]_[SERIE/ANO].pdf`

---

## O que este agente faz

1. Varre todos os PDFs da pasta `docOrientadores/`
2. Converte cada página relevante em imagem
3. Usa Vision (LLM) para extrair o conteúdo estruturado
4. Salva o resultado em JSON indexado por disciplina, etapa, série e bimestre
5. Ignora páginas não relevantes (capas, sumários, orientações de uso, links)

---

## Páginas relevantes para extração

O agente deve extrair **apenas** páginas que contenham tabelas do **Escopo-Sequência**, identificadas por:

- Cabeçalho contendo: `Escopo - Sequência`
- Presença das colunas: `Aula`, `Conteúdo`, `Objetivos de aprendizagem`, `Habilidades`, `Aprendizagem Essencial`
- Indicação de série e bimestre no topo da tabela

**Páginas a ignorar:**
- Capa
- Créditos
- Sumário
- Apresentação
- Orientações de Uso
- Links Importantes
- Aprendizagens Essenciais do Ano (visão macro)
- Páginas de detalhe das AEs (fundo verde/branco sem tabela de aulas)
- Matriz Prova Paulista
- Páginas de separação de seção (fundo verde escuro com apenas o título)

---

## Schema JSON de saída

```json
{
  "disciplina": "Física",
  "etapa": "EM",
  "serie": "1ª série",
  "bimestre": "1º Bimestre",
  "aulas": [
    {
      "numero": 1,
      "titulo": "Movimento e Repouso: Tudo é uma questão de referencial",
      "aprendizagem_essencial": "AE1 - Resolver problemas envolvendo corpos em movimento com velocidade e/ou aceleração constantes, representando trajetória, posição, velocidade e aceleração por meio de funções, gráficos e tabelas.",
      "habilidade": "EM13CNT204",
      "conteudo": "Conceitos iniciais para a descrição do movimento.",
      "objetivos_aprendizagem": [
        "Identificar os conceitos fundamentais da cinemática, incluindo ponto material, referencial, movimento e repouso.",
        "Diferenciar trajetória e velocidade escalar, distinguindo suas formas média e instantânea."
      ],
      "campos_opcionais": {
        "unidade_tematica": "",
        "conhecimentos_previos": [],
        "habilidades_relacionadas": [],
        "descritores_prova_paulista": [],
        "materiais_digitais": "",
        "livro_estudante": ""
      }
    }
  ]
}
```

---

## Prompt de extração (Vision)

Use este prompt ao enviar cada página de Escopo-Sequência para o modelo Vision:

```
Você é um agente de extração de dados pedagógicos.

Analise a imagem desta página e extraia o conteúdo da tabela de Escopo-Sequência.

Regras:
- Retorne APENAS JSON válido, sem texto antes ou depois
- Não inclua markdown, backticks ou qualquer outro caractere fora do JSON
- Se um campo não estiver visível ou legível, use string vazia "" ou array vazio []
- Os objetivos de aprendizagem devem ser uma lista, um item por objetivo
- Preserve o texto exatamente como está no documento, sem resumir

Schema obrigatório:
{
  "serie": "string",
  "bimestre": "string",
  "aulas": [
    {
      "numero": int,
      "titulo": "string",
      "aprendizagem_essencial": "string",
      "habilidade": "string",
      "conteudo": "string",
      "objetivos_aprendizagem": ["string"]
    }
  ]
}
```

---

## Lógica de processamento

```python
import google.generativeai as genai
import base64
import json
import os
from pdf2image import convert_from_path
from pathlib import Path
import io

# Configure sua chave de API do Google
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Modelos recomendados (escolha um):
# "gemini-1.5-flash"  → mais barato, ótimo custo-benefício para extração
# "gemini-1.5-pro"    → mais preciso, use se o flash errar muito
MODELO = "gemini-1.5-flash"

PASTA_PDFS = "./docOrientadores"
PASTA_SAIDA = "./docOrientadores/extraidos"

PROMPT_EXTRACAO = """
Você é um agente de extração de dados pedagógicos.
Analise a imagem desta página e extraia o conteúdo da tabela de Escopo-Sequência.

Regras:
- Retorne APENAS JSON válido, sem texto antes ou depois
- Não inclua markdown, backticks ou qualquer outro caractere fora do JSON
- Se um campo não estiver visível ou legível, use string vazia "" ou array vazio []
- Os objetivos de aprendizagem devem ser uma lista, um item por objetivo
- Preserve o texto exatamente como está no documento, sem resumir

Schema obrigatório:
{
  "serie": "string",
  "bimestre": "string",
  "aulas": [
    {
      "numero": int,
      "titulo": "string",
      "aprendizagem_essencial": "string",
      "habilidade": "string",
      "conteudo": "string",
      "objetivos_aprendizagem": ["string"]
    }
  ]
}
"""

PROMPT_CLASSIFICADOR = """
Analise esta imagem de uma página de um Guia do Currículo Priorizado.

Responda APENAS com uma das opções abaixo (sem explicação):
- ESCOPO_SEQUENCIA  → se a página contém uma tabela com colunas Aula, Conteúdo, Objetivos de aprendizagem, Habilidades, Aprendizagem Essencial
- IGNORAR           → qualquer outro tipo de página (capa, sumário, orientações, matriz, etc.)
"""

def imagem_para_bytes(imagem):
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    return buffer.getvalue()

def classificar_pagina(imagem):
    model = genai.GenerativeModel(MODELO)
    img_bytes = imagem_para_bytes(imagem)
    
    response = model.generate_content([
        {"mime_type": "image/png", "data": img_bytes},
        PROMPT_CLASSIFICADOR
    ])
    return response.text.strip()

def extrair_pagina(imagem):
    model = genai.GenerativeModel(MODELO)
    img_bytes = imagem_para_bytes(imagem)
    
    response = model.generate_content([
        {"mime_type": "image/png", "data": img_bytes},
        PROMPT_EXTRACAO
    ])
    texto = response.text.strip()
    # Remove backticks caso o modelo os inclua mesmo sendo instruído a não
    texto = texto.replace("```json", "").replace("```", "").strip()
    return json.loads(texto)

def processar_pdf(caminho_pdf, disciplina, etapa):
    print(f"\nProcessando: {caminho_pdf}")
    paginas = convert_from_path(caminho_pdf, dpi=150)

    resultado_completo = {
        "disciplina": disciplina,
        "etapa": etapa,
        "series": {}
    }

    for i, pagina in enumerate(paginas):
        print(f"  Página {i+1}/{len(paginas)}...", end=" ")

        tipo = classificar_pagina(pagina)

        if tipo != "ESCOPO_SEQUENCIA":
            print("ignorada")
            continue

        print("extraindo...")
        dados = extrair_pagina(pagina)

        serie = dados.get("serie", "desconhecida")
        bimestre = dados.get("bimestre", "desconhecido")

        if serie not in resultado_completo["series"]:
            resultado_completo["series"][serie] = {}

        if bimestre not in resultado_completo["series"][serie]:
            resultado_completo["series"][serie][bimestre] = []

        resultado_completo["series"][serie][bimestre].extend(dados.get("aulas", []))

    return resultado_completo

def processar_pasta():
    os.makedirs(PASTA_SAIDA, exist_ok=True)

    for arquivo in Path(PASTA_PDFS).glob("*.pdf"):
        # Pula JSONs já existentes para evitar reprocessamento
        nome_saida = f"{arquivo.stem}.json"
        caminho_saida = os.path.join(PASTA_SAIDA, nome_saida)
        if os.path.exists(caminho_saida):
            print(f"Já extraído, pulando: {arquivo.name}")
            continue

        # Extrai disciplina e etapa do nome do arquivo (ex: FIS_EM_1serie.pdf)
        partes = arquivo.stem.split("_")
        disciplina = partes[0] if len(partes) > 0 else "DESCONHECIDA"
        etapa = partes[1] if len(partes) > 1 else "DESCONHECIDA"

        resultado = processar_pdf(str(arquivo), disciplina, etapa)

        with open(caminho_saida, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)

        print(f"  Salvo em: {caminho_saida}")

if __name__ == "__main__":
    processar_pasta()
```

### Instalação das dependências

```bash
pip install google-generativeai pdf2image Pillow
```

> **Poppler necessário para o pdf2image:**
> - Windows: baixe em https://github.com/oschwartz10612/poppler-windows e adicione ao PATH
> - Linux: `sudo apt install poppler-utils`
> - Mac: `brew install poppler`

---

## Estrutura de saída dos JSONs

```
docOrientadores/
├── extraidos/
│   ├── FIS_EM_1serie.json
│   ├── FIS_EM_2serie.json
│   ├── MAT_EM_1serie.json
│   └── ...
```

Cada JSON segue o schema definido acima, indexado por série e bimestre para consulta rápida.

---

## Campos opcionais (a ativar conforme necessidade)

Estes campos estão presentes no PDF mas não são extraídos por padrão. Para ativá-los, adicione-os ao schema e ao prompt de extração:

| Campo | Onde aparece no PDF | Como ativar |
|---|---|---|
| `unidade_tematica` | Coluna da Matriz / lateral das AEs | Adicionar ao schema e prompt |
| `conhecimentos_previos` | Página de detalhe de cada AE | Processar páginas de AE separadamente |
| `habilidades_relacionadas` | Página de detalhe de cada AE | Processar páginas de AE separadamente |
| `descritores_prova_paulista` | Página de detalhe de cada AE | Processar páginas de AE separadamente |
| `materiais_digitais` | Tabela do Escopo-Sequência (links) | Adicionar ao schema e prompt |
| `livro_estudante` | Tabela do Escopo-Sequência | Adicionar ao schema e prompt |

---

## Observações importantes

- **DPI recomendado:** 150 para bom equilíbrio entre qualidade e tamanho da imagem
- **Modelo recomendado:** `gemini-1.5-flash` para extração (muito barato, ótimo custo-benefício); use `gemini-1.5-pro` se o flash errar muito em páginas complexas
- **Chave de API:** configure a variável de ambiente `GOOGLE_API_KEY` com sua chave do Google AI Studio (https://aistudio.google.com)
- **Reprocessamento:** Se um JSON já existe na pasta `extraidos/`, o agente pula o arquivo automaticamente para evitar custo desnecessário
- **Validação:** Após a extração, valide se o número de aulas extraídas por bimestre bate com o esperado (geralmente 14 aulas por bimestre neste formato de Guia do Currículo Priorizado SP)

import os
import io
import json
import base64
import time
from pathlib import Path
from pdf2image import convert_from_path
from anthropic import Anthropic, RateLimitError, APIStatusError
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODELO = "claude-haiku-4-5"

PASTA_PDFS = "./docOrientadores"
PASTA_SAIDA = "./docOrientadores/extraidos"

PROMPT_UNICO = """
Você é um agente de extração de dados pedagógicos de um Guia do Currículo Priorizado.

Analise a imagem desta página e realize as seguintes tarefas:

1. CLASSIFICAÇÃO: Determine se a página contém uma tabela de "Escopo-Sequência" (colunas: Aula, Conteúdo, Objetivos de aprendizagem, Habilidades, Aprendizagem Essencial).
2. EXTRAÇÃO: Se for uma tabela de Escopo-Sequência, extraia os dados conforme o schema. Se NÃO for (capa, sumário, orientações, etc.), retorne o campo "tipo" como "IGNORAR" e deixe "serie", "bimestre" e "aulas" vazios.

Regras:
- Preserve o texto original.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "tipo": {"type": "string", "enum": ["ESCOPO_SEQUENCIA", "IGNORAR"]},
        "serie": {"type": "string"},
        "bimestre": {"type": "string"},
        "aulas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "numero": {"type": "integer"},
                    "titulo": {"type": "string"},
                    "aprendizagem_essencial": {"type": "string"},
                    "habilidade": {"type": "string"},
                    "conteudo": {"type": "string"},
                    "objetivos_aprendizagem": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["numero", "titulo", "aprendizagem_essencial", "habilidade", "conteudo", "objetivos_aprendizagem"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["tipo", "serie", "bimestre", "aulas"],
    "additionalProperties": False,
}


def imagem_para_base64(imagem):
    buffer = io.BytesIO()
    imagem.save(buffer, format="JPEG", quality=75)
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


def call_claude_with_retry(base64_image, max_retries=5):
    retries = 0
    while retries < max_retries:
        try:
            response = client.messages.create(
                model=MODELO,
                max_tokens=2000,
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT_UNICO},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64_image,
                                },
                            },
                        ],
                    }
                ],
            )
            texto = next(b.text for b in response.content if b.type == "text")
            return texto
        except RateLimitError:
            wait = (retries + 1) * 3
            print(f"(rate limit - aguardando {wait}s)...", end=" ", flush=True)
            time.sleep(wait)
            retries += 1
        except APIStatusError as e:
            if e.status_code >= 500:
                wait = (retries + 1) * 3
                print(f"(erro servidor {e.status_code} - aguardando {wait}s)...", end=" ", flush=True)
                time.sleep(wait)
                retries += 1
            else:
                raise
    return None


def processar_pdf(caminho_pdf, disciplina, etapa):
    print(f"\nProcessando: {caminho_pdf}")
    paginas = convert_from_path(caminho_pdf, dpi=110)

    resultado_completo = {
        "disciplina": disciplina,
        "etapa": etapa,
        "series": {},
    }

    for i, pagina in enumerate(paginas):
        print(f"  Página {i+1}/{len(paginas)}...", end=" ", flush=True)

        try:
            b64_img = imagem_para_base64(pagina)
            res_json = call_claude_with_retry(b64_img)

            if not res_json:
                print("ERRO")
                continue

            dados = json.loads(res_json)
            tipo = dados.get("tipo", "IGNORAR")

            if tipo == "IGNORAR":
                print("ignorada")
                continue

            print("extraído!", end=" ", flush=True)

            serie = dados.get("serie", "desconhecida")
            bimestre = dados.get("bimestre", "desconhecido")

            if serie not in resultado_completo["series"]:
                resultado_completo["series"][serie] = {}
            if bimestre not in resultado_completo["series"][serie]:
                resultado_completo["series"][serie][bimestre] = []

            resultado_completo["series"][serie][bimestre].extend(dados.get("aulas", []))
            print(f"({serie} - {bimestre})")

        except Exception as e:
            print(f"erro ao processar página {i+1}: {e}")

    return resultado_completo


def processar_pasta():
    os.makedirs(PASTA_SAIDA, exist_ok=True)

    for arquivo in Path(PASTA_PDFS).glob("*.pdf"):
        nome_saida = f"{arquivo.stem}.json"
        caminho_saida = os.path.join(PASTA_SAIDA, nome_saida)

        partes = arquivo.stem.split("_")
        disciplina = partes[0] if len(partes) > 0 else "DESCONHECIDA"
        etapa = partes[1] if len(partes) > 1 else "DESCONHECIDA"

        resultado = processar_pdf(str(arquivo), disciplina, etapa)

        with open(caminho_saida, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)

        print(f"  Salvo em: {caminho_saida}")


if __name__ == "__main__":
    processar_pasta()

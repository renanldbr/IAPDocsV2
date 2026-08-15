import os
import io
import json
import base64
import time
import re
from pathlib import Path
from pdf2image import convert_from_path
from openai import OpenAI
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ.get("NVIDIA_API_KEY"),
)

MODELO = "meta/muse-glimmer-30b"

PASTA_PDFS = "./docOrientadores"
PASTA_SAIDA = "./docOrientadores/extraidos"

PROMPT_UNICO = """
Você é um agente de extração de dados pedagógicos de um Guia do Currículo Priorizado.

Analise a imagem desta página e realize as seguintes tarefas:

1. CLASSIFICAÇÃO: Determine se a página contém uma tabela de "Escopo-Sequência" (colunas: Aula, Conteúdo, Objetivos de aprendizagem, Habilidades, Aprendizagem Essencial).
2. EXTRAÇÃO: Se for uma tabela de Escopo-Sequência, extraia os dados conforme o schema abaixo. Se NÃO for (capa, sumário, orientações, etc.), retorne o campo "tipo" como "IGNORAR".

Regras:
- Retorne APENAS JSON válido.
- Não inclua markdown ou backticks.
- Preserve o texto original.

Schema de Retorno:
{
  "tipo": "ESCOPO_SEQUENCIA" ou "IGNORAR",
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


def imagem_para_base64(imagem):
    buffer = io.BytesIO()
    imagem.save(buffer, format="JPEG", quality=75)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def extrair_json(texto):
    texto = texto.strip()
    texto = re.sub(r"^```(json)?", "", texto).strip()
    texto = re.sub(r"```$", "", texto).strip()
    return texto


def call_nvidia_with_retry(base64_image, max_retries=5):
    retries = 0
    while retries < max_retries:
        try:
            response = client.chat.completions.create(
                model=MODELO,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT_UNICO},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                temperature=0.2,
                max_tokens=8192,
                stream=False,
            )
            return response.choices[0].message.content
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                wait = (retries + 1) * 3
                print(f"(rate limit - aguardando {wait}s)...", end=" ", flush=True)
                time.sleep(wait)
                retries += 1
            else:
                raise e
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
            res_texto = call_nvidia_with_retry(b64_img)

            if not res_texto:
                print("ERRO")
                continue

            dados = json.loads(extrair_json(res_texto))
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

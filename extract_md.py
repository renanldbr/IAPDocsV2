import os
import re
import sys
import json
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MODELO = "gpt-4o-mini"

PASTA_MDS = "./docOrientadores/extraidos"
PASTA_SAIDA = "./docOrientadores/extraidos"

# Casa "Escopo - Sequência 1ª série 1º Bimestre", "Escopo-Sequência", "3ºsérie" etc.
HEADER_RE = re.compile(
    r"Escopo\s*-?\s*Sequência(?:\s+(?P<serie_num>\d)[ºª]\s*s[ée]rie)?(?:\s+(?P<bim_num>\d)º\s*Bimestre)?",
    re.IGNORECASE,
)

PROMPT_TEMPLATE = """
Você é um agente de extração de dados pedagógicos de um Guia do Currículo Priorizado.

O texto abaixo é uma tabela de "Escopo-Sequência" (colunas: Aula, Conteúdo, Objetivos de
aprendizagem, Habilidades, Aprendizagem Essencial) que foi convertida de PDF para texto.
A conversão embaralhou a ordem das colunas/linhas, então frases de uma mesma aula podem
aparecer fragmentadas e fora de ordem. Reconstrua os dados de cada aula usando o número da
aula (1, 2, 3...) como âncora.

Série: {serie}
Bimestre: {bimestre}

Texto:
\"\"\"
{trecho}
\"\"\"

Retorne APENAS um JSON válido, sem markdown ou backticks, no formato:
{{
  "aulas": [
    {{
      "numero": int,
      "titulo": "string",
      "aprendizagem_essencial": "string",
      "habilidade": "string",
      "conteudo": "string",
      "objetivos_aprendizagem": ["string"]
    }}
  ]
}}

Se não houver aulas identificáveis no texto, retorne {{"aulas": []}}.
"""


def call_openai_with_retry(prompt, max_retries=5):
    retries = 0
    while retries < max_retries:
        try:
            response = client.chat.completions.create(
                model=MODELO,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
        except Exception as e:
            if "rate_limit_exceeded" in str(e).lower():
                wait = (retries + 1) * 3
                print(f"(RPM/TPM limit - aguardando {wait}s)...", end=" ", flush=True)
                time.sleep(wait)
                retries += 1
            else:
                raise e
    return None


def dividir_em_blocos(texto):
    """Divide o markdown em blocos (serie, bimestre, trecho) usando os cabeçalhos
    "Escopo - Sequência" como marcadores. Cabeçalhos sem número (páginas de
    continuação) herdam a série/bimestre do bloco anterior."""
    matches = list(HEADER_RE.finditer(texto))
    blocos = []
    serie_atual = None
    bimestre_atual = None

    for i, m in enumerate(matches):
        if m.group("serie_num"):
            serie_atual = f"{m.group('serie_num')}ª Série"
        if m.group("bim_num"):
            bimestre_atual = f"{m.group('bim_num')}º Bimestre"

        inicio = m.end()
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        trecho = texto[inicio:fim].strip()

        if serie_atual and bimestre_atual and len(trecho) > 80:
            blocos.append((serie_atual, bimestre_atual, trecho))

    return blocos


def processar_md(caminho_md, disciplina, etapa):
    print(f"\nProcessando: {caminho_md}")
    texto = Path(caminho_md).read_text(encoding="utf-8")
    blocos = dividir_em_blocos(texto)

    resultado_completo = {
        "disciplina": disciplina,
        "etapa": etapa,
        "series": {},
    }

    for serie, bimestre, trecho in blocos:
        print(f"  {serie} / {bimestre}...", end=" ", flush=True)
        prompt = PROMPT_TEMPLATE.format(serie=serie, bimestre=bimestre, trecho=trecho)
        try:
            res_json = call_openai_with_retry(prompt)
            if not res_json:
                print("ERRO")
                continue
            dados = json.loads(res_json)
            aulas = dados.get("aulas", [])
            if not aulas:
                print("sem aulas")
                continue

            resultado_completo["series"].setdefault(serie, {}).setdefault(bimestre, [])
            resultado_completo["series"][serie][bimestre].extend(aulas)
            print(f"+{len(aulas)} aula(s)")
        except Exception as e:
            print(f"erro ao processar bloco: {e}")

    return resultado_completo


def processar_arquivo(caminho_md):
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    arquivo = Path(caminho_md)
    partes = arquivo.stem.split("_")
    disciplina = partes[0] if len(partes) > 0 else "DESCONHECIDA"
    etapa = partes[1] if len(partes) > 1 else "DESCONHECIDA"

    resultado = processar_md(str(arquivo), disciplina, etapa)

    nome_saida = f"{disciplina}_{etapa}.json"
    caminho_saida = os.path.join(PASTA_SAIDA, nome_saida)
    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"  Salvo em: {caminho_saida}")


def processar_pasta():
    for arquivo in Path(PASTA_MDS).glob("*.md"):
        processar_arquivo(str(arquivo))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        processar_arquivo(sys.argv[1])
    else:
        processar_pasta()

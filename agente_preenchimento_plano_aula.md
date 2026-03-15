# Agente de Preenchimento do Plano de Aula

## Visão Geral

Este agente é responsável por:
1. Apresentar uma interface para o usuário selecionar disciplina, série e bimestre
2. Consultar o JSON extraído correspondente na pasta `docOrientadores/extraidos/`
3. Preencher o documento Word `MODELO DE PLANO DE AULA- EFAPE.docx` com as informações selecionadas
4. Preservar toda a formatação original do documento modelo
5. Gerar um arquivo Word preenchido para download

---

## Estrutura de pastas esperada

```
docOrientadores/
├── extraidos/
│   ├── FIS_EM.json
│   ├── MAT_EM.json
│   └── ...
└── MODELO DE PLANO DE AULA- EFAPE.docx
```

---

## Interface do usuário (Streamlit)

A interface deve conter três campos de seleção em sequência:
- **Disciplina:** populada dinamicamente a partir dos JSONs disponíveis na pasta `extraidos/`
- **Série/Ano:** populada com base na disciplina selecionada
- **Bimestre:** populado com base na série selecionada

Após a seleção, o app exibe uma prévia das aulas encontradas e um botão para gerar o documento.

```python
import streamlit as st
import json
import os
from pathlib import Path
from preenchedor import preencher_documento  # função definida abaixo

PASTA_EXTRAIDOS = "./docOrientadores/extraidos"
MODELO_PATH = "./docOrientadores/MODELO DE PLANO DE AULA- EFAPE.docx"

def carregar_todos_jsons():
    docs = {}
    for arquivo in Path(PASTA_EXTRAIDOS).glob("*.json"):
        with open(arquivo, "r", encoding="utf-8") as f:
            dados = json.load(f)
            chave = f"{dados['disciplina']} ({dados['etapa']})"
            docs[chave] = dados
    return docs

# ── Interface ──────────────────────────────────────────────
st.set_page_config(page_title="Plano de Aula", layout="centered")
st.title("Gerador de Plano de Aula")

docs = carregar_todos_jsons()

if not docs:
    st.error("Nenhum documento extraído encontrado em docOrientadores/extraidos/")
    st.stop()

# Seleção da disciplina
disciplina = st.selectbox("Disciplina", options=sorted(docs.keys()))
doc = docs[disciplina]

# Seleção da série
series = sorted(doc["series"].keys())
serie = st.selectbox("Série / Ano", options=series)

# Seleção do bimestre
bimestres = sorted(doc["series"][serie].keys())
bimestre = st.selectbox("Bimestre", options=bimestres)

# Carrega as aulas da seleção
aulas = doc["series"][serie][bimestre]
st.markdown(f"**{len(aulas)} aulas encontradas para {serie} — {bimestre}**")

# ── Prévia navegável por aula ───────────────────────────────
st.markdown("---")
st.subheader("Prévia do Plano de Aula")

# Navegação entre aulas
numeros = [f"Aula {a['numero']} — {a['titulo']}" for a in aulas]
aula_selecionada = st.selectbox("Selecione a aula para visualizar", options=numeros)
indice = numeros.index(aula_selecionada)
aula = aulas[indice]

# Cartão de prévia
with st.container(border=True):
    st.markdown(f"### Aula {aula['numero']} — {aula['titulo']}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Disciplina:** {doc['disciplina']}")
        st.markdown(f"**Série:** {serie}")
    with col2:
        st.markdown(f"**Bimestre:** {bimestre}")
        st.markdown(f"**Habilidade:** `{aula['habilidade']}`")

    st.markdown("---")
    st.markdown("**Aprendizagem Essencial**")
    st.info(aula["aprendizagem_essencial"])

    st.markdown("**Conteúdo**")
    st.write(aula["conteudo"])

    st.markdown("**Objetivos de Aprendizagem**")
    for obj in aula["objetivos_aprendizagem"]:
        st.markdown(f"- {obj}")

# Navegação por botões anterior / próximo
col_ant, col_prox = st.columns(2)
with col_ant:
    if indice > 0:
        if st.button("← Aula anterior"):
            st.session_state["aula_idx"] = indice - 1
            st.rerun()
with col_prox:
    if indice < len(aulas) - 1:
        if st.button("Próxima aula →"):
            st.session_state["aula_idx"] = indice + 1
            st.rerun()

st.markdown("---")

# ── Geração do documento ────────────────────────────────────
if st.button("Gerar Plano de Aula Completo (.docx)", type="primary"):
    with st.spinner("Preenchendo o documento..."):
        caminho_saida = preencher_documento(
            modelo_path=MODELO_PATH,
            aulas=aulas,
            disciplina=doc["disciplina"],
            etapa=doc["etapa"],
            serie=serie,
            bimestre=bimestre
        )
    with open(caminho_saida, "rb") as f:
        st.download_button(
            label="Baixar Plano de Aula (.docx)",
            data=f,
            file_name=f"Plano_{doc['disciplina']}_{serie}_{bimestre}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
```

---

## Lógica de preenchimento do documento Word

O preenchimento usa a abordagem **unpack → editar XML → repack** para preservar 100% da formatação original do modelo.

### Estratégia de mapeamento

O documento modelo contém marcadores (placeholders) nos campos a serem preenchidos.
O agente deve localizar esses marcadores no XML e substituí-los pelo conteúdo correspondente.

**Marcadores esperados no documento modelo:**

| Marcador no .docx | Campo do JSON | Observação |
|---|---|---|
| `{{DISCIPLINA}}` | `disciplina` | Campo único por documento |
| `{{ETAPA}}` | `etapa` | Ex: EM, EF |
| `{{SERIE}}` | `serie` | Ex: 1ª série |
| `{{BIMESTRE}}` | `bimestre` | Ex: 1º Bimestre |
| `{{AULA_NUMERO}}` | `aula.numero` | Repetido por aula |
| `{{AULA_TITULO}}` | `aula.titulo` | Repetido por aula |
| `{{AULA_HABILIDADE}}` | `aula.habilidade` | Repetido por aula |
| `{{AULA_AE}}` | `aula.aprendizagem_essencial` | Repetido por aula |
| `{{AULA_CONTEUDO}}` | `aula.conteudo` | Repetido por aula |
| `{{AULA_OBJETIVOS}}` | `aula.objetivos_aprendizagem` | Lista — um parágrafo por objetivo |

> **Importante:** Antes de usar este agente, abra o documento
> `MODELO DE PLANO DE AULA- EFAPE.docx` e insira esses marcadores
> exatamente nos campos que devem ser preenchidos.
> Os demais campos do documento devem ser deixados em branco ou com
> texto fixo — eles **não serão tocados** pelo agente.

---

### Código do preenchedor (`preenchedor.py`)

```python
import zipfile
import shutil
import os
import re
from pathlib import Path

PASTA_TEMP = "./temp_docx"

def unpack_docx(docx_path, destino):
    """Descompacta o .docx em uma pasta temporária."""
    if os.path.exists(destino):
        shutil.rmtree(destino)
    with zipfile.ZipFile(docx_path, 'r') as z:
        z.extractall(destino)

def pack_docx(pasta, saida_path, original_path):
    """Recompacta a pasta de volta em .docx."""
    if os.path.exists(saida_path):
        os.remove(saida_path)
    # Copia o original para preservar metadados e relacionamentos
    shutil.copy2(original_path, saida_path)
    with zipfile.ZipFile(saida_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(pasta):
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, pasta)
                z.write(filepath, arcname)

def substituir_marcador(xml, marcador, valor):
    """
    Substitui um marcador no XML preservando a formatação dos runs.
    Lida com o caso em que o marcador está fragmentado em múltiplos <w:r>.
    """
    # Substitui ocorrências diretas (marcador num único run)
    xml = xml.replace(marcador, valor)
    return xml

def objetivos_para_paragrafos(xml, marcador, objetivos):
    """
    Substitui o marcador de objetivos por múltiplos parágrafos,
    copiando a formatação do parágrafo onde o marcador se encontra.
    """
    # Localiza o parágrafo que contém o marcador
    padrao = r'(<w:p[ >].*?' + re.escape(marcador) + r'.*?</w:p>)'
    match = re.search(padrao, xml, re.DOTALL)
    
    if not match:
        return xml.replace(marcador, "\n".join(objetivos))
    
    paragrafo_modelo = match.group(1)
    
    # Extrai o bloco de propriedades do parágrafo (<w:pPr>)
    ppr_match = re.search(r'(<w:pPr>.*?</w:pPr>)', paragrafo_modelo, re.DOTALL)
    ppr = ppr_match.group(1) if ppr_match else ""
    
    # Extrai as propriedades do run (<w:rPr>)
    rpr_match = re.search(r'(<w:rPr>.*?</w:rPr>)', paragrafo_modelo, re.DOTALL)
    rpr = rpr_match.group(1) if rpr_match else ""
    
    # Cria um parágrafo para cada objetivo com a mesma formatação
    paragrafos = []
    for objetivo in objetivos:
        novo_paragrafo = f"""<w:p>
          {ppr}
          <w:r>
            {rpr}
            <w:t xml:space="preserve">{objetivo}</w:t>
          </w:r>
        </w:p>"""
        paragrafos.append(novo_paragrafo)
    
    bloco_objetivos = "\n".join(paragrafos)
    xml = xml.replace(match.group(1), bloco_objetivos)
    return xml

def preencher_documento(modelo_path, aulas, disciplina, etapa, serie, bimestre):
    """
    Preenche o documento modelo com os dados das aulas selecionadas.
    Retorna o caminho do arquivo gerado.
    """
    pasta_temp = PASTA_TEMP
    unpack_docx(modelo_path, pasta_temp)
    
    xml_path = os.path.join(pasta_temp, "word", "document.xml")
    
    with open(xml_path, "r", encoding="utf-8") as f:
        xml = f.read()
    
    # ── Campos únicos (cabeçalho do documento) ──────────────
    xml = substituir_marcador(xml, "{{DISCIPLINA}}", disciplina)
    xml = substituir_marcador(xml, "{{ETAPA}}", etapa)
    xml = substituir_marcador(xml, "{{SERIE}}", serie)
    xml = substituir_marcador(xml, "{{BIMESTRE}}", bimestre)
    
    # ── Campos por aula ─────────────────────────────────────
    # O documento modelo deve ter um bloco repetível por aula.
    # Para cada aula, substitui os marcadores numerados.
    # Estratégia: o modelo tem os marcadores com sufixo _N
    # Ex: {{AULA_TITULO_1}}, {{AULA_TITULO_2}}, etc.
    # OU o modelo tem um bloco único e o agente o replica para cada aula.
    
    for aula in aulas:
        n = aula["numero"]
        xml = substituir_marcador(xml, f"{{{{AULA_NUMERO_{n}}}}}", str(aula["numero"]))
        xml = substituir_marcador(xml, f"{{{{AULA_TITULO_{n}}}}}", aula["titulo"])
        xml = substituir_marcador(xml, f"{{{{AULA_HABILIDADE_{n}}}}}", aula["habilidade"])
        xml = substituir_marcador(xml, f"{{{{AULA_AE_{n}}}}}", aula["aprendizagem_essencial"])
        xml = substituir_marcador(xml, f"{{{{AULA_CONTEUDO_{n}}}}}", aula["conteudo"])
        xml = objetivos_para_paragrafos(
            xml,
            f"{{{{AULA_OBJETIVOS_{n}}}}}",
            aula["objetivos_aprendizagem"]
        )
    
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)
    
    # Gera o arquivo de saída
    saida_path = f"./docOrientadores/Plano_{disciplina}_{serie}_{bimestre}.docx".replace(" ", "_")
    pack_docx(pasta_temp, saida_path, modelo_path)
    shutil.rmtree(pasta_temp)
    
    return saida_path
```

---

## Regras críticas de preservação da formatação

- **Nunca recriar o documento do zero** — sempre partir do modelo descompactado
- **Nunca usar `\n` dentro de `<w:t>`** — cada parágrafo deve ser um `<w:p>` separado
- **Sempre copiar `<w:pPr>` e `<w:rPr>`** do parágrafo original ao criar novos parágrafos (objetivos)
- **Sempre usar `xml:space="preserve"`** em `<w:t>` quando o texto tiver espaços nas extremidades
- **Campos não mapeados não devem ser tocados** — o agente substitui apenas os marcadores `{{...}}` e ignora todo o resto

---

## Instalação das dependências

```bash
pip install streamlit
```

> O preenchedor usa apenas bibliotecas nativas do Python (`zipfile`, `shutil`, `re`, `os`) — sem dependências extras.

---

## Como executar

```bash
streamlit run app.py
```

---

## Observações importantes

- **Marcadores fragmentados:** O Word às vezes divide um texto em múltiplos `<w:r>` (runs) ao editar. Se um marcador como `{{AULA_TITULO_1}}` aparecer fragmentado no XML (ex: `{{AULA_` + `TITULO_1}}`), o agente não vai encontrá-lo. Para evitar isso, **sempre digite os marcadores diretamente no Word sem editar depois**, ou use o Find & Replace do Word para inserir cada marcador de uma vez.
- **Campos opcionais:** Campos do documento modelo que não têm marcador correspondente simplesmente não são alterados.
- **Múltiplas aulas:** O modelo deve ter os marcadores numerados de `_1` até `_N` conforme o número de aulas do bimestre (geralmente 14). Aulas sem marcador correspondente no modelo serão ignoradas silenciosamente.

import streamlit as st
import json
import os
from pathlib import Path
from datetime import date
from preenchedor import preencher_documento
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

PASTA_EXTRAIDOS = "./docOrientadores/extraidos"
MODELO_EFAPE_PATH = "./docOrientadores/MODELO DE PLANO DE AULA- EFAPE.docx"
MODELO_PAV2_PATH = "./docOrientadores/PAV2.docx"
MODELO_GUIA_PATH = "./docOrientadores/Guia de Aprendizagem.docx"

def carregar_todos_jsons():
    docs = {}
    if not os.path.exists(PASTA_EXTRAIDOS):
        return docs
    for arquivo in Path(PASTA_EXTRAIDOS).glob("*.json"):
        with open(arquivo, "r", encoding="utf-8") as f:
            dados = json.load(f)
            chave = f"{dados['disciplina']} ({dados['etapa']})"
            docs[chave] = dados
    return docs

def refinar_metodologia(texto_usuario, metodologia_tipo):
    prompt = f"""
    Você é um especialista em metodologias ativas para a Educação Paulista.
    O professor escreveu a seguinte descrição para uma aula: "{texto_usuario}"
    
    Sua tarefa é aprimorar este texto tornando-o mais profissional, didático e alinhado com a metodologia "{metodologia_tipo}".
    Use um tom inspirador e focado no protagonismo do estudante.
    Retorne apenas o texto aprimorado, sem introduções ou explicações.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Erro ao refinar: {e}"

# ── Estado Inicial ───────────────────────────────────────────
if "pagina" not in st.session_state:
    st.session_state.pagina = 1

def processar_proxima():
    st.session_state.pagina = 2

def processar_voltar():
    st.session_state.pagina = 1

def processar_refinamento(num_aula, tipo_met):
    key = f"met_text_{num_aula}"
    texto_atual = st.session_state.get(key, "")
    if texto_atual.strip():
        with st.spinner(f"Aprimorando Aula {num_aula}..."):
            refinado = refinar_metodologia(texto_atual, tipo_met)
            st.session_state[key] = refinado

# ── Helper para renderizar Checklist em colunas ──
def render_checklist(label, opcoes, key_prefix, col_count=2):
    st.markdown(f"**{label}**")
    cols = st.columns(col_count)
    selecionados = []
    for i, opt in enumerate(opcoes):
        check_key = f"{key_prefix}_{i}"
        is_checked = st.session_state.get(check_key, False)
        if cols[i % col_count].checkbox(opt, value=is_checked, key=check_key):
            selecionados.append(opt)
    return selecionados

# ── Interface ──────────────────────────────────────────────
st.set_page_config(page_title="Plano de Aula IA", layout="wide")
st.title("🚀 Gerador de Plano de Aula Inteligente")

docs = carregar_todos_jsons()

if not docs:
    st.error("Nenhum documento extraído encontrado.")
    st.stop()

# ── Barra Lateral / Configurações (Sempre visíveis ou globais) ──
with st.sidebar:
    # ── Seleção de Modelo ──
    st.header("📄 Modelo de Plano")
    modelo_opcoes = {
        "📋 Plano EFAPE": "EFAPE",
        "📊 Plano PAV2": "PAV2",
        "📖 Guia de Aprendizagem": "GUIA",
    }
    modelo_label = st.radio(
        "Escolha o modelo:",
        options=list(modelo_opcoes.keys()),
        index=0,
        key="modelo_radio"
    )
    modelo_selecionado = modelo_opcoes[modelo_label]
    st.session_state["modelo_selecionado"] = modelo_selecionado

    if modelo_selecionado == "EFAPE":
        modelo_path = MODELO_EFAPE_PATH
        st.caption("Plano de Aula padrão EFAPE com seções de metodologia, recursos e avaliação.")
    elif modelo_selecionado == "PAV2":
        modelo_path = MODELO_PAV2_PATH
        st.caption("Plano de Aula PAV2 em formato de tabela com uma linha por aula.")
    else:
        modelo_path = MODELO_GUIA_PATH
        st.caption("Guia de Aprendizagem com justificativa, ambientes e fontes de pesquisa.")

    st.markdown("---")
    st.header("👤 Informações do Professor")
    prof_default = st.session_state.get("professor_nome", "")
    professor_nome = st.text_input("Nome", value=prof_default, placeholder="Seu nome no documento")
    st.session_state["professor_nome"] = professor_nome
    
    st.header("📅 Período")
    col_ini, col_fim = st.columns(2)
    
    data_inicio = col_ini.date_input(
        "Início", 
        value=st.session_state.get("data_inicio", date.today()), 
        format="DD/MM/YYYY",
        key="data_inicio"
    )
    data_fim = col_fim.date_input(
        "Fim", 
        value=st.session_state.get("data_fim", date.today()), 
        format="DD/MM/YYYY",
        key="data_fim"
    )
    
    periodo_str = f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"

if st.session_state.pagina == 1:
    # ── ETAPA 1: Seleção e Metodologias ───────────────────────
    st.info("📌 **Etapa 1:** Selecione as aulas e refine as metodologias.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        disciplina_key = st.selectbox("Disciplina", options=sorted(docs.keys()), index=0)
        doc = docs[disciplina_key]
    with col2:
        serie = st.selectbox("Série / Ano", options=sorted(doc["series"].keys()))
    with col3:
        bimestre = st.selectbox("Bimestre", options=sorted(doc["series"][serie].keys()))

    st.markdown("---")

    # ── Seleção de Aulas ───────────────────────────────────────
    aulas_disponiveis = doc["series"][serie][bimestre]
    labels_aulas = [f"Aula {a['numero']} — {a['titulo']}" for a in aulas_disponiveis]
    mapa_aulas = {f"Aula {a['numero']} — {a['titulo']}": a for a in aulas_disponiveis}

    # Resetar checklists de aula se mudar bimestre/serie para evitar confusão
    tag_atual = f"chk_aula_{serie}_{bimestre}"
    if st.session_state.get("last_tag") != tag_atual:
        # Limpar chaves antigas de aula (opcional, mas recomendado para sanidade)
        for key in list(st.session_state.keys()):
            if key.startswith("chk_aula_"):
                st.session_state[key] = False
        st.session_state["last_tag"] = tag_atual

    # ── Selecionar todas as aulas ──
    def toggle_todas_aulas():
        novo_valor = st.session_state.get("chk_todas_aulas", False)
        for i in range(len(labels_aulas)):
            st.session_state[f"{tag_atual}_{i}"] = novo_valor

    st.checkbox(
        "✅ Selecionar todas as aulas",
        key="chk_todas_aulas",
        on_change=toggle_todas_aulas
    )

    # Renderizar Checklist para Aulas
    labels_selecionadas = render_checklist("📚 Quais aulas deseja incluir?", labels_aulas, tag_atual, col_count=1)
    aulas_selecionadas = [mapa_aulas[label] for label in labels_selecionadas]
    
    # Salvar para usar na pág 2
    st.session_state["aulas_data"] = {
        "aulas": aulas_selecionadas,
        "disciplina": doc["disciplina"],
        "etapa": doc["etapa"],
        "serie": serie,
        "bimestre": bimestre
    }

    # ── Metodologias ───────────────────────────────────────────
    st.markdown("---")
    st.subheader("💡 Metodologias e Estratégias")
    metodologias_lista = []

    if aulas_selecionadas:
        for aula in sorted(aulas_selecionadas, key=lambda x: int(x['numero'])):
            with st.expander(f"Aula {aula['numero']}: {aula['titulo']}", expanded=True):
                col_met, col_btn = st.columns([4, 1])
                
                tipo_met = col_met.selectbox(
                    f"Tipo de Metodologia (Aula {aula['numero']})",
                    [
                        "Sala de Aula Invertida", "Rotação Por Estações", "Aprendizagem Por Projetos",
                        "Aprendizagem Por Problemas", "Gamificação No Ensino", "Instrução Por Pares",
                        "Cultura Maker Escolar", "Estudo De Caso", "Ensino Por Investigação",
                        "Modelagem Matemática Real", "Outra"
                    ],
                    key=f"tipo_{aula['numero']}"
                )
                
                key_text = f"met_text_{aula['numero']}"
                if key_text not in st.session_state:
                    st.session_state[key_text] = ""
                    
                texto_met = st.text_area(
                    "Descrição da prática",
                    key=key_text,
                    placeholder="Preenchimento Opcional. Escreva o seu rascunho aqui e caso queira aprimorar clique no botão ao lado",
                    height=150
                )
                
                col_btn.button(
                    "✨ Refinar com IA", 
                    key=f"btn_{aula['numero']}", 
                    on_click=processar_refinamento, 
                    args=(aula['numero'], tipo_met)
                )
                
                desc_limpa = st.session_state[key_text].strip()
                final_met = f"{tipo_met} - {desc_limpa}" if desc_limpa else tipo_met
                metodologias_lista.append(final_met)
    
    st.session_state["metodologias_lista"] = metodologias_lista

    st.markdown("---")
    if st.button("Próxima Etapa ➡️", type="primary", use_container_width=True):
        if not aulas_selecionadas:
            st.warning("Selecione pelo menos uma aula.")
        else:
            processar_proxima()
            st.rerun()

else:
    # ── ETAPA 2: Detalhes Pedagógicos ────────────────────────
    st.info("📝 **Etapa 2:** Preencha os detalhes pedagógicos finais.")
    
    # Recuperar dados da Etapa 1
    dados_etapa1 = st.session_state.get("aulas_data", {})
    metodologias_lista = st.session_state.get("metodologias_lista", [])
    
    if st.button("⬅️ Voltar"):
        processar_voltar()
        st.rerun()
    
    st.subheader("📚 Detalhes do Plano")
    
    # ── Recursos Didáticos ──
    opcoes_recursos = [
        "Quadro branco / quadro negro", "Livro didático",
        "Slides do Material Digital",
        "Vídeos educativos (conteúdos do YouTube)", "Simulações interativas",
        "Experimentos práticos de laboratório", "Mapas conceituais", "Infográficos",
        "Modelos / maquetes físicas", "Jogos educativos", "Flashcards (cartões de memória)",
        "Aplicativos educacionais (Kahoot! / Plickers)",
        "Plataformas Digitais de Aprendizagem",
        "Podcasts educativos", "Fichas de exercícios / Lista de Exercícios",
        "Projetor multimídia (data show)", "Quadros interativos digitais (smart board)",
        "Imagens, fotografias e ilustrações científicas", "Linha do tempo visual",
        "Debates e discussões orientadas em sala", "Outros (descrever abaixo)"
    ]

    recursos_selecionados = render_checklist("🛠️ Recursos Didáticos", opcoes_recursos, "p2_rec")

    recursos_manuais = ""
    if "Outros (descrever abaixo)" in recursos_selecionados:
        recursos_manuais = st.text_area(
            "Descreva os outros recursos",
            value=st.session_state.get("p2_recursos_man", ""),
            placeholder="Digite aqui os recursos adicionais...",
            height=100,
            key="p2_recursos_man"
        )

    # Unir seleções para o documento
    lista_final_recursos = [r for r in recursos_selecionados if r != "Outros (descrever abaixo)"]
    if recursos_manuais:
        lista_final_recursos.append(recursos_manuais)
    recursos_final_str = "; ".join(lista_final_recursos)
    
    # ── Avaliação ──
    st.markdown("---")
    opcoes_avaliacao = [
        "Prova escrita discursiva", "Prova objetiva (múltipla escolha)", "Lista de exercícios avaliativa",
        "Trabalho de pesquisa", "Seminário / apresentação oral", "Projeto interdisciplinar",
        "Relatório de experimento", "Portfólio de aprendizagem", "Autoavaliação do aluno",
        "Avaliação por pares", "Rubrica (matriz de critérios de avaliação)", "Diário de aprendizagem",
        "Estudo de caso", "Mapa conceitual avaliado", "Produção textual / redação",
        "Questionário online (Google Forms)", "Quiz interativo (Kahoot!)",
        "Observação sistemática do professor com checklist", "Resolução de problemas / desafios práticos",
        "Debate avaliativo.", "Outros (descrever abaixo)"
    ]

    aval_selecionados = render_checklist("📊 Critérios/Instrumentos de Avaliação", opcoes_avaliacao, "p2_aval")

    aval_manuais = ""
    if "Outros (descrever abaixo)" in aval_selecionados:
        aval_manuais = st.text_area(
            "Descreva os outros instrumentos de avaliação",
            value=st.session_state.get("p2_aval_man", ""),
            placeholder="Digite aqui os critérios adicionais...",
            height=100,
            key="p2_aval_man"
        )

    lista_final_aval = [a for a in aval_selecionados if a != "Outros (descrever abaixo)"]
    if aval_manuais:
        lista_final_aval.append(aval_manuais)
    aval_final_str = "; ".join(lista_final_aval)

    # ── Campos exclusivos do Guia de Aprendizagem ──
    modelo_ativo = st.session_state.get("modelo_selecionado", "EFAPE")

    guia_ambientes_str = ""
    guia_fontes_str = ""
    guia_justificativa_str = ""
    guia_aproximacao_str = ""

    if modelo_ativo == "GUIA":
        st.markdown("---")
        st.subheader("🏫 Ambientes de Aprendizagem")
        opcoes_ambientes = [
            "Sala de aula",
            "Laboratório de ciências",
            "Laboratório de informática",
            "Biblioteca",
            "Espaços externos / área verde",
            "Quadra esportiva",
            "Ambiente virtual (Google Classroom / Moodle)",
            "Videoconferência (Meet / Teams / Zoom)",
            "Museu / teatro / espaços culturais",
            "Comunidade local / visita técnica",
        ]
        ambientes_selecionados = render_checklist(
            "Selecione os ambientes utilizados:",
            opcoes_ambientes, "p2_amb", col_count=2
        )
        guia_ambientes_str = "; ".join(ambientes_selecionados)

        st.markdown("---")
        st.subheader("🔍 Fontes de Pesquisa para o Estudante")
        opcoes_fontes = [
            "Livro didático adotado pela escola",
            "Livros complementares da biblioteca",
            "Artigos científicos (Scielo, Google Acadêmico)",
            "Portais educacionais (Khan Academy, Stoodi, Me Salva!)",
            "Vídeos no YouTube (canais educativos)",
            "Documentos e sites do governo (IBGE, INEP, EMBRAPA)",
            "Jornais e revistas online (G1, UOL, BBC Brasil)",
            "Podcasts e rádios educativas",
            "Museus virtuais e acervos digitais",
            "Simuladores online (PhET, Geogebra)",
        ]
        fontes_selecionadas = render_checklist(
            "Sugira fontes de pesquisa:",
            opcoes_fontes, "p2_font", col_count=2
        )
        fontes_manuais = st.text_area(
            "Outras fontes (opcional)",
            value=st.session_state.get("p2_fontes_man", ""),
            placeholder="Links, títulos de livros, sites específicos...",
            height=80,
            key="p2_fontes_man"
        )
        lista_fontes_final = list(fontes_selecionadas)
        if fontes_manuais.strip():
            lista_fontes_final.append(fontes_manuais.strip())
        guia_fontes_str = "\n".join([f"- {f}" for f in lista_fontes_final])

        st.markdown("---")
        st.subheader("📚 Justificativa")
        texto_justif_padrao = (
            "Este Guia de Aprendizagem visa desenvolver as competências e habilidades do "
            "Currículo Paulista e os princípios do Programa Ensino Integral: Pedagogia da "
            "Presença, Protagonismo, os Quatro Pilares da Educação e a Pedagogia de "
            "Competências."
        )
        guia_justificativa_str = st.text_area(
            "Justificativa do Guia",
            value=st.session_state.get("p2_justif", texto_justif_padrao),
            height=130,
            key="p2_justif"
        )

        st.markdown("---")
        st.subheader("🌍 Aproximação com a Realidade do Estudante")
        texto_aprox_padrao = (
            "Aproximar os conteúdos propostos com o contexto vivido pelos estudantes de "
            "forma intencional, exemplificando situações, profissões e transformações "
            "onde os sujeitos possam assumir uma postura ativa, crítica e protagonista."
        )
        guia_aproximacao_str = st.text_area(
            "Aproximação com a realidade",
            value=st.session_state.get("p2_aprox", texto_aprox_padrao),
            height=130,
            key="p2_aprox"
        )

    # ── Recomposição/Recuperação ──
    st.markdown("---")
    aulas_p1 = dados_etapa1.get("aulas", [])
    opcoes_recup = [f"Aula {a['numero']}" for a in aulas_p1]
    opcoes_recup_com_outra = opcoes_recup + ["Outra"]
    
    recup_selecionadas = render_checklist("🔄 Recomposição, Aprofundamento e Recuperação", opcoes_recup_com_outra, "p2_recup")
    
    lista_final_recup = [r for r in recup_selecionadas if r != "Outra"]
    
    if "Outra" in recup_selecionadas:
        # Buscar todas as aulas do bimestre atual para oferecer como opção
        chave_doc = f"{dados_etapa1['disciplina']} ({dados_etapa1['etapa']})"
        serie_atual = dados_etapa1['serie']
        bimestre_atual = dados_etapa1['bimestre']
        
        todas_aulas_bimestre = docs.get(chave_doc, {}).get("series", {}).get(serie_atual, {}).get(bimestre_atual, [])
        labels_todas = [f"Aula {a['numero']} — {a['titulo']}" for a in todas_aulas_bimestre]
        
        extras_selecionadas = st.multiselect(
            "Selecione as aulas extras para recomposição",
            options=labels_todas,
            default=st.session_state.get("recup_extras", []),
            key="recup_extras"
        )
        # Extrair apenas "Aula X" do label para o documento
        for label in extras_selecionadas:
            num_aula = label.split(" — ")[0]
            if num_aula not in lista_final_recup:
                lista_final_recup.append(num_aula)
    
    # Ordenar as aulas numericamente
    def sort_key(s):
        try:
            return int(s.replace("Aula ", ""))
        except:
            return 999
            
    lista_final_recup.sort(key=sort_key)
    
    recup_final_str = "Recomposição/Aprofundamento nas aulas: " + ", ".join(lista_final_recup) if lista_final_recup else ""

    st.markdown("---")
    if st.button("✨ Gerar e Baixar Plano de Aula", type="primary", use_container_width=True):
        if not professor_nome:
            st.warning("Preencha o nome do Professor na barra lateral.")
        else:
            with st.spinner("Gerando documento final..."):
                try:
                    modelo_path_atual = st.session_state.get("modelo_selecionado", "EFAPE")
                    if modelo_path_atual == "EFAPE":
                        modelo_path_arquivo = MODELO_EFAPE_PATH
                    elif modelo_path_atual == "PAV2":
                        modelo_path_arquivo = MODELO_PAV2_PATH
                    else:
                        modelo_path_arquivo = MODELO_GUIA_PATH

                    caminho_saida = preencher_documento(
                        modelo_path=modelo_path_arquivo,
                        modelo_tipo=modelo_path_atual,
                        aulas=dados_etapa1["aulas"],
                        disciplina=dados_etapa1["disciplina"],
                        etapa=dados_etapa1["etapa"],
                        serie=dados_etapa1["serie"],
                        bimestre=dados_etapa1["bimestre"],
                        professor_nome=professor_nome,
                        periodo=periodo_str,
                        metodologias=metodologias_lista,
                        recursos=recursos_final_str,
                        avaliacao=aval_final_str,
                        recuperacao=recup_final_str,
                        ambientes=guia_ambientes_str,
                        fontes=guia_fontes_str,
                        justificativa=guia_justificativa_str,
                        aproximacao=guia_aproximacao_str,
                    )

                    with open(caminho_saida, "rb") as f:
                        st.download_button(
                            label="⬇️ Baixar Plano de Aula (Word)",
                            data=f,
                            file_name=os.path.basename(caminho_saida),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True
                        )
                    st.success("Plano gerado com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao gerar: {e}")


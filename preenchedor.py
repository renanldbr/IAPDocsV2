import os
import re
from docx import Document

def preencher_documento(modelo_path, aulas, disciplina, etapa, serie, bimestre, professor_nome, periodo, metodologias, recursos, avaliacao, recuperacao):
    """
    Preenche o documento Word agregando múltiplas aulas com formatações específicas.
    """
    doc = Document(modelo_path)
    
    mapeamento_disciplinas = {
        "FIS": "Física",
        "MAT": "Matemática",
        "BIO": "Biologia",
        "QUI": "Química",
        "CIE": "Ciências",
        "GEO": "Geografia",
        "HIS": "História",
        "LPT": "Língua Portuguesa",
        "ING": "Inglês",
        "ART": "Arte",
        "EFI": "Educação Física"
    }
    disciplina_completa = mapeamento_disciplinas.get(disciplina.upper(), disciplina)
    
    aulas_ordenadas = sorted(aulas, key=lambda x: int(x['numero']))
    
    t1 = doc.tables[1]
    
    def append_to_cell(cell, label, value):
        if label.lower() in cell.text.lower():
            if cell.paragraphs:
                p = cell.paragraphs[0]
                run = p.add_run(f" {value}")
                run.bold = True
    
    append_to_cell(t1.cell(1, 0), "Professor(a):", professor_nome)
    append_to_cell(t1.cell(1, 1), "Ano/Série:", serie)
    append_to_cell(t1.cell(2, 0), "Componente Curricular:", disciplina_completa)
    t1.cell(2, 1).text = f"{bimestre}"
    
    for row in t1.rows:
        for cell in row.cells:
            if "período" in cell.text.lower():
                append_to_cell(cell, "Período de realização:", periodo)

    titulos = []
    conteudos_formatados = []
    objetivos_formatados = []
    mets_formatadas = []
    
    ae_unicos = []
    habilidades_unicas = []
    re_ae_prefix = re.compile(r"^(AE|EA|AI)\d+\s*[-:]\s*", re.IGNORECASE)

    for i, aula in enumerate(aulas_ordenadas):
        prefix = f"Aula {aula['numero']}: "
        
        def limpar_texto(t):
            if not t: return ""
            # Lista exaustiva de marcadores: bullets, círculos, quadrados, traços, etc.
            bullets = r"[•●·▪\-*○◦⦿•‣⁃■□◊►▼]"
            # Remove no início da string ou após quebras de linha
            t = re.sub(f"^{bullets}\\s*", "", t.strip())
            t = re.sub(f"\n{bullets}\\s*", "\n", t)
            # Remove qualquer marcador solto no meio do texto que possa ter vindo da extração
            t = re.sub(f"\\s+{bullets}\\s+", " ", t)
            return " ".join(t.split()).strip()

        # Títulos
        titulo_limpo = limpar_texto(aula['titulo'])
        titulos.append(f"{prefix}{titulo_limpo}")
        
        # Conteúdos
        cont_limpo = limpar_texto(aula['conteudo']).replace("\n", "; ")
        conteudos_formatados.append(f"{prefix}{cont_limpo}")
        
        # Objetivos
        objs_limpos = "; ".join([limpar_texto(obj) for obj in aula['objetivos_aprendizagem']])
        objetivos_formatados.append(f"{prefix}{objs_limpos}")
        
        # Metodologias (Mapeadas pelo index da lista de selecionadas)
        met_texto = metodologias[i] if i < len(metodologias) else ""
        mets_formatadas.append(f"{prefix}{met_texto}")
        
        ae_raw = aula['aprendizagem_essencial'].strip()
        ae_clean = re_ae_prefix.sub("", ae_raw).strip()
        ae_norm = " ".join(ae_clean.strip(" .").split()).lower()
        if not any(" ".join(x.strip(" .").split()).lower() == ae_norm for x in ae_unicos):
            ae_unicos.append(ae_clean)
        hab = aula['habilidade'].strip()
        if not any(" ".join(x.strip(" .").split()).lower() == " ".join(hab.strip(" .").split()).lower() for x in habilidades_unicas):
            habilidades_unicas.append(hab)

    ae_formatado = [f"AE{idx+1}: {ae_val}" for idx, ae_val in enumerate(ae_unicos)]
    t2 = doc.tables[2]
    t2.cell(1, 0).text = "\n".join(titulos)
    t2.cell(3, 0).text = "\n".join(ae_formatado)
    t2.cell(5, 0).text = "\n".join(habilidades_unicas)
    t2.cell(7, 0).text = "\n".join(conteudos_formatados)
    t2.cell(9, 0).text = "\n".join(objetivos_formatados)
    
    # Metodologias na linha 11
    if len(t2.rows) > 11:
        t2.cell(11, 0).text = "\n".join(mets_formatadas)
    
    # Recursos Didáticos na linha 13
    if len(t2.rows) > 13:
        t2.cell(13, 0).text = recursos
        
    # Critérios de Avaliação na linha 15
    if len(t2.rows) > 15:
        t2.cell(15, 0).text = avaliacao
        
    # Recuperação na linha 19
    if len(t2.rows) > 19:
        t2.cell(19, 0).text = recuperacao

    safe_disciplina = disciplina_completa.replace("/", "-").replace(" ", "_")
    saida_path = f"./docOrientadores/Saida/Plano_{safe_disciplina}_{serie}_{bimestre}.docx"
    os.makedirs("./docOrientadores/Saida", exist_ok=True)
    doc.save(saida_path)
    return saida_path

import json
import os
from pathlib import Path
import re

PASTA_EXTRAIDOS = "./docOrientadores/extraidos"

def normalizar_geral(texto):
    if not texto:
        return ""
    # Padroniza símbolos de grau
    texto = texto.replace("°", "º")
    # Limpeza de caracteres não desejados (preserva letras, números, espaços, º e ª)
    texto = re.sub(r"[^a-zA-Z0-9\sºª]", " ", texto)
    # Remove espaços duplos e nas pontas
    return " ".join(texto.split()).strip()

def normalizar_serie(nome, etapa):
    limpo = normalizar_geral(nome)
    
    # Extrai o número (ex: "6", "1")
    numero_match = re.search(r"(\d+)", limpo)
    if not numero_match:
        return limpo.title()
    
    numero = numero_match.group(1)
    
    if etapa.upper() == "EM" or "série" in nome.lower() or "serie" in nome.lower():
        return f"{numero}ª Série"
    else:
        # Padrão para Fundamental (AF)
        return f"{numero}º Ano"

def normalizar_bimestre(nome):
    limpo = normalizar_geral(nome)
    numero_match = re.search(r"(\d+)", limpo)
    if not numero_match:
        return limpo.title()
    
    numero = numero_match.group(1)
    return f"{numero}º Bimestre"

def calcular_score_aula(aula):
    score = 0
    titulo = str(aula.get("titulo", "")).lower()
    genericos = ["unidade temática", "grupo", "problemas envolvendo", "matéria e energia", "vida, terra e cosmos"]
    for g in genericos:
        if g in titulo:
            score -= 100
    objs = aula.get("objetivos_aprendizagem", [])
    if objs:
        score += len(objs) * 10
    score += len(titulo)
    if len(str(aula.get("conteudo", ""))) > 20:
        score += 20
    if re.match(r"^[\d\s,]+$", titulo):
        score -= 500
    return score

def limpar_json(caminho):
    print(f"Limpando com normalização robusta: {caminho}")
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)
    
    etapa = dados.get("etapa", "EM")
    novas_series = {}
    series_original = dados.get("series", {})
    
    for nome_original, bimestres in series_original.items():
        nome_limpo = normalizar_serie(nome_original, etapa)
        if nome_limpo not in novas_series:
            novas_series[nome_limpo] = {}
            
        for bimestre_original, aulas in bimestres.items():
            b_limpo = normalizar_bimestre(bimestre_original)
            
            if b_limpo not in novas_series[nome_limpo]:
                novas_series[nome_limpo][b_limpo] = {}
            
            for aula in aulas:
                num = str(aula.get("numero", "0"))
                try:
                    num_int = int(re.search(r"(\d+)", num).group(1))
                except:
                    continue
                
                score_atual = calcular_score_aula(aula)
                
                if num_int not in novas_series[nome_limpo][b_limpo]:
                    novas_series[nome_limpo][b_limpo][num_int] = aula
                else:
                    score_existente = calcular_score_aula(novas_series[nome_limpo][b_limpo][num_int])
                    if score_atual > score_existente:
                        novas_series[nome_limpo][b_limpo][num_int] = aula
                        
    # Converter de volta para listas ordenadas
    final_series = {}
    for s_nome, b_dict in novas_series.items():
        final_series[s_nome] = {}
        # Ordenar bimestres por número
        for b_nome in sorted(b_dict.keys(), key=lambda x: int(re.search(r"(\d+)", x).group(1))):
            a_dict = b_dict[b_nome]
            lista_aulas = []
            for n in sorted(a_dict.keys()):
                aula = a_dict[n]
                if calcular_score_aula(aula) > -300:
                    lista_aulas.append(aula)
            if lista_aulas:
                final_series[s_nome][b_nome] = lista_aulas
                
    dados["series"] = final_series
    
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    for arquivo in Path(PASTA_EXTRAIDOS).glob("*.json"):
        limpar_json(arquivo)
    print("Normalização robusta concluída!")

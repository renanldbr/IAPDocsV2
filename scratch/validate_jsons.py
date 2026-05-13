import json
import os
from pathlib import Path

PASTA_EXTRAIDOS = "./docOrientadores/extraidos"
REQUIRED_KEYS = ["numero", "titulo", "aprendizagem_essencial", "habilidade", "conteudo", "objetivos_aprendizagem"]

def validate_jsons():
    for arquivo in Path(PASTA_EXTRAIDOS).glob("*.json"):
        with open(arquivo, "r", encoding="utf-8") as f:
            try:
                dados = json.load(f)
                for serie, bimestres in dados.get("series", {}).items():
                    for bimestre, aulas in bimestres.items():
                        for aula in aulas:
                            for key in REQUIRED_KEYS:
                                if key not in aula:
                                    print(f"MISSING KEY '{key}' in {arquivo.name} -> {serie} -> {bimestre} -> Aula {aula.get('numero', '?')}")
            except Exception as e:
                print(f"Error loading {arquivo.name}: {e}")

if __name__ == "__main__":
    validate_jsons()

#!/usr/bin/env python3
"""
Fase 7 — Demo en Gradio del RAG con metadatos.

Pregunta en lenguaje natural + filtros de carpeta / área / etiqueta / fecha.
Lanza:  python app.py    →    http://127.0.0.1:7860
"""
from __future__ import annotations
import csv
import importlib.util
from pathlib import Path

import gradio as gr

ROOT = Path(__file__).resolve().parent

# Carga la lógica RAG de src/03_rag.py (nombre con prefijo numérico → import por ruta)
_spec = importlib.util.spec_from_file_location("rag3", ROOT / "src" / "03_rag.py")
rag3 = importlib.util.module_from_spec(_spec)
import sys
sys.path.insert(0, str(ROOT / "src"))   # para que rag3 encuentre rag_core
_spec.loader.exec_module(rag3)

# Opciones de los desplegables a partir de metadata.csv
with open(ROOT / "data" / "metadata.csv", encoding="utf-8") as f:
    META = list(csv.DictReader(f))
CARPETAS = ["(todas)"] + sorted({r["carpeta"] for r in META})
AREAS = ["(todas)"] + sorted({r["area"] for r in META})
TAGS = ["(todas)"] + sorted({t for r in META for t in r["etiquetas"].split(";")})


def responder(pregunta, carpeta, area, etiqueta, k):
    if not pregunta.strip():
        yield "Escribe una pregunta.", ""
        return
    # Feedback inmediato para que no parezca que está colgado.
    yield "⏳ Buscando en las transcripciones y generando con el modelo local… (unos segundos)", ""
    filtros = {}
    if carpeta and carpeta != "(todas)": filtros["carpeta"] = carpeta
    if area and area != "(todas)": filtros["area"] = area
    if etiqueta and etiqueta != "(todas)": filtros["etiqueta"] = etiqueta
    texto, hits = rag3.answer(pregunta, k=int(k), **filtros)
    fuentes = "\n".join(
        f"- **{d.metadata['carpeta']}** ({d.metadata['fecha']}) · score {s:.2f} — "
        f"_{' '.join(d.page_content.split())[:140]}…_"
        for d, s in hits
    ) or "_(sin fuentes)_"
    yield texto, fuentes


with gr.Blocks(title="RAG sobre las clases (con metadatos)") as demo:
    gr.Markdown("# 🔎 Buscador RAG sobre las transcripciones del módulo LLM\n"
                "Pregunta en lenguaje natural y, si quieres, **acota por carpeta, área, etiqueta o fecha**.")
    with gr.Row():
        pregunta = gr.Textbox(label="Pregunta", placeholder="¿Qué es el chunking y por qué se usa overlap?", scale=4)
        k = gr.Slider(2, 10, value=5, step=1, label="k (nº de fragmentos)", scale=1)
    with gr.Row():
        carpeta = gr.Dropdown(CARPETAS, value="(todas)", label="Carpeta (clase)")
        area = gr.Dropdown(AREAS, value="(todas)", label="Área")
        etiqueta = gr.Dropdown(TAGS, value="(todas)", label="Etiqueta (tema)")
    btn = gr.Button("Preguntar", variant="primary")
    respuesta = gr.Markdown(label="Respuesta")
    gr.Markdown("### 📎 Fuentes")
    fuentes = gr.Markdown()
    btn.click(responder, [pregunta, carpeta, area, etiqueta, k], [respuesta, fuentes])
    pregunta.submit(responder, [pregunta, carpeta, area, etiqueta, k], [respuesta, fuentes])


if __name__ == "__main__":
    # Precalienta embeddings + LLM para que la PRIMERA pregunta no tarde 30-60 s.
    print("Calentando modelos (embeddings + LLM local)… puede tardar ~30 s la primera vez.")
    try:
        rag3.answer("hola", k=1)
        print("✅ Modelos listos.")
    except Exception as e:
        print(f"⚠️  Aviso al calentar (¿Ollama abierto?): {e}")
    demo.launch()

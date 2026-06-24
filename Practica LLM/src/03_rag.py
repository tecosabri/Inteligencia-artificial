#!/usr/bin/env python3
"""
Fase 5 — RAG end-to-end: recupera (con o sin metadatos) y genera una respuesta
con un LLM local (Ollama), citando las clases y SIN inventar.

Ejemplos:
    python src/03_rag.py "¿qué diferencia hay entre LoRA y QLoRA?"
    python src/03_rag.py "¿qué es un guardrail?" --etiqueta safety
    python src/03_rag.py "¿qué se vio de evaluación?" --carpeta "Clase 6"
"""
from __future__ import annotations
import argparse
from rag_core import retrieve, get_llm, format_citation

SYSTEM = (
    "Eres un asistente que responde preguntas sobre las clases de un curso de "
    "LLMs a partir del CONTEXTO. El contexto son transcripciones de clases "
    "habladas: lenguaje informal, coloquial y con posibles erratas. Interpreta "
    "y reconstruye la explicación a partir de él. Reglas:\n"
    "- Apóyate en el contexto y explícalo con tus palabras, claro y conciso.\n"
    "- Solo si el contexto realmente NO trata el tema, responde: \"No lo "
    "encuentro en las transcripciones.\" No inventes datos que no aparezcan.\n"
    "- Responde en español.\n"
    "- Cita entre paréntesis la clase de la que sale la información (p. ej. (Clase 4))."
)


def build_prompt(query: str, hits) -> str:
    context = "\n\n---\n\n".join(
        f"[{format_citation(d)}]\n{' '.join(d.page_content.split())}" for d, _ in hits
    )
    return (
        f"{SYSTEM}\n\n=== CONTEXTO ===\n{context}\n\n=== PREGUNTA ===\n{query}\n\n=== RESPUESTA ==="
    )


def answer(query: str, k: int = 5, **filters):
    hits = retrieve(query, k=k, **filters)
    if not hits:
        return "No lo encuentro en las transcripciones (con esos filtros).", []
    llm = get_llm(temperature=0.0)
    resp = llm.invoke(build_prompt(query, hits))
    text = resp.content if hasattr(resp, "content") else str(resp)
    return text, hits


def to_ord(f):
    return int(f.replace("-", "")) if f else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--carpeta")
    ap.add_argument("--area")
    ap.add_argument("--etiqueta")
    ap.add_argument("--desde")
    ap.add_argument("--hasta")
    args = ap.parse_args()

    text, hits = answer(
        args.query, k=args.k,
        carpeta=args.carpeta, area=args.area, etiqueta=args.etiqueta,
        desde=to_ord(args.desde), hasta=to_ord(args.hasta),
    )
    print("\n🧠 RESPUESTA\n" + "-" * 60)
    print(text)
    print("\n📎 FUENTES\n" + "-" * 60)
    for d, score in hits:
        print(f"  [{score:.3f}] {format_citation(d)}")


if __name__ == "__main__":
    main()

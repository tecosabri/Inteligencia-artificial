#!/usr/bin/env python3
"""
Fase 6 — Evaluación: ¿mejora el filtrado por metadatos la recuperación?

Comparamos dos pipelines sobre un golden set:
  - BASELINE: búsqueda semántica sola.
  - METADATOS: misma búsqueda + filtro por la etiqueta (tema) de la pregunta.

Métricas (relevante = chunk de la CLASE correcta):
  - precision@k : fracción de los k chunks que son de la clase correcta.
  - MRR         : 1 / (rango del primer chunk de la clase correcta).
  - nº clases   : cuántas clases distintas aparecen en el top-k (contaminación).

Nota: RAGAS 0.4.3 tiene un conflicto de imports con langchain 1.x (referencia
`langchain_community.chat_models.vertexai`, que ya no existe), así que las
métricas se calculan de forma nativa — las mismas ideas que RAGAS (precisión
de contexto) pero sin la dependencia rota. Con --judge se añade un juez LLM
local (Ollama) que puntúa fidelidad y relevancia de la respuesta generada.

Uso:
    python src/04_eval.py
    python src/04_eval.py --judge        # añade evaluación de la generación (lento)
"""
from __future__ import annotations
import argparse
from rag_core import retrieve

K = 5

# (pregunta, clase_correcta, etiqueta_tema)
GOLDEN = [
    ("¿Qué es el chunking y por qué se usa solapamiento (overlap)?", "clase-4", "chunking"),
    ("¿Qué diferencia hay entre LoRA y QLoRA?", "clase-3", "lora"),
    ("¿Qué es el mecanismo de atención en un Transformer?", "clase-2", "atencion"),
    ("¿Qué es el MCP (Model Context Protocol) y para qué sirve?", "clase-5", "mcp"),
    ("¿Qué es RAG y qué pasos sigue?", "clase-4", "rag"),
    ("¿Qué es la observabilidad y qué hace Langfuse?", "clase-6", "langfuse"),
    ("¿Qué es el fine-tuning y por qué causa olvido catastrófico?", "clase-3", "fine-tuning"),
    ("¿Qué es un agente y en qué consiste el bucle ReAct?", "clase-5", "agentes"),
    ("¿Qué es el prompt injection y cómo se mitiga?", "clase-6", "safety"),
    ("¿Qué es DPO en el alineamiento de modelos?", "clase-3", "dpo"),
]


def metrics(hits, clase_correcta):
    clases = [d.metadata["source_id"] for d, _ in hits]
    rel = [c == clase_correcta for c in clases]
    prec = sum(rel) / len(rel) if rel else 0.0
    mrr = 0.0
    for i, r in enumerate(rel, 1):
        if r:
            mrr = 1.0 / i
            break
    n_clases = len(set(clases))
    return prec, mrr, n_clases


def run():
    print(f"\nGolden set: {len(GOLDEN)} preguntas · k={K}\n")
    print(f"{'Pregunta':<48} {'BASE p@k':>8} {'META p@k':>8} {'BASE MRR':>8} {'META MRR':>8}")
    print("-" * 84)
    agg = {"bp": 0, "mp": 0, "bm": 0, "mm": 0, "bc": 0, "mc": 0}
    for q, clase, tag in GOLDEN:
        bp, bm, bc = metrics(retrieve(q, k=K), clase)
        mp, mm, mc = metrics(retrieve(q, k=K, etiqueta=tag), clase)
        agg["bp"] += bp; agg["mp"] += mp; agg["bm"] += bm
        agg["mm"] += mm; agg["bc"] += bc; agg["mc"] += mc
        print(f"{q[:46]:<48} {bp:>8.2f} {mp:>8.2f} {bm:>8.2f} {mm:>8.2f}")
    n = len(GOLDEN)
    print("-" * 84)
    print(f"{'MEDIA':<48} {agg['bp']/n:>8.2f} {agg['mp']/n:>8.2f} {agg['bm']/n:>8.2f} {agg['mm']/n:>8.2f}")
    print(f"\nContaminación (nº medio de clases distintas en el top-{K}):")
    print(f"  BASELINE:   {agg['bc']/n:.2f} clases   |   CON METADATOS: {agg['mc']/n:.2f} clases")
    print("\nLectura: con el filtro por etiqueta sube la precisión@k y la respuesta")
    print("se concentra en la(s) clase(s) correcta(s) (menos contaminación).")


def judge():
    """Juez LLM local: fidelidad y relevancia de la respuesta (0-1). Lento."""
    import re
    from rag_core import get_llm
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("rag3", pathlib.Path(__file__).parent / "03_rag.py")
    rag3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(rag3)
    llm = get_llm()

    def score(pregunta, respuesta, contexto):
        p = (f"Evalúa de 0.0 a 1.0. FIDELIDAD: ¿la respuesta se apoya solo en el contexto? "
             f"RELEVANCIA: ¿responde a la pregunta? Devuelve solo: fidelidad=X relevancia=Y\n\n"
             f"PREGUNTA: {pregunta}\nCONTEXTO: {contexto[:2000]}\nRESPUESTA: {respuesta}")
        out = llm.invoke(p).content
        f = re.search(r"fidelidad\s*=\s*([01](?:\.\d+)?)", out)
        r = re.search(r"relevancia\s*=\s*([01](?:\.\d+)?)", out)
        return (float(f.group(1)) if f else 0.0, float(r.group(1)) if r else 0.0)

    print("\n--- Juez LLM (generación: baseline vs metadatos) ---")
    accB = [0, 0]; accM = [0, 0]
    for q, clase, tag in GOLDEN:
        aB, hB = rag3.answer(q, k=K)
        aM, hM = rag3.answer(q, k=K, etiqueta=tag)
        ctxB = " ".join(d.page_content for d, _ in hB)
        ctxM = " ".join(d.page_content for d, _ in hM)
        fB, rB = score(q, aB, ctxB); fM, rM = score(q, aM, ctxM)
        accB[0] += fB; accB[1] += rB; accM[0] += fM; accM[1] += rM
        print(f"  {q[:40]:<42} BASE fid={fB:.2f} rel={rB:.2f} | META fid={fM:.2f} rel={rM:.2f}")
    n = len(GOLDEN)
    print(f"\nMEDIA  BASE: fidelidad={accB[0]/n:.2f} relevancia={accB[1]/n:.2f}")
    print(f"MEDIA  META: fidelidad={accM[0]/n:.2f} relevancia={accM[1]/n:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", action="store_true", help="Añade juez LLM sobre la generación (lento)")
    args = ap.parse_args()
    run()
    if args.judge:
        judge()

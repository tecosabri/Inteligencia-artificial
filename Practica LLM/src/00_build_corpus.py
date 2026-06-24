#!/usr/bin/env python3
"""Fase 1 — Prepara el corpus de la práctica RAG a partir de las 6
transcripciones del módulo LLM. Limpia los marcadores de timestamp/AUDIO,
escribe data/clase-N.txt y data/metadata.csv."""
import os, re, csv

PROJ = "/Users/isma/Desktop/practica-final-rag"
SRC = "/Users/isma/Desktop/Bootcamp IA/LLM"
DATA = os.path.join(PROJ, "data")
os.makedirs(DATA, exist_ok=True)

# Por clase: (fichero_fuente, slug, titulo, area, carpeta, fecha, etiquetas)
CLASES = [
    ("clase 1/Clase 1_transcripcion_v3.txt", "clase-1",
     "Ingeniería con Agentes de Código: Claude Code, SDD, Skills y Hooks",
     "Fundamentos", "Clase 1", "2026-06-16",
     ["agentes-codigo","claude-code","sdd","skills","subagentes","hooks","observabilidad"]),
    ("clase 2/Clase 2_transcripcion_v3.txt", "clase-2",
     "Fundamentos de LLMs: Transformers, Pretraining y Prompt Engineering",
     "Fundamentos", "Clase 2", "2026-06-17",
     ["tokens","embeddings","atencion","transformer","pretraining","prompt-engineering","dspy","mixture-of-experts","reasoning"]),
    ("clase 3/Clase 3_transcripcion.txt", "clase-3",
     "LLMOps, Fine-tuning, Alignment y Evaluación",
     "Construcción", "Clase 3", "2026-06-18",
     ["fine-tuning","lora","qlora","distillation","alignment","rlhf","dpo","grpo","evaluacion","multimodal"]),
    ("clase 4/Clase 4_transcripcion_v3.txt", "clase-4",
     "Frameworks, Embeddings, Vector Stores y RAG",
     "Construcción", "Clase 4", "2026-06-19",
     ["embeddings","vector-store","rag","chunking","retrieval","reranking","knowledge-graph","ragas","guardrails","evaluacion"]),
    ("clase 5/Clase 5_transcripcion.txt", "clase-5",
     "Agentes: LangChain, LangGraph, MCP, ADK, A2A y n8n",
     "Producción", "Clase 5", "2026-06-22",
     ["agentes","react","langchain","langgraph","mcp","adk","a2a","n8n","harness","rag"]),
    ("clase 6/Clase 6_transcripcion_v3.txt", "clase-6",
     "Producción: Observabilidad, Evaluación, Safety, Coste y Despliegue",
     "Producción", "Clase 6", "2026-06-23",
     ["observabilidad","langfuse","evaluacion","safety","red-team","coste","latencia","multimodal","deploy"]),
]
PROFESOR = "Erick Risco"
IDIOMA = "es"  # español con tecnicismos en inglés

AUDIO_RE = re.compile(r".*?AUDIO:\s*", re.DOTALL)
NOISE_RE = re.compile(r"^(?:y\s*)+$", re.IGNORECASE)  # filler "y y y"

# Correcciones de errores del ASR en términos técnicos (preprocesado: GIGO).
# Se aplican con límites de palabra; el orden importa (QLoRA antes que LoRA).
CORRECTIONS = [
    (r"\bracks\b", "RAGs"),
    (r"\brack\b", "RAG"),
    (r"\bwar\s?rail(?:es|s)?\b", "guardrails"),
    (r"\b(?:grad|guard)rack\b", "guardrail"),
    (r"\bráguilas?\b", "RAGAS"),
    (r"\bragas\b", "RAGAS"),
    (r"\bqlora\b", "QLoRA"),
    (r"\b[ckq]u?\s?lora\b", "QLoRA"),     # "cu lora", "q lora"
    (r"\bloras\b", "LoRAs"),
    (r"\blora\b", "LoRA"),
    (r"\bhagenpha[cs]e\b", "Hugging Face"),
    (r"\bhagenface\b", "Hugging Face"),
    (r"\bhuggin?gface\b", "Hugging Face"),
    (r"\bjaginface\b", "Hugging Face"),
    (r"\blanfi(?:os|us|o)\b", "Langfuse"),
    (r"\bdisipi\b", "DSPy"),
    (r"\bcarpath?ian\b", "Karpathy"),
    (r"\bkarpac[ií]\b", "Karpathy"),
    (r"\bfight tuning\b", "fine-tuning"),
    (r"\bfine tuning\b", "fine-tuning"),
]
CORRECTIONS = [(re.compile(p, re.IGNORECASE), r) for p, r in CORRECTIONS]


def apply_corrections(text):
    for pat, repl in CORRECTIONS:
        text = pat.sub(repl, text)
    return text


def clean(path):
    segs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "AUDIO:" not in line:
                continue
            txt = AUDIO_RE.sub("", line, count=1).strip()
            if not txt or NOISE_RE.match(txt):
                continue
            segs.append(txt)
    # Une los segmentos en prosa continua, normalizando espacios.
    text = " ".join(segs)
    text = re.sub(r"\s+", " ", text).strip()
    text = apply_corrections(text)
    return text

rows = []
for src_rel, slug, titulo, area, carpeta, fecha, tags in CLASES:
    src = os.path.join(SRC, src_rel)
    text = clean(src)
    out = os.path.join(DATA, slug + ".txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    nwords = len(text.split())
    rows.append({
        "id": slug,
        "fichero": slug + ".txt",
        "titulo": titulo,
        "profesor": PROFESOR,
        "area": area,
        "carpeta": carpeta,
        "etiquetas": ";".join(tags),
        "fecha": fecha,
        "idioma": IDIOMA,
        "n_palabras": nwords,
    })
    print(f"{slug}: {nwords} palabras -> {out}")

meta = os.path.join(DATA, "metadata.csv")
with open(meta, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"\nmetadata.csv -> {meta}")
print(f"Total palabras corpus: {sum(r['n_palabras'] for r in rows)}")
print(f"Carpetas: {sorted(set(r['carpeta'] for r in rows))}")
print(f"Áreas: {sorted(set(r['area'] for r in rows))}")
all_tags = sorted({t for r in rows for t in r['etiquetas'].split(';')})
print(f"Etiquetas únicas ({len(all_tags)}): {all_tags}")

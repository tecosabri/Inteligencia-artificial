# Práctica Final LLM — RAG sobre transcripciones con metadatos

Buscador inteligente sobre un corpus de **transcripciones** que entiende
preguntas en lenguaje natural **y respeta cómo están organizadas** (por
carpeta, etiquetas y fecha). POC autónomo, en Python, 100% local.

> **Motivación (contexto de alto nivel):** la idea nace de un proyecto
> personal —una app de notas de voz que organiza transcripciones en carpetas
> y con etiquetas—. Esta práctica es un POC independiente de ese problema de
> búsqueda; no toca esa app.

## El corpus
Las **6 clases del módulo LLM** del bootcamp (~25 h de vídeo → ~203.000
palabras de transcripción). Corpus realista en **español** (con tecnicismos en
inglés) y con organización natural en **carpetas (clases)** y **etiquetas
(temas que cruzan varias clases)**.

> **Idioma:** corpus y consultas en **español (ES/ES)**. El objetivo es
> **extraer información**, no traducir. Embeddings con un modelo abierto con
> buen rendimiento en español.

```
data/
  clase-1.txt … clase-6.txt   # transcripciones limpias (202.898 palabras)
  metadata.csv                # una fila por transcripción
```

### Esquema de `metadata.csv`
| campo | descripción | uso en el RAG |
|---|---|---|
| `id` / `fichero` | identificador y archivo | join |
| `titulo` · `profesor` | de la clase | display / cita |
| `area` | Fundamentos / Construcción / Producción | filtro de carpeta (alto nivel) |
| `carpeta` | la clase (Clase 1…6) | **filtro de carpeta** |
| `etiquetas` | temas, separados por `;` (cruzan clases) | **filtro por etiqueta** |
| `fecha` | fecha de la clase | **filtro temporal** |

## Estado por fases (ciclo de vida GenAI)
- [x] **Fase 0** — Setup y planteamiento
- [x] **Fase 1** — Datos: corpus limpio + `metadata.csv`
- [x] **Fase 2** — Ingesta: chunking + embeddings + Chroma con metadatos → **1.394 chunks** (`src/01_ingest.py`)
- [x] **Fase 3** — Baseline: retrieval semántico (`src/02_query.py`)
- [x] **Fase 4** — Retrieval **con metadatos** (filtro carpeta/área/etiqueta/fecha) (`src/02_query.py`, `rag_core.py`)
- [x] **Fase 5** — Generación end-to-end con LLM local + citas + guardrail (`src/03_rag.py`)
- [x] **Fase 6** — Evaluación: golden set + métricas, **baseline vs metadata** (`src/04_eval.py`)
- [x] **Fase 7** — Demo en Gradio (`app.py`)
- [ ] **Fase 8** — Conclusiones (borrador abajo) · _extras: self-query, deploy a HF Spaces_

## 📊 Resultados de evaluación (Fase 6)
Golden set de 10 preguntas, k=5. **Relevante = chunk de la clase correcta.**
| Métrica | Baseline (semántico) | Con metadatos (filtro por etiqueta) |
|---|---|---|
| Precisión@5 | 0,66 | **0,96** |
| MRR | 0,73 | **1,00** |
| Clases distintas en top-5 (contaminación) | 2,30 | **1,10** |

**Lectura:** filtrar por la etiqueta del tema sube la precisión de 0,66 → 0,96
y concentra los resultados en la clase correcta (menos mezcla entre clases).

## Requisitos
- **Python 3.11–3.13** (¡NO 3.8! falla al compilar `tokenizers`).
- **Ollama** sirviendo un modelo open-weights (`ollama pull qwen2.5:7b-instruct`).

## Cómo usar
```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5:7b-instruct

python src/01_ingest.py                       # construye el índice (Fase 2)
python src/02_query.py "qué es la evaluación" --etiqueta evaluacion   # baseline vs metadatos (Fase 3-4)
python src/03_rag.py "¿qué es LoRA?" --carpeta "Clase 3"              # RAG con respuesta (Fase 5)
python src/04_eval.py                          # tabla antes/después (Fase 6); --judge añade juez LLM
python app.py                                  # demo web en http://127.0.0.1:7860 (Fase 7)
```

## Stack
Python 3.13 · LangChain · ChromaDB · sentence-transformers
(`paraphrase-multilingual-mpnet-base-v2`) · **LLM open-weights local vía
Ollama** · Gradio. Sin servicios de pago.

## Decisiones de ingeniería y limitaciones (borrador Fase 8)
- **ES/ES, no traducción.** El corpus y las preguntas son español; usamos un
  modelo de embeddings multilingüe con buen español (no hay problema
  cross-lingual).
- **LLM local open-weights** (Ollama / Qwen2.5-7B) para generación y para el
  juez de evaluación. Sin claves ni coste.
- **Evaluación nativa en vez de RAGAS.** RAGAS 0.4.3 tiene un conflicto de
  imports con langchain 1.x (referencia `langchain_community.chat_models.vertexai`,
  retirado). Implementamos las mismas ideas (precisión de contexto, fidelidad,
  relevancia) de forma nativa: métricas de recuperación + juez LLM local.
- **Limpieza de términos del ASR (preprocesado, GIGO).** Las transcripciones
  son ASR de habla espontánea y destrozan los tecnicismos: "RAG"→"rack" (61
  veces), "guardrail"→"WarRail", "LoRA"→"Lora", "RAGAS"→"ráguilas"… Sin
  corregirlo, la consulta limpia "RAG" no casa con "rack" y el RAG se niega a
  responder. `src/00_build_corpus.py` aplica un diccionario de correcciones
  por término antes de indexar — esto, por sí solo, arregló la búsqueda de los
  términos clave. El ruido restante aún baja algo los scores de similitud;
  mejoras futuras: chunking más fino, expansión de consulta, reranking con
  cross-encoder, búsqueda híbrida (BM25 + semántica).
- **Etiquetas que cruzan clases** (p. ej. `rag` está en Clase 4 y 5): el filtro
  por esa etiqueta no aísla una sola clase — comportamiento esperado y honesto.
- **Pendiente (extras):** `SelfQueryRetriever` (que un LLM extraiga los filtros
  de la pregunta automáticamente) y desplegar la demo en Hugging Face Spaces.
```
practica-final-rag/
├── data/                # corpus + metadata.csv
├── src/
│   ├── 00_build_corpus.py  # Fase 1: limpia transcripciones + corrige términos ASR
│   ├── rag_core.py      # embeddings, vector store, LLM, retrieval con metadatos
│   ├── 01_ingest.py     # Fase 2
│   ├── 02_query.py      # Fase 3-4
│   ├── 03_rag.py        # Fase 5
│   └── 04_eval.py       # Fase 6
├── app.py               # Fase 7 (Gradio)
├── requirements.txt
└── README.md
```

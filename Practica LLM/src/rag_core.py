"""
Núcleo compartido del RAG: embeddings, vector store, LLM local y helpers de
recuperación con metadatos. Lo usan 02_query.py, 03_rag.py, 04_eval.py y app.py.
"""
from __future__ import annotations
import os
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = str(ROOT / "chroma_db")
COLLECTION = "clases_llm"

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
# LLM local open-weights (Ollama). Cámbialo con la variable de entorno OLLAMA_MODEL.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")

_embeddings = None
_vectorstore = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = Chroma(
            collection_name=COLLECTION,
            embedding_function=get_embeddings(),
            persist_directory=CHROMA_DIR,
        )
    return _vectorstore


def get_llm(temperature: float = 0.0):
    """LLM local vía Ollama. Import perezoso para no exigir Ollama si solo recuperas.
    keep_alive mantiene el modelo en memoria 30 min para que no recargue en cada consulta."""
    from langchain_ollama import ChatOllama
    return ChatOllama(model=OLLAMA_MODEL, temperature=temperature, keep_alive="30m")


# --- Filtros de metadatos -----------------------------------------------------

def build_where(carpeta: str | None = None, area: str | None = None,
                desde: int | None = None, hasta: int | None = None) -> dict | None:
    """Construye el filtro `where` de Chroma a partir de campos escalares.
    Fechas en formato entero AAAAMMDD (p. ej. 20260619). Devuelve None si no hay filtros."""
    clauses = []
    if carpeta:
        clauses.append({"carpeta": carpeta})
    if area:
        clauses.append({"area": area})
    if desde is not None:
        clauses.append({"fecha_ord": {"$gte": desde}})
    if hasta is not None:
        clauses.append({"fecha_ord": {"$lte": hasta}})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def retrieve(query: str, k: int = 5, *, carpeta: str | None = None,
             area: str | None = None, etiqueta: str | None = None,
             desde: int | None = None, hasta: int | None = None):
    """Recupera los k chunks más relevantes.
    - carpeta/area/fecha → filtro DURO en Chroma (where).
    - etiqueta → post-filtrado (las etiquetas se guardan como string "a;b;c").
    Devuelve lista de (Document, score)."""
    db = get_vectorstore()
    where = build_where(carpeta, area, desde, hasta)
    # Si filtramos por etiqueta, pedimos de más y filtramos en Python.
    fetch_k = k * 6 if etiqueta else k
    hits = db.similarity_search_with_relevance_scores(query, k=fetch_k, filter=where)
    if etiqueta:
        tag = etiqueta.lower()
        hits = [(d, s) for d, s in hits if tag in d.metadata.get("etiquetas", "").lower().split(";")]
    return hits[:k]


def format_citation(doc) -> str:
    m = doc.metadata
    return f"{m.get('carpeta','?')} · {m.get('fecha','?')} · [{m.get('titulo','')[:40]}]"

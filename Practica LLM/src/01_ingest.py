#!/usr/bin/env python3
"""
Fase 2 — Ingesta e indexado.

Lee el corpus (data/clase-*.txt + data/metadata.csv), trocea cada
transcripción en chunks, calcula su embedding con un modelo abierto con buen
rendimiento en español, y lo guarda en un índice ChromaDB **adjuntando los
metadatos a cada chunk** (carpeta, área, etiquetas, fecha…). Esos metadatos
son los que luego permitirán filtrar la búsqueda (Fase 4).

Todo corre en local: la primera ejecución descarga el modelo de embeddings
(~1 GB) desde Hugging Face; no hace falta ninguna API key.

Uso:
    python src/01_ingest.py                 # construye el índice
    python src/01_ingest.py --test "¿qué es el chunking?"   # prueba rápida
"""
from __future__ import annotations
import argparse
import csv
import os
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# --- Configuración -----------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
META_CSV = DATA_DIR / "metadata.csv"
CHROMA_DIR = str(ROOT / "chroma_db")
COLLECTION = "clases_llm"

# Modelo de embeddings abierto y multilingüe con buen español. Alternativas:
#   intfloat/multilingual-e5-base (mejor calidad, requiere prefijos query/passage)
#   sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (más rápido, 384d)
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"  # 768 dims

CHUNK_SIZE = 1000      # caracteres (~150-180 palabras)
CHUNK_OVERLAP = 150    # solape para no cortar ideas a la mitad


def load_metadata() -> list[dict]:
    with open(META_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_documents(meta_rows: list[dict]) -> list[Document]:
    """Trocea cada transcripción y crea un Document por chunk con sus metadatos."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    docs: list[Document] = []
    for row in meta_rows:
        text = (DATA_DIR / row["fichero"]).read_text(encoding="utf-8")
        chunks = splitter.split_text(text)
        fecha_ord = int(row["fecha"].replace("-", ""))  # 2026-06-19 -> 20260619
        for i, chunk in enumerate(chunks):
            docs.append(Document(
                page_content=chunk,
                metadata={
                    "source_id": row["id"],
                    "titulo": row["titulo"],
                    "profesor": row["profesor"],
                    "area": row["area"],              # filtro de carpeta (alto nivel)
                    "carpeta": row["carpeta"],        # filtro de carpeta (clase)
                    "etiquetas": row["etiquetas"],    # "tag1;tag2;..." (filtro por etiqueta)
                    "fecha": row["fecha"],
                    "fecha_ord": fecha_ord,           # para filtros temporales (>=, <=)
                    "idioma": row["idioma"],
                    "chunk_index": i,
                },
            ))
        print(f"  {row['id']}: {len(chunks)} chunks")
    return docs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", metavar="PREGUNTA", help="Hace una búsqueda de prueba tras indexar")
    args = ap.parse_args()

    print(f"Cargando metadatos de {META_CSV.name}…")
    meta_rows = load_metadata()

    print(f"Troceando {len(meta_rows)} transcripciones (chunk={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})…")
    docs = build_documents(meta_rows)
    print(f"Total: {len(docs)} chunks")

    print(f"Cargando modelo de embeddings: {EMBED_MODEL}\n(la primera vez descarga ~1 GB)…")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        encode_kwargs={"normalize_embeddings": True},  # coseno = producto punto
    )

    print(f"Construyendo índice Chroma en {CHROMA_DIR}…")
    db = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLLECTION,
        persist_directory=CHROMA_DIR,
    )
    print(f"✅ Índice listo: {len(docs)} chunks indexados en la colección '{COLLECTION}'.")

    if args.test:
        print(f"\n🔎 Prueba: «{args.test}»")
        hits = db.similarity_search_with_relevance_scores(args.test, k=4)
        for d, score in hits:
            print(f"\n[{score:.3f}] {d.metadata['carpeta']} · tags={d.metadata['etiquetas']}")
            print("   " + d.page_content[:200].replace("\n", " ") + "…")


if __name__ == "__main__":
    main()

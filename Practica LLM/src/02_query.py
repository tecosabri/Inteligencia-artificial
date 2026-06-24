#!/usr/bin/env python3
"""
Fase 3-4 — Recuperación: baseline semántico vs recuperación CON metadatos.

Demuestra el corazón del proyecto: filtrar por carpeta (clase), etiqueta (tema)
y fecha mejora la precisión y desambigua frente a la búsqueda "a pelo".

Ejemplos:
    python src/02_query.py "qué es el chunking"
    python src/02_query.py "qué es la evaluación" --carpeta "Clase 6"
    python src/02_query.py "qué es la evaluación" --etiqueta ragas
    python src/02_query.py "qué herramientas hay" --area Producción --desde 2026-06-22
"""
from __future__ import annotations
import argparse
from rag_core import retrieve, format_citation


def show(titulo, hits):
    print(f"\n{'='*70}\n{titulo}\n{'='*70}")
    if not hits:
        print("  (sin resultados)")
        return
    for d, score in hits:
        print(f"\n[{score:.3f}] {format_citation(d)}")
        print("   " + " ".join(d.page_content.split())[:220] + "…")


def to_ord(fecha: str | None) -> int | None:
    return int(fecha.replace("-", "")) if fecha else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=4)
    ap.add_argument("--carpeta")        # p.ej. "Clase 4"
    ap.add_argument("--area")           # Fundamentos / Construcción / Producción
    ap.add_argument("--etiqueta")       # p.ej. rag, evaluacion, lora
    ap.add_argument("--desde")          # AAAA-MM-DD
    ap.add_argument("--hasta")          # AAAA-MM-DD
    args = ap.parse_args()

    # Baseline: solo semántico, sin metadatos.
    base = retrieve(args.query, k=args.k)
    show("BASELINE — solo búsqueda semántica", base)

    # Con metadatos (si se pasó algún filtro).
    if any([args.carpeta, args.area, args.etiqueta, args.desde, args.hasta]):
        meta = retrieve(
            args.query, k=args.k,
            carpeta=args.carpeta, area=args.area, etiqueta=args.etiqueta,
            desde=to_ord(args.desde), hasta=to_ord(args.hasta),
        )
        filtros = {kk: vv for kk, vv in vars(args).items()
                   if kk in {"carpeta", "area", "etiqueta", "desde", "hasta"} and vv}
        show(f"CON METADATOS — filtros: {filtros}", meta)
    else:
        print("\n(Pasa --carpeta/--etiqueta/--area/--desde/--hasta para comparar con el filtrado.)")


if __name__ == "__main__":
    main()

"""A small web API over the same connection and search logic as the
desktop app, with a one-page frontend (index.html). Needs the optional
extras: pip install "bible-connection[api]". Run from anywhere with

    uvicorn bible_connection.api:app
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from bible_connection.core.connections import find_verse, get_connections, search_text, verse_ref
from bible_connection.core.db import get_connection

app = FastAPI(title="Bible Connection API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


def row_to_verse(row):
    return {
        "id": row["id"],
        "book": row["book"],
        "chapter": row["chapter"],
        "verse": row["verse"],
        "text": row["text"],
        "ref": verse_ref(row),
    }


@app.get("/api/verse")
def api_verse(ref: str = Query(..., description="e.g. 'John 3:16'"), limit: int = 8):
    conn = get_connection()
    row = find_verse(conn, ref)
    if row is None:
        raise HTTPException(404, f"Verse not found: {ref!r}")

    curated, semantic = get_connections(conn, row["id"], limit=limit)
    return {
        "verse": row_to_verse(row),
        "curated": [{**row_to_verse(r), "weight": r["weight"]} for r in curated],
        "semantic": [{**row_to_verse(r), "weight": r["weight"]} for r in semantic],
    }


@app.get("/api/search")
def api_search(q: str, limit: int = 15):
    conn = get_connection()
    rows = search_text(conn, q, limit=limit)
    return {"results": [row_to_verse(r) for r in rows]}


@app.get("/api/stats")
def api_stats():
    conn = get_connection()
    verses = conn.execute("SELECT COUNT(*) FROM verses").fetchone()[0]
    curated = conn.execute("SELECT COUNT(*) FROM edges WHERE edge_type='curated'").fetchone()[0]
    semantic = conn.execute("SELECT COUNT(*) FROM edges WHERE edge_type='semantic'").fetchone()[0]
    return {"verses": verses, "curated_edges": curated, "semantic_edges": semantic}


WEB_DIR = Path(__file__).resolve().parent  # index.html, next to this file
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

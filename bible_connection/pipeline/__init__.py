"""Rebuilds the content database from the source files in the repo's
data/raw folder. Only useful in a clone -- an installed copy ships the
built database and has no data/raw. Run each step as a module from the
repo root, in the order DEVELOPMENT.md lists, e.g.

    python3 -m bible_connection.pipeline.ingest_kjv
"""
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

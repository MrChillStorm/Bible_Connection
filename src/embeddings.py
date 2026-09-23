"""Compute sentence embeddings for every verse and store them in the
embeddings table, then derive 'semantic' edges from nearest-neighbor
similarity.

Brute-force cosine similarity is fine at this scale (~31k verses): we
batch rows against the full matrix rather than materializing the full
31k x 31k similarity matrix (which would be ~3.7GB).

Semantic ranking is re-ranked (not replaced) by an IDF-weighted Strong's
lemma-overlap signal: two verses sharing a *rare* original-language word
get nudged up the candidate list relative to peers with the same raw
cosine score, since the plain-English embedding is blind to which
underlying Hebrew/Greek word each translated word actually represents.
The stored edge weight stays pure cosine similarity throughout -- the
lemma signal only affects which candidates get selected and their
relative order, never what a saved edge's weight means.
"""
import argparse
import math

import numpy as np
from scipy.sparse import csr_matrix
from sentence_transformers import SentenceTransformer

from db import get_connection

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 512

LEMMA_BOOST_ALPHA = 0.15   # weight given to lemma-cosine similarity (itself in [0,1]) when re-ranking
LEMMA_BOOST_CAP = 0.15     # safety net; with alpha=cap this only ever binds on float overshoot
CANDIDATE_POOL_FACTOR = 4  # gather this many x top_k boosted candidates before filtering by raw cosine


def compute_embeddings(conn) -> None:
    rows = conn.execute("SELECT id, text FROM verses ORDER BY id").fetchall()
    ids = [r["id"] for r in rows]
    texts = [r["text"] for r in rows]

    print(f"Encoding {len(texts)} verses with {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)
    vectors = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,  # so dot product == cosine similarity
        convert_to_numpy=True,
    ).astype(np.float32)

    dim = vectors.shape[1]
    conn.execute("DELETE FROM embeddings")
    conn.executemany(
        "INSERT INTO embeddings (verse_id, model, dim, vector) VALUES (?, ?, ?, ?)",
        ((vid, MODEL_NAME, dim, vec.tobytes()) for vid, vec in zip(ids, vectors)),
    )
    conn.commit()
    print(f"Stored {len(ids)} embeddings (dim={dim})")


def load_embedding_matrix(conn):
    rows = conn.execute(
        "SELECT v.id, v.book_order, v.chapter, e.vector, e.dim FROM verses v "
        "JOIN embeddings e ON e.verse_id = v.id ORDER BY v.id"
    ).fetchall()
    ids = np.array([r["id"] for r in rows], dtype=np.int64)
    book_order = np.array([r["book_order"] for r in rows], dtype=np.int32)
    chapter = np.array([r["chapter"] for r in rows], dtype=np.int32)
    dim = rows[0]["dim"]
    matrix = np.vstack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows]).reshape(len(rows), dim)
    return ids, book_order, chapter, matrix


def build_lemma_matrix(conn, ids: np.ndarray) -> csr_matrix:
    """Sparse (n_verses x n_strong_numbers) TF-IDF-style matrix, L2-row-
    normalized so that (M @ M.T)[i,j] is a proper cosine similarity in
    [0,1] between two verses' sets of Strong's-tagged words, weighted by
    rarity (idf). Row-normalizing matters: without it, a verse sharing
    several moderately-common words with another (e.g. "God", "the",
    "that") can rack up a large *raw* idf-sum purely by sharing many
    weak signals, none of which is individually distinctive -- cosine
    similarity divides that back down by each verse's own total lemma
    "weight budget", so a handful of common shared words can't outweigh
    one genuinely rare shared word the way an unnormalized sum can."""
    id_to_row = {int(vid): i for i, vid in enumerate(ids)}
    n_verses = len(ids)

    pairs = conn.execute("SELECT DISTINCT verse_id, strong_number FROM word_strongs").fetchall()

    doc_freq: dict[str, int] = {}
    for r in pairs:
        doc_freq[r["strong_number"]] = doc_freq.get(r["strong_number"], 0) + 1

    strong_to_col = {s: i for i, s in enumerate(doc_freq)}

    rows_idx, cols_idx, data = [], [], []
    for r in pairs:
        vid = r["verse_id"]
        row = id_to_row.get(vid)
        if row is None:
            continue
        s = r["strong_number"]
        idf = math.log(n_verses / doc_freq[s])
        rows_idx.append(row)
        cols_idx.append(strong_to_col[s])
        data.append(max(idf, 0.0))

    matrix = csr_matrix((data, (rows_idx, cols_idx)), shape=(n_verses, len(strong_to_col)), dtype=np.float32)

    norms = np.sqrt(matrix.multiply(matrix).sum(axis=1)).A1
    norms[norms == 0] = 1.0  # verses with no tagged words: leave as an all-zero row
    inv_norms = csr_matrix((1.0 / norms, (range(n_verses), range(n_verses))), shape=(n_verses, n_verses))
    return inv_norms @ matrix


def compute_semantic_edges(conn, top_k: int = 5, threshold: float = 0.55, chapter_gap: int = 1) -> None:
    ids, book_order, chapter, matrix = load_embedding_matrix(conn)
    n = len(ids)
    lemma_matrix = build_lemma_matrix(conn, ids)
    print(f"Computing top-{top_k} semantic neighbors for {n} verses (threshold={threshold}, "
          f"lemma-boosted re-ranking) ...")

    conn.execute("DELETE FROM edges WHERE edge_type = 'semantic'")

    pool_size = min(top_k * CANDIDATE_POOL_FACTOR, n - 1)
    batch = 500
    inserted = 0
    for start in range(0, n, batch):
        end = min(start + batch, n)
        cosine = matrix[start:end] @ matrix.T  # (batch, n) pure cosine similarities -- stored as edge weight
        lemma_overlap = (lemma_matrix[start:end] @ lemma_matrix.T).toarray()  # (batch, n) lemma cosine similarity, in [0,1]
        boost = np.clip(lemma_overlap * LEMMA_BOOST_ALPHA, 0, LEMMA_BOOST_CAP)
        ranking_score = cosine + boost  # used only to pick/order candidates, never stored

        for local_i, global_i in enumerate(range(start, end)):
            cos_row = cosine[local_i].copy()
            rank_row = ranking_score[local_i].copy()

            same_book = book_order == book_order[global_i]
            near_chapter = same_book & (np.abs(chapter - chapter[global_i]) <= chapter_gap)
            cos_row[near_chapter] = -1.0
            rank_row[near_chapter] = -1.0
            cos_row[global_i] = -1.0
            rank_row[global_i] = -1.0

            # widen the pool with the boosted ranking, then only keep
            # candidates that clear the threshold on their own (pure)
            # cosine merit -- the lemma boost can reorder and surface
            # candidates, but never smuggle a low-cosine match past the
            # quality bar just because it shares a couple of rare words
            pool_idx = np.argpartition(-rank_row, pool_size)[:pool_size]
            pool_idx = pool_idx[cos_row[pool_idx] >= threshold]
            pool_idx = pool_idx[np.argsort(-rank_row[pool_idx])][:top_k]

            edge_rows = []
            for j in pool_idx:
                score = float(cos_row[j])
                a_id, b_id = int(ids[global_i]), int(ids[j])
                a, b = (a_id, b_id) if a_id < b_id else (b_id, a_id)
                edge_rows.append((a, b, score))

            if edge_rows:
                conn.executemany(
                    """INSERT OR IGNORE INTO edges (verse_id_a, verse_id_b, edge_type, weight, source)
                       VALUES (?, ?, 'semantic', ?, ?)""",
                    [(a, b, score, MODEL_NAME) for a, b, score in edge_rows],
                )
                inserted += len(edge_rows)

        conn.commit()
        print(f"  ... {end}/{n} verses processed, {inserted} edges so far", end="\r")

    print()
    print(f"Inserted {inserted} semantic edges (pre-dedup; symmetric neighbor pairs collapse via INSERT OR IGNORE)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-encode", action="store_true", help="reuse existing embeddings table")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.55)
    args = parser.parse_args()

    conn = get_connection()
    if not args.skip_encode:
        compute_embeddings(conn)
    compute_semantic_edges(conn, top_k=args.top_k, threshold=args.threshold)
    conn.close()


if __name__ == "__main__":
    main()

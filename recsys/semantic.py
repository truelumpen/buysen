"""Search by meaning, merged with keyword search.

CLIP turns the typed query into a vector and compares it with every product's
image and text vectors, so "gift for a gamer" can find controllers even when
those words aren't in the title. The meaning ranking and the keyword (FTS5)
ranking are merged with Reciprocal Rank Fusion, which combines ranks, not scores.
"""

# makes a function remember its result
from functools import cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app import db

# --- Settings -------------------------------------------------
QUERY_IMAGE_WEIGHT = 1.0   # 1 = match the query to product photos only (tested best: CLIP's text-to-text
                           # scores favour a few vague "hub" products for every query), 0 = text only
SEMANTIC_CANDIDATES = 100  # how many meaning matches join the merge
KEYWORD_CANDIDATES = 100   # how many keyword matches join the merge
MIN_SIMILARITY = 0.27      # meaning matches weaker than this are dropped (real queries top ~0.27-0.31,
                           # nonsense ~0.23-0.26). Retune if QUERY_IMAGE_WEIGHT changes.
RRF_K = 60                 # Reciprocal Rank Fusion constant: larger = rank differences matter less
# --------------------------------------------------------------

MODEL_NAME = "clip-ViT-B-32"
EMBEDDINGS_PATH = db.DB_PATH.parent / "embeddings.npz"


@cache
def _model():
    """The CLIP model, loaded once and kept in memory."""
    model = SentenceTransformer(MODEL_NAME)
    model.max_seq_length = 77
    return model


@cache
def _vectors():
    """The product vectors from recsys.embed (None if not built yet)."""
    if not EMBEDDINGS_PATH.exists():
        return None
    data = np.load(EMBEDDINGS_PATH)
    return [int(i) for i in data["ids"]], data["text"], data["image"], data["has_image"]

def load():
    """Load the model and vectors up front, so the first search isn't slow."""
    if _vectors() is not None:
        _model()


def meaning_ranking(query):
    """Product ids ranked by how close their meaning is to the query."""
    vectors = _vectors()
    if vectors is None:
        return []
    ids, text, image, _ = vectors
    query_vector = _model().encode(query, normalize_embeddings=True)
    # Products without a photo have an all-zero image vector, so their image score is 0:
    # they get no meaning match from photos, but keyword search still finds them.
    scores = QUERY_IMAGE_WEIGHT * (image @ query_vector) + (1 - QUERY_IMAGE_WEIGHT) * (text @ query_vector)
    best = np.argsort(-scores)[:SEMANTIC_CANDIDATES]
    return [ids[i] for i in best if scores[i] >= MIN_SIMILARITY]


def hybrid_search(query, limit=24, offset=0):
    """One page of search results: keyword and meaning matches merged by rank."""
    keyword = [p["id"] for p in db.search_products(query, limit=KEYWORD_CANDIDATES)]
    meaning = meaning_ranking(query)

    # Reciprocal Rank Fusion: each list adds 1 / (RRF_K + rank) to a product's score,
    # so products ranked high in either list (or in both) rise to the top.
    scores = {}
    for ranking in (keyword, meaning):
        for rank, product_id in enumerate(ranking, start=1):
            scores[product_id] = scores.get(product_id, 0) + 1 / (RRF_K + rank)
    merged = sorted(scores, key=scores.get, reverse=True)
    return db.get_products(merged[offset : offset + limit])
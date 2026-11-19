"""Search by meaning, merged with keyword search.

CLIP turns the typed query into a vector and compares it with every product's
image and text vectors, so "gift for a gamer" can find controllers even when
those words aren't in the title. The meaning ranking and the keyword (FTS5)
ranking are merged with Reciprocal Rank Fusion, which combines ranks, not scores.
"""

import numpy as np

from app import db
from recsys import embed

# --- Settings -------------------------------------------------
QUERY_IMAGE_WEIGHT = 1.0   # 1 = match the query to product photos only (tested best: CLIP's text-to-text
                           # scores favour a few vague "hub" products for every query), 0 = text only
SEMANTIC_CANDIDATES = 100  # how many meaning matches join the merge
KEYWORD_CANDIDATES = 100   # how many keyword matches join the merge
MIN_SIMILARITY = 0.27      # meaning matches weaker than this are dropped (real queries top ~0.27-0.31,
                           # nonsense ~0.23-0.26). Retune if QUERY_IMAGE_WEIGHT changes.
RRF_K = 60                 # Reciprocal Rank Fusion constant: larger = rank differences matter less
# --------------------------------------------------------------

def load():
    """Load the vectors and CLIP up front, so the first search isn't slow."""
    if embed.load_embeddings() is not None:
        embed.load_model()


def meaning_ranking(query):
    """Product ids ranked by how close their meaning is to the query."""
    vectors = embed.load_embeddings()
    if vectors is None:
        return []
    query_vector = embed.load_model().encode(query, normalize_embeddings=True)
    # Products without a photo have an all-zero image vector, so their image score is 0:
    # they get no meaning match from photos, but keyword search still finds them.
    scores = QUERY_IMAGE_WEIGHT * (vectors["image"] @ query_vector) + (1 - QUERY_IMAGE_WEIGHT) * (
        vectors["text"] @ query_vector
    )
    best = np.argsort(-scores)[:SEMANTIC_CANDIDATES]
    return [vectors["ids"][i] for i in best if scores[i] >= MIN_SIMILARITY]


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
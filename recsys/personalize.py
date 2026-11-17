"""Personal recommendations from a user's views and buys.

A user's "taste" is the weighted average of the vectors of products they recently
viewed and bought. Every product is scored against that taste, so the home page
(Items for You, top categories, category shelves) changes as soon as they browse.
Users with no history get the most-bought fallbacks from db.py.
"""

# makes a function remember its result
from functools import cache

import numpy as np

from app import db

# --- Settings -----------------------------------------------------------------
BUY_WEIGHT = 3.0       # a purchase shapes the taste this many times more than a view
VIEW_WEIGHT = 1.0
HISTORY_LENGTH = 50    # only the most recent events count, so taste follows the user
IMAGE_WEIGHT = 0.1     # share of image similarity in the score (as in content.py)
TOP_CATEGORIES = 3     # how many category shelves the home page shows
HALF_LIFE = 7          # every N newer events halve an older event's influence (smaller = more reactive)
CATEGORY_DEPTH = 50    # categories are ranked by how many of the user's top N products they hold
# ------------------------------------------------------------------------------

EMBEDDINGS_PATH = db.DB_PATH.parent / "embeddings.npz"


@cache
def _catalog():
    """Load the product vectors once and keep them in memory (None if not built yet).
    After re-running recsys.embed, restart the server to pick up the new file."""
    if not EMBEDDINGS_PATH.exists():
        return None
    data = np.load(EMBEDDINGS_PATH)
    ids = [int(i) for i in data["ids"]]
    category = {p["id"]: p["category"] for p in db.list_products(limit=-1)}
    return {
        "ids": ids,
        "row": {product_id: row for row, product_id in enumerate(ids)},
        "category": category,
        "text": data["text"],
        "image": data["image"],
    }

def scores_for_history(rows, weights):
    """Score every product against a history: the catalog rows of the products the
    user touched, each with a weight. Shared by the website and recsys.evaluate."""
    catalog = _catalog()
    # Taste = weighted sum of the history's vectors (scale doesn't matter for ranking).
    weights = np.array(weights)[:, None]
    taste_text = (catalog["text"][rows] * weights).sum(axis=0)
    taste_image = (catalog["image"][rows] * weights).sum(axis=0)
    return (1 - IMAGE_WEIGHT) * (catalog["text"] @ taste_text) + IMAGE_WEIGHT * (
        catalog["image"] @ taste_image
    )

def ranked_products(user_id):
    """Every product id, best match first, excluding ones the user bought.
    None when there is nothing to personalise from yet."""
    catalog = _catalog()
    if catalog is None or user_id is None:
        return None
    rows, weights = [], []
    for position, event in enumerate(db.get_user_history(user_id, HISTORY_LENGTH)):
        row = catalog["row"].get(event["product_id"])
        if row is not None:
            rows.append(row)
            kind_weight = BUY_WEIGHT if event["kind"] == "buy" else VIEW_WEIGHT
            recency = 0.5 ** (position / HALF_LIFE)  # newest event = 1, halves every HALF_LIFE events
            weights.append(kind_weight * recency)
    if not rows:
        return None
    scores = scores_for_history(rows, weights)
    bought = {p["id"] for p in db.get_bought(user_id)}
    order = np.argsort(-scores)
    return [catalog["ids"][i] for i in order if catalog["ids"][i] not in bought]


def recommend(user_id, limit=5, offset=0, category=None):
    """One page of personal picks, optionally only from one category."""
    ranked = ranked_products(user_id)
    if ranked is None:  # no history yet: fall back to the simple versions
        if category:
            return db.list_products(category=category, limit=limit, offset=offset)
        return db.recommend_for_user(user_id, limit=limit, offset=offset)
    if category:
        ranked = [i for i in ranked if _catalog()["category"][i] == category]
    return db.get_products(ranked[offset : offset + limit])


def top_categories(user_id, limit=TOP_CATEGORIES):
    """The user's best categories: the ones most common among their top matches."""
    ranked = ranked_products(user_id)
    if ranked is None:
        return db.top_categories(user_id, limit)
    counts = {}
    for product_id in ranked[:CATEGORY_DEPTH]:
        category = _catalog()["category"][product_id]
        counts[category] = counts.get(category, 0) + 1
    best = sorted(counts, key=counts.get, reverse=True)
    for category in db.popular_categories():  # top up if the user's matches span few categories
        if category not in best:
            best.append(category)
    return best[:limit]
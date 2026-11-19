"""Phase 3 evaluation: measure the recommenders and write reports/evaluation.md.

Run from the project root:  uv run python -m recsys.evaluate
Takes a few seconds (plus ~5 s to load CLIP for the search table).
"""

import random
from datetime import date
from pathlib import Path

import numpy as np

from app import db
from recsys import content, embed, personalize, semantic
from recsys.metrics import category_agreement, coverage

# --- Settings to experiment with ---------------------------------------------
WEIGHTS_TO_TRY = [1.0, 0.7, 0.5, 0.3, 0.1, 0.0]  # IMAGE_WEIGHT values for the related-items table
TOP_N = 10             # how many recommendations are checked per product / per user
SIMULATED_VIEWS = 5    # products each simulated user views before we look at their picks
SEED = 42              # same random picks every run, so the report is reproducible
REAL_QUERIES = [
    "gift for a gamer", "something to keep my dog busy", "cozy winter outfit",
    "kitchen gadgets", "toys for toddlers", "hiking gear", "office desk organizer",
]
NONSENSE_QUERIES = ["zzzzqqq", "asdf jkl", "xkcd lorem ipsum"]
# ------------------------------------------------------------------------------

REPORT_PATH = Path(__file__).parent.parent / "reports" / "evaluation.md"


def load_data():
    """The saved vectors, plus each product's category in the same row order."""
    data = embed.load_embeddings()
    category_of = {p["id"]: p["category"] for p in db.list_products(limit=-1)}
    categories = np.array([category_of[i] for i in data["ids"]])
    return data, categories


def related_items_table(data, categories):
    """Related items: how often they share the product's category, for each IMAGE_WEIGHT."""
    lines = [
        f"| IMAGE_WEIGHT | Same category @1 | Same category @{TOP_N} | Coverage |",
        "|---|---|---|---|",
    ]
    for weight in WEIGHTS_TO_TRY:
        similarity = content.similarity_matrix(data["text"], data["image"], data["has_image"], weight)
        neighbours = content.top_k(similarity, TOP_N)
        current = " (current)" if weight == content.IMAGE_WEIGHT else ""
        lines.append(
            f"| {weight}{current} "
            f"| {category_agreement(neighbours, categories, 1):.0%} "
            f"| {category_agreement(neighbours, categories, TOP_N):.0%} "
            f"| {coverage(neighbours, len(categories)):.0%} |"
        )
    return lines


def personalization_table(categories):
    """Simulated users: view products from one category, then check their top picks."""
    rng = random.Random(SEED)
    popular = np.array([p["category"] for p in db.list_products(limit=TOP_N)])
    lines = [
        (f"| Simulated user viewed {SIMULATED_VIEWS} products from | "
        f"Items for You in that category | Popular items in that category |"),
        "|---|---|---|",
    ]
    personal_shares, popular_shares = [], []
    for category in sorted(set(categories)):
        viewed = rng.sample(list(np.where(categories == category)[0]), SIMULATED_VIEWS)
        scores = personalize.scores_for_history(viewed, [1.0] * SIMULATED_VIEWS)
        scores[viewed] = -np.inf  # don't count the products they already viewed
        top = np.argsort(-scores)[:TOP_N]
        personal_shares.append((categories[top] == category).mean())
        popular_shares.append((popular == category).mean())
        lines.append(f"| {category} | {personal_shares[-1]:.0%} | {popular_shares[-1]:.0%} |")
    lines.append(f"| **Average** | **{np.mean(personal_shares):.0%}** | **{np.mean(popular_shares):.0%}** |")
    return lines


def search_table():
    """Search by meaning: real queries should find matches, nonsense should find none."""
    semantic.load()
    lines = ["| Query | Type | Meaning matches | Best meaning match |", "|---|---|---|---|"]
    for kind, queries in (("real", REAL_QUERIES), ("nonsense", NONSENSE_QUERIES)):
        for query in queries:
            ranking = semantic.meaning_ranking(query)
            best = db.get_products(ranking[:1])
            title = best[0]["title"][:60].replace("|", "/") if best else "none"
            lines.append(f"| {query} | {kind} | {len(ranking)} | {title} |")
    return lines


def main():
    data, categories = load_data()
    report = [
        "# Cloneazon evaluation (Phase 3)",
        "",
        (f"Generated {date.today()} by `uv run python -m recsys.evaluate` "
        f"on {len(categories):,} products. Random choices use seed {SEED}."),
        "",
        "## 1. Related items",
        "",
        (f"For every product, its top {TOP_N} related items. *Same category @k*: share of the top k "
        "that are in the product's own category. *Coverage*: share of the catalog that appears in "
        "anyone's related list (low = the same few products everywhere)."),
        "",
        *related_items_table(data, categories),
        "",
        ("Category is a rough proxy for relevance: a phone case under a phone counts as a miss if "
        "they sit in different categories, and a dog leash under a cat bowl counts as a hit."),
        "",
        "## 2. Personalization (simulated users)",
        "",
        (f"Each simulated user views {SIMULATED_VIEWS} random products from one category. We then "
        f"check how many of their top {TOP_N} *Items for You* come from that category, compared "
        "with *Popular items*, which ignore the user."),
        "",
        *personalization_table(categories),
        "",
        ("Simulated users are not real shoppers; this checks that personalization adapts, "
        "not that people would buy what it shows."),
        "",
        "## 3. Search by meaning",
        "",
        (f"Matches above MIN_SIMILARITY = {semantic.MIN_SIMILARITY} "
        f"(QUERY_IMAGE_WEIGHT = {semantic.QUERY_IMAGE_WEIGHT}). Keyword matches are not counted here."),
        "",
        *search_table(),
        "",
    ]
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(report))
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
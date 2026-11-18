"""Sanity checks on the related items that recsys.content saved to the database.

These read the real data, so run `uv run python -m recsys.build` first.
"""

import sqlite3
from contextlib import closing

import pytest

from app import db


@pytest.fixture(scope="module")
def rows():
    """All saved content rows as (product_id, similar_id, score, rank), read once for every test."""
    if not db.DB_PATH.exists():
        pytest.skip("No database yet")
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        rows = conn.execute(
            "SELECT product_id, similar_id, score, rank FROM similar_items WHERE method = 'content'"
        ).fetchall()
    if not rows:
        pytest.skip("No related items yet: run `uv run python -m recsys.build`")
    return rows


def test_no_product_is_related_to_itself(rows):
    assert all(product_id != similar_id for product_id, similar_id, _, _ in rows)


def test_no_duplicate_pairs(rows):
    pairs = [(product_id, similar_id) for product_id, similar_id, _, _ in rows]
    assert len(pairs) == len(set(pairs))


def test_ranks_count_up_and_follow_scores(rows):
    per_product = {}
    for product_id, _, score, rank in rows:
        per_product.setdefault(product_id, []).append((rank, score))
    for items in per_product.values():
        items.sort()  # by rank
        ranks = [rank for rank, _ in items]
        scores = [score for _, score in items]
        assert ranks == list(range(1, len(ranks) + 1))  # 1, 2, 3, ... with no gaps
        assert scores == sorted(scores, reverse=True)  # rank 1 has the highest score
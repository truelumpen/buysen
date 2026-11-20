"""After a full pipeline run (s1-s4): the complements fit the catalog and shoppers exist.

These read the real database, so run the pipeline first.
"""

import json
import sqlite3
from contextlib import closing

import pytest

from app import db
from pipeline import s4_simulate_shoppers as s4


@pytest.fixture(scope="module")
def conn():
    if not db.DB_PATH.exists():
        pytest.skip("No database yet: run the pipeline (s1-s4) first")
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        yield conn


def test_every_complement_id_is_a_catalog_product(conn):
    product_ids = {row[0] for row in conn.execute("SELECT id FROM products")}
    with s4.COMPLEMENTS_PATH.open() as f:
        rows = [json.loads(line) for line in f]
    used = {row["product_id"] for row in rows} | {c["id"] for row in rows for c in row["complements"]}
    assert used <= product_ids


def test_simulated_shoppers_made_purchases(conn):
    shoppers = conn.execute("SELECT COUNT(*) FROM users WHERE name_ LIKE 'shopper-%'").fetchone()[0]
    purchases = conn.execute("SELECT COUNT(*) FROM events WHERE kind = 'buy'").fetchone()[0]
    assert shoppers == s4.SHOPPERS
    assert purchases > shoppers  # every shopper buys on at least two trips
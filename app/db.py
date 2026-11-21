"""All database access for Cloneazon."""

import re
import sqlite3
from contextlib import (
    closing,  #ensure that resources are automatically and safely closed upon exiting the block, even if errors occur.
)
from pathlib import Path

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR.parent / "data" / "cloneazon.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Access elements by row["title"] instead of row[number]
    conn.execute("PRAGMA foreign_keys = ON") # Enfore foreign keys for each connection as it is OFF by default
    return conn


def _read(sql, params=()):
    with closing(_connect()) as conn:
        return conn.execute(sql, params).fetchall()


def _write(sql, params):
    with closing(_connect()) as conn:
        conn.execute(sql, params)
        conn.commit()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = (APP_DIR / "schema.sql").read_text()
    with closing(_connect()) as conn:
        conn.executescript(schema)


def get_user(user_id):
    rows = _read("SELECT * FROM users WHERE id = ?", (user_id,))
    return rows[0] if rows else None


def get_or_create_user(name):
    """Log in as `name`, creating the account the first time that name is used."""
    with closing(_connect()) as conn:
        # OR IGNORE: if the name already exists (UNIQUE), skip the insert instead of failing.
        conn.execute("INSERT OR IGNORE INTO users (name_) VALUES (?)", (name,))
        conn.commit()
        return conn.execute("SELECT * FROM users WHERE name_ = ?", (name,)).fetchone()


def list_categories():
    rows = _read("SELECT DISTINCT category FROM products ORDER BY category")
    return [row["category"] for row in rows]


def list_products(category=None, limit=24, offset=0):
    """Most popular products first, optionally only from one category.
    `offset` skips that many products, which is how pages 2, 3, ... are fetched."""
    if category is None:
        return _read(
            "SELECT * FROM products ORDER BY times_bought DESC, id LIMIT ? OFFSET ?",
            (limit, offset),
        )
    return _read(
        "SELECT * FROM products WHERE category = ? ORDER BY times_bought DESC, id LIMIT ? OFFSET ?",
        (category, limit, offset),
    )

def popular_categories():
    """All categories, most bought first."""
    rows = _read(
        "SELECT category FROM products GROUP BY category ORDER BY SUM(times_bought) DESC"
    )
    return [row["category"] for row in rows]
    

def search_products(query, limit=24, offset=0):
    """Products matching every word of `query`, most relevant first."""
    words = re.findall(r"\w+", query.lower())
    if not words:
        return []
    # Quote each word so characters like " or * can't break the FTS5 syntax.
    # The * after the last word also matches unfinished words ("headph").
    match = " ".join(f'"{word}"' for word in words) + "*"
    return _read(
        """
        SELECT products.*
        FROM products_fts
        JOIN products ON products.id = products_fts.rowid
        WHERE products_fts MATCH ?
        ORDER BY bm25(products_fts, 10.0, 3.0, 1.0), products.times_bought DESC
        LIMIT ? OFFSET ?
        """,
        (match, limit, offset),
    )

def get_products(ids):
    """The products with these ids, in the same order as `ids`."""
    if not ids:
        return []
    placeholders = ", ".join("?" for _ in ids)
    rows = _read(f"SELECT * FROM products WHERE id IN ({placeholders})", ids)
    by_id = {row["id"]: row for row in rows}
    return [by_id[i] for i in ids if i in by_id]


def get_user_history(user_id, limit=50):
    """The user's most recent views and buys, newest first."""
    return _read(
        """
        SELECT product_id, kind FROM events
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )

def get_product(product_id):
    rows = _read("SELECT * FROM products WHERE id = ?", (product_id,))
    return rows[0] if rows else None


def get_reviews(product_id):
    return _read(
        """
        SELECT reviews.*, users.name_ AS reviewer
        FROM reviews
        JOIN users ON users.id = reviews.user_id
        WHERE reviews.product_id = ?
        ORDER BY reviews.created_at DESC, reviews.id DESC
        """,
        (product_id,),
    )


def get_bought(user_id):
    return _read(
        """
        SELECT products.*, events.created_at AS bought_at
        FROM events
        JOIN products ON products.id = events.product_id
        WHERE events.user_id = ? AND events.kind = 'buy'
        ORDER BY events.created_at DESC, events.id DESC
        """,
        (user_id,),
    )
# Used by the queries below to leave out what a user already bought.
# With exclude_bought_by=None (logged out) it matches nothing, so nothing is left out.
NOT_BOUGHT_BY = "NOT IN (SELECT product_id FROM events WHERE user_id = ? AND kind = 'buy')"


def popular_products(limit=10, offset=0, exclude_bought_by=None):
    """Most bought in this store first (Amazon's sales break ties), skipping what the user bought."""
    return _read(
        f"""
        SELECT products.*
        FROM products
        LEFT JOIN (SELECT product_id, COUNT(*) AS store_buys
                   FROM events WHERE kind = 'buy' GROUP BY product_id) AS sales
          ON sales.product_id = products.id
        WHERE products.id {NOT_BOUGHT_BY}
        ORDER BY COALESCE(sales.store_buys, 0) DESC, products.times_bought DESC, products.id
        LIMIT ? OFFSET ?
        """,
        (exclude_bought_by, limit, offset),
    )


def bought_with(product_id, limit=-1, exclude_bought_by=None):
    """Complements of `product_id`: products other shoppers bought on the same trip
    (within a day), most shared buyers first, skipping what the user bought."""
    return _read(
        f"""
        SELECT products.*, COUNT(DISTINCT other.user_id) AS together
        FROM events AS mine
        JOIN events AS other
          ON other.user_id = mine.user_id
         AND other.kind = 'buy'
         AND other.product_id != mine.product_id
         AND ABS(julianday(other.created_at) - julianday(mine.created_at)) < 1
        JOIN products ON products.id = other.product_id
        WHERE mine.kind = 'buy' AND mine.product_id = ?
          AND products.id {NOT_BOUGHT_BY}
        GROUP BY products.id
        ORDER BY together DESC, products.times_bought DESC, products.id
        LIMIT ?
        """,
        (product_id, exclude_bought_by, limit),
    )


def get_similar(product_id, method, limit=6, exclude_bought_by=None):
    return _read(
        f"""
        SELECT products.*, similar_items.score
        FROM similar_items
        JOIN products ON products.id = similar_items.similar_id
        WHERE similar_items.product_id = ? AND similar_items.method = ?
          AND products.id {NOT_BOUGHT_BY}
        ORDER BY similar_items.rank
        LIMIT ?
        """,
        (product_id, method, exclude_bought_by, limit),
    )

def replace_similar(method, rows):
    """Replace every similar_items row of one method, in a single transaction.
    `rows` are (product_id, similar_id, score, rank) tuples."""
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM similar_items WHERE method = ?", (method,))
        conn.executemany(
            """
            INSERT INTO similar_items (product_id, similar_id, method, score, rank)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(product_id, similar_id, method, score, rank) for product_id, similar_id, score, rank in rows],
        )
        conn.commit()

def add_review(product_id, user_id, rating, text):
    text = (text or "").strip() or None
    _write(
        "INSERT INTO reviews (product_id, user_id, rating, text_) VALUES (?, ?, ?, ?)",
        (product_id, user_id, rating, text),
    )


def add_event(user_id, product_id, kind):
    _write(
        "INSERT INTO events (user_id, product_id, kind) VALUES (?, ?, ?)",
        (user_id, product_id, kind),
    )
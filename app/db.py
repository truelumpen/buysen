"""All database access for Cloneazon."""

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


def list_products(category=None, limit=24):
    """Most popular products first, optionally only from one category."""
    if category is None:
        return _read(
            "SELECT * FROM products ORDER BY times_bought DESC, id LIMIT ?",
            (limit,),
        )
    return _read(
        "SELECT * FROM products WHERE category = ? ORDER BY times_bought DESC, id LIMIT ?",
        (category, limit),
    )

def popular_categories():
    """All categories, most bought first."""
    rows = _read(
        "SELECT category FROM products GROUP BY category ORDER BY SUM(times_bought) DESC"
    )
    return [row["category"] for row in rows]


def top_categories(user_id, limit=3):
    """The categories this user interacts with most, topped up with popular ones."""
    rows = _read(
        """
        SELECT products.category
        FROM events
        JOIN products ON products.id = events.product_id
        WHERE events.user_id = ?
        GROUP BY products.category
        ORDER BY COUNT(*) DESC
        """,
        (user_id,),
    )
    categories = [row["category"] for row in rows]
    for category in popular_categories():
        if category not in categories:
            categories.append(category)
    return categories[:limit]


def recommend_for_user(user_id, limit=5):
    """Placeholder until the Phase 3 model: popular items from the user's
    favourite categories that they haven't bought yet."""
    favourites = top_categories(user_id)
    placeholders = ", ".join("?" for _ in favourites)
    return _read(
        f"""
        SELECT * FROM products
        WHERE category IN ({placeholders})
          AND id NOT IN (SELECT product_id FROM events WHERE user_id = ? AND kind = 'buy')
        ORDER BY rating DESC, times_bought DESC
        LIMIT ?
        """,
        (*favourites, user_id, limit),
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


def get_similar(product_id, method, limit=6):
    return _read(
        """
        SELECT products.*, similar_items.score
        FROM similar_items
        JOIN products ON products.id = similar_items.similar_id
        WHERE similar_items.product_id = ? AND similar_items.method = ?
        ORDER BY similar_items.rank
        LIMIT ?
        """,
        (product_id, method, limit),
    )


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
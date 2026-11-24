"""Step 3: load the downloaded catalog into the website's database.

Run from the project root:  uv run python -m pipeline.s3_load_db
Products whose image failed to download get a "No image" placeholder.
"""

import json
import sqlite3
from contextlib import closing

from app import db

CATALOG_PATH = db.DB_PATH.parent / "catalog.jsonl"
IMAGES_DIR = db.DB_PATH.parent / "images"
PLACEHOLDER_IMAGE = "static/no-image.svg"


def to_row(product):
    """Turn one catalog product into the values for one products row."""
    image = IMAGES_DIR / f"{product['asin']}.jpg"
    image_path = f"images/{product['asin']}.jpg" if image.exists() else PLACEHOLDER_IMAGE
    return (
        product["title"],
        product["description"],
        "\n".join(product["features"]),
        product["price_cents"],
        product["category"],
        image_path,
        product["rating"],
        product["times_bought"],
    )


def main():
    db.init_db()
    with CATALOG_PATH.open() as f:
        rows = [to_row(json.loads(line)) for line in f]

    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]:
            print("Products are already loaded. Delete data/buysen.db to reload.")
            return
        conn.executemany(
            """
            INSERT INTO products
                (title, description_, features, price_cents, category,
                 image_path, rating, times_bought)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        # Fill the search index from the products we just inserted.
        conn.execute("INSERT INTO products_fts(products_fts) VALUES ('rebuild')")
        conn.commit()

    placeholders = sum(row[5] == PLACEHOLDER_IMAGE for row in rows)
    print(f"Loaded {len(rows):,} products ({placeholders:,} use the placeholder image)")


if __name__ == "__main__":
    main()
"""Rebuild all recommendation data in the right order.

Run from the project root:  uv run python -m recsys.build
Add --embed to recompute the CLIP vectors even if the products haven't changed
(for example after editing titles or images).
Restart the web server afterwards so it loads the new data.
"""

import sys

import numpy as np

from app import db
from recsys import content, embed


def embeddings_up_to_date():
    """True if embeddings.npz exists and covers exactly the products in the database."""
    if not embed.EMBEDDINGS_PATH.exists():
        return False
    saved = set(np.load(embed.EMBEDDINGS_PATH)["ids"].tolist())
    current = {p["id"] for p in db.list_products(limit=-1)}
    return saved == current


def main():
    # Step 1 is slow (minutes), so it only runs when the products changed or on request.
    if "--embed" in sys.argv or not embeddings_up_to_date():
        print("Step 1/2: embedding products with CLIP (takes a few minutes)...")
        embed.main()
    else:
        print("Step 1/2: embeddings are up to date, skipping")

    print("Step 2/2: computing related items...")
    content.main()

    print("Done. Restart the web server to load the new data.")


if __name__ == "__main__":
    main()
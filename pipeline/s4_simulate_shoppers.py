"""Step 4: simulate shoppers, so the store has views and purchases to learn from.

complements_data/complements.jsonl lists, for every product, products that are
bought together with it (made once with an LLM and committed to the repo).
Each simulated shopper makes a few shopping trips. On every trip they buy one product
from a favourite category, often look at and buy its complements a few minutes later,
and view one random product as noise.

Run from the project root, after s3:  uv run python -m pipeline.s4_simulate_shoppers
"""

import json
import random
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from app import db

# --- Settings ------------------------------------------------------------------
SHOPPERS = 1000
TRIPS = (2, 6)          # shopping trips per shopper
FAVOURITES = (1, 2)     # favourite categories per shopper
VIEW_PARTNER = 0.6      # chance to look at a complement on the same trip
BUY_PARTNER = 0.5       # chance to buy it after looking
DAYS = 120              # trips are spread over the last DAYS days
SEED = 42               # same shoppers on every run
# --------------------------------------------------------------------------------

COMPLEMENTS_PATH = Path(__file__).parent.parent / "complements_data" / "complements.jsonl"
NOW = datetime(2026, 11, 20, 12, 0)  # a fixed "today", so every run makes identical data


def load_partners(product_ids):
    """product id -> ids of the products bought together with it."""
    partners = {}
    with COMPLEMENTS_PATH.open() as f:
        for line in f:
            row = json.loads(line)
            partners[row["product_id"]] = [c["id"] for c in row["complements"]]
    used = set(partners) | {p for ids in partners.values() for p in ids}
    if not used <= product_ids:
        raise SystemExit(
            "complements.jsonl doesn't match this catalog. "
            "Rebuild the catalog with the original s1 settings (TOTAL_ITEMS, SEED)."
        )
    return partners


def main():
    rng = random.Random(SEED)
    category = {p["id"]: p["category"] for p in db.list_products(limit=-1)}
    partners = load_partners(set(category))
    all_ids = sorted(category)

    # Trips start from products that have complements, grouped by category.
    starts = {}
    for product_id, ids in partners.items():
        if ids:
            starts.setdefault(category[product_id], []).append(product_id)
    categories = sorted(starts)

    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        if conn.execute("SELECT COUNT(*) FROM users WHERE name_ LIKE 'shopper-%'").fetchone()[0]:
            print("Shoppers already exist. To redo them, delete data/buysen.db and rerun s3 and s4.")
            return

        events = []
        for number in range(1, SHOPPERS + 1):
            user_id = conn.execute(
                "INSERT INTO users (name_) VALUES (?)", (f"shopper-{number:04d}",)
            ).lastrowid
            favourites = rng.sample(categories, rng.randint(*FAVOURITES))

            for _ in range(rng.randint(*TRIPS)):
                product = rng.choice(starts[rng.choice(favourites)])
                trip = [(product, "view"), (product, "buy")]
                for partner in partners[product]:
                    if rng.random() < VIEW_PARTNER:
                        trip.append((partner, "view"))
                        if rng.random() < BUY_PARTNER:
                            trip.append((partner, "buy"))
                trip.append((rng.choice(all_ids), "view"))  # noise: random browsing

                # Each action happens a few minutes after the previous one.
                clock = NOW - timedelta(days=rng.uniform(0, DAYS))
                for product_id, kind in trip:
                    clock += timedelta(minutes=rng.randint(1, 5))
                    events.append((user_id, product_id, kind, clock.strftime("%Y-%m-%d %H:%M:%S")))

        conn.executemany(
            "INSERT INTO events (user_id, product_id, kind, created_at) VALUES (?, ?, ?, ?)",
            events,
        )
        conn.commit()

    buys = sum(kind == "buy" for _, _, kind, _ in events)
    print(f"Simulated {SHOPPERS:,} shoppers: {len(events):,} events ({buys:,} purchases)")


if __name__ == "__main__":
    main()
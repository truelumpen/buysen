"""Step 1: download a stratified random sample of products from Amazon Reviews 2023.

Each category gets a share of TOTAL_ITEMS proportional to how many usable
products it really has, and products are picked uniformly at random inside
each category (reservoir sampling), so the sample mirrors the real catalog.
Every category file is read exactly once.
Output: data/catalog.jsonl (one product per line).
"""

import gzip
import json
import random
from pathlib import Path

import requests
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"
CATALOG_PATH = DATA_DIR / "catalog.jsonl"
BASE_URL = (
    "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023"
    "/raw/meta_categories/meta_{}.jsonl.gz"
)
CATEGORIES = {
    "Electronics": "Electronics",
    "Home_and_Kitchen": "Home & Kitchen",
    "Clothing_Shoes_and_Jewelry": "Clothing",
    "Sports_and_Outdoors": "Sports & Outdoors",
    "Toys_and_Games": "Toys & Games",
    "Beauty_and_Personal_Care": "Beauty & Personal Care",
    "Cell_Phones_and_Accessories": "Cell Phones & Accessories",
    "Tools_and_Home_Improvement": "Tools & Home Improvement",
    "Office_Products": "Office Products",
    "Pet_Supplies": "Pet Supplies",
}
TOTAL_ITEMS = 5_000
SEED = 42


def to_product(raw, category):
    """Return a clean product, or None if the item is missing something we need."""
    try:
        price = float(raw.get("price"))
    except (TypeError, ValueError):
        return None
    images = [image["large"] for image in raw.get("images") or [] if image.get("large")]
    if not raw.get("title") or price <= 0 or not images:
        return None

    # Amazon's number of ratings stands in for how many times the product was bought.
    times_bought = int(raw.get("rating_number") or 0)
    rating = raw.get("average_rating")
    if times_bought == 0 or rating is None or not 1 <= rating <= 5:
        rating = None

    # Keep both: the description text and the "About this item" bullet points.
    description = "\n".join(raw.get("description") or []).strip()
    features = [bullet.strip() for bullet in raw.get("features") or [] if bullet.strip()]

    return {
        "asin": raw["parent_asin"],
        "title": raw["title"].strip(),
        "description": description,
        "features": features,
        "price_cents": round(price * 100),
        "category": category,
        "rating": rating,
        "times_bought": times_bought,
        "image_url": images[0],
    }


def sample_category(file_name, category, k, rng):
    """Stream a whole category file once and return (sample, usable).

    The goal is a random catalog of TOTAL_ITEMS products whose category mix
    matches the real dataset, which is called stratified sampling.

    Inside one category we use reservoir sampling. We keep the first k usable
    products. After that, for the n-th usable product (counting from 0) we pick
    a random slot between 0 and n, and if that slot is below k the new product
    replaces whatever is in it. In the end every product has the same chance
    of being kept, and we never hold the whole file in memory.

    main() then stratifies by category. It gives each category a quota equal
    to TOTAL_ITEMS times that category's share of all usable products, and
    randomly picks that many products from the category's reservoir. A random
    subset of a random sample is still random.

    The whole file must be read even for a small sample, because a fair pick
    needs every item to have a chance. SEED makes the result repeatable.
    """
    sample = []
    usable = 0
    with requests.get(BASE_URL.format(file_name), stream=True, timeout=60) as response:
        response.raise_for_status()
        size = int(response.headers["Content-Length"])
        with (
            tqdm.wrapattr(response.raw, "read", total=size, desc=category) as raw,
            gzip.open(raw, "rt", encoding="utf-8") as lines,
        ):
            for line in lines:
                product = to_product(json.loads(line), category)
                if product is None:
                    continue
                if usable < k:
                    sample.append(product)
                else:
                    slot = rng.randrange(usable + 1)
                    if slot < k:
                        sample[slot] = product
                usable += 1
    return sample, usable


def main():
    rng = random.Random(SEED)
    samples = {}
    usable = {}
    for file_name, category in CATEGORIES.items():
        samples[category], usable[category] = sample_category(file_name, category, TOTAL_ITEMS, rng)

    total_usable = sum(usable.values())
    catalog = []
    seen = set()
    for category, sample in samples.items():
        share = usable[category] / total_usable
        quota = min(round(TOTAL_ITEMS * share), len(sample))
        chosen = [p for p in rng.sample(sample, quota) if p["asin"] not in seen]
        seen.update(p["asin"] for p in chosen)
        catalog.extend(chosen)
        print(f"{category}: {len(chosen):,} items ({share:.1%} of {total_usable:,} usable)")

    DATA_DIR.mkdir(exist_ok=True)
    with CATALOG_PATH.open("w") as out:
        for product in catalog:
            out.write(json.dumps(product) + "\n")
    print(f"Saved {len(catalog):,} products to {CATALOG_PATH}")


if __name__ == "__main__":
    main()
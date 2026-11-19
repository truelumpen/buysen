"""Phase 4 benchmark, step 1: a toy catalog with Amazon's own recommendations.

Downloads the 2018 Amazon Reviews release (Toys & Games):
  - ratings, which collaborative filtering learns from
  - product metadata, including Amazon's "Customers also viewed" (also_view) and
    "Customers also bought" (also_buy) lists: the answers we compare against.
Keeps the CATALOG_SIZE most-rated toys, downloads their images and embeds them with CLIP.

Run from the project root:  uv run python -m benchmark.prepare
Output in data/benchmark/: products.jsonl, ratings.csv, images/, embeddings.npz
"""

import gzip
import html
import io
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from recsys import embed

# --- Settings ------------------------------------------------------------------
CATALOG_SIZE = 5_000   # the most-rated toys that form the benchmark catalog
SHORTLIST = 30_000     # most-rated products whose metadata we look at (most get filtered out)
WORKERS = 16           # parallel image downloads
# --------------------------------------------------------------------------------

BASE_URL = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_v2"
RATINGS_URL = f"{BASE_URL}/categoryFilesSmall/Toys_and_Games.csv"
META_URL = f"{BASE_URL}/metaFiles2/meta_Toys_and_Games.json.gz"
OUT_DIR = Path(__file__).parent.parent / "data" / "benchmark"
IMAGES_DIR = OUT_DIR / "images"


def stream_lines(url, label, gzipped):
    """Download a file and yield its lines one by one, without saving it to disk."""
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        size = int(response.headers["Content-Length"])
        # Don't let the connection close itself at the end of the data; the text reader
        # below still needs it, and the `with` block closes it anyway.
        response.raw.auto_close = False
        with tqdm.wrapattr(response.raw, "read", total=size, desc=label) as raw:
            if gzipped:
                lines = gzip.open(raw, "rt", encoding="utf-8")
            else:
                lines = io.TextIOWrapper(raw, encoding="utf-8")
            yield from lines


def count_ratings():
    """Pass 1 over the ratings: how many ratings each product has."""
    counts = Counter()
    for line in stream_lines(RATINGS_URL, "Ratings (count)", gzipped=False):
        counts[line.split(",", 1)[0]] += 1  # each line: product,user,rating,time
    return counts


def read_products(shortlist):
    """Metadata of shortlisted products that have a title, an image and an Amazon list."""
    products = {}
    for line in stream_lines(META_URL, "Product metadata", gzipped=True):
        raw = json.loads(line)
        asin = raw["asin"]
        if asin not in shortlist or asin in products:  # the file repeats some products
            continue
        title = html.unescape(raw.get("title", "")).strip()  # "&amp;" -> "&"
        images = raw.get("imageURLHighRes") or []
        if not title or len(title) > 300 or not images:  # very long titles are page junk
            continue
        if not (raw.get("also_view") or raw.get("also_buy")):
            continue
        products[asin] = {
            "asin": asin,
            "title": title,
            "features": [html.unescape(f).strip() for f in raw.get("feature") or [] if f.strip()],
            "image_url": images[0],
            "also_view": raw.get("also_view") or [],
            "also_buy": raw.get("also_buy") or [],
        }
    return products


def save_ratings(catalog):
    """Pass 2 over the ratings: keep only ratings of catalog products."""
    kept = 0
    with (OUT_DIR / "ratings.csv").open("w") as out:
        out.write("asin,user,rating,timestamp\n")
        for line in stream_lines(RATINGS_URL, "Ratings (keep)", gzipped=False):
            if line.split(",", 1)[0] in catalog:
                out.write(line if line.endswith("\n") else line + "\n")
                kept += 1
    return kept


def download_image(product):
    """Save one product image; returns True if the file exists afterwards."""
    path = IMAGES_DIR / f"{product['asin']}.jpg"
    if not path.exists():
        try:
            response = requests.get(product["image_url"], timeout=30)
            response.raise_for_status()
            path.write_bytes(response.content)
        except requests.RequestException:
            return False
    return True


def save_embeddings(products, has_image):
    """CLIP text and image vectors for every catalog product, in catalog order."""
    model = SentenceTransformer(embed.MODEL_NAME)
    model.max_seq_length = 77
    texts = [embed.product_text({"title": p["title"], "features": "\n".join(p["features"])}) for p in products]
    text = model.encode(texts, batch_size=embed.BATCH_SIZE, normalize_embeddings=True, show_progress_bar=True)
    image = np.zeros_like(text)
    paths = [IMAGES_DIR / f"{p['asin']}.jpg" for p, has in zip(products, has_image) if has]
    image[has_image] = embed.embed_images(model, paths)
    np.savez(
        OUT_DIR / "embeddings.npz",
        asins=np.array([p["asin"] for p in products]),
        text=text,
        image=image,
        has_image=has_image,
    )


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)

    counts = count_ratings()
    shortlist = {asin for asin, _ in counts.most_common(SHORTLIST)}
    candidates = read_products(shortlist)

    # The catalog: the most-rated candidates.
    top = sorted(candidates, key=counts.get, reverse=True)[:CATALOG_SIZE]
    catalog = set(top)
    products = []
    for asin in top:
        product = candidates[asin]
        # Amazon's lists, trimmed to products we could actually recommend.
        product["also_view"] = [a for a in product["also_view"] if a in catalog and a != asin]
        product["also_buy"] = [a for a in product["also_buy"] if a in catalog and a != asin]
        product["n_ratings"] = counts[asin]
        products.append(product)

    kept = save_ratings(catalog)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        has_image = np.array(list(tqdm(pool.map(download_image, products), total=len(products), desc="Images")))

    save_embeddings(products, has_image)

    with (OUT_DIR / "products.jsonl").open("w") as out:
        for product in products:
            out.write(json.dumps(product) + "\n")

    with_view = sum(bool(p["also_view"]) for p in products)
    with_buy = sum(bool(p["also_buy"]) for p in products)
    print(f"Catalog: {len(products):,} toys, {kept:,} ratings, {int(has_image.sum()):,} images")
    print(f"Amazon lists inside the catalog: also_view for {with_view:,}, also_buy for {with_buy:,}")


if __name__ == "__main__":
    main()
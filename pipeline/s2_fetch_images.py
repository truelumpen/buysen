"""Step 2: download one image per product in data/catalog.jsonl.

Saves each image as data/images/{asin}.jpg. Images that already exist are
skipped, so the script can safely be rerun after a crash or a failed download.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"
CATALOG_PATH = DATA_DIR / "catalog.jsonl"
IMAGES_DIR = DATA_DIR / "images"
WORKERS = 16


def download(product):
    """Download one product image. Returns the asin if it failed, otherwise None."""
    path = IMAGES_DIR / f"{product['asin']}.jpg"
    if path.exists():
        return None
    try:
        response = requests.get(product["image_url"], timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        return product["asin"]
    # Write to a temporary name first, so a half-written file never looks finished.
    temp_path = path.with_suffix(".part")
    temp_path.write_bytes(response.content)
    temp_path.rename(path)
    return None


def main():
    with CATALOG_PATH.open() as f:
        products = [json.loads(line) for line in f]
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # A pool of threads to execute calls asynchronously.
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(tqdm(pool.map(download, products), total=len(products), desc="Images"))

    failed = [asin for asin in results if asin]
    print(f"Images ready for {len(products) - len(failed):,} of {len(products):,} products")
    if failed:
        print(f"Failed ({len(failed)}): {', '.join(failed[:10])}")


if __name__ == "__main__":
    main()
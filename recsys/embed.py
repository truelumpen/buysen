"""Phase 3, step 1: turn every product into vectors with CLIP.

Each product gets two 512-number vectors in CLIP's shared "meaning space":
  - a text vector, from its title and first few feature bullets
  - an image vector, from its product photo (left as zeros if it has no real image)
Similar products get similar vectors, so similarity becomes simple maths.

Run from the project root:  uv run python -m recsys.embed
Output: data/embeddings.npz (ids, text, image, has_image), rows in the same order.
"""

from functools import cache

import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer

from app import db

MODEL_NAME = "clip-ViT-B-32"
EMBEDDINGS_PATH = db.DB_PATH.parent / "embeddings.npz"
FEATURES_IN_TEXT = 3  # CLIP only reads ~77 tokens, so keep the text short
BATCH_SIZE = 32

@cache
def load_model():
    """The CLIP model, loaded once per process and kept in memory."""
    model = SentenceTransformer(MODEL_NAME)
    # CLIP's text side stops at 77 tokens; longer text is cut off, not rejected.
    model.max_seq_length = 77
    return model


@cache
def load_embeddings():
    """The saved vectors, read once per process and shared by every recsys module.
    None if this script hasn't run yet. Restart the server after re-embedding."""
    if not EMBEDDINGS_PATH.exists():
        return None
    data = np.load(EMBEDDINGS_PATH)
    return {
        "ids": [int(i) for i in data["ids"]],
        "text": data["text"],
        "image": data["image"],
        "has_image": data["has_image"],
    }

    
def product_text(product):
    """Title plus the first few feature bullets: the most informative words first."""
    bullets = [b for b in product["features"].split("\n") if b][:FEATURES_IN_TEXT]
    return ". ".join([product["title"], *bullets])


def embed_images(model, paths):
    """Embed images in small batches, so only a few photos are open in memory at once."""
    vectors = []
    for start in range(0, len(paths), BATCH_SIZE):
        images = [Image.open(path).convert("RGB") for path in paths[start : start + BATCH_SIZE]]
        vectors.append(model.encode(images, normalize_embeddings=True))
        for image in images:
            image.close()
        print(f"Images: {min(start + BATCH_SIZE, len(paths))}/{len(paths)}", end="\r")
    print()
    return np.vstack(vectors)


def main():
    products = db.list_products(limit=-1) # All products
    ids = np.array([p["id"] for p in products])
    image_files = [db.DB_PATH.parent / p["image_path"] for p in products]
    # The "No image" placeholder lives in static/, real photos in data/images/.
    has_image = np.array([p["image_path"].startswith("images/") for p in products])

    model = load_model()

    text = model.encode(
        [product_text(p) for p in products],
        batch_size=BATCH_SIZE,
        normalize_embeddings=True, # every vector gets length 1, so similarity is just a dot product (cosine similarity).
        show_progress_bar=True,
    )

    image = np.zeros_like(text)
    real = [path for path, has in zip(image_files, has_image) if has]
    image[has_image] = embed_images(model, real)

    np.savez(EMBEDDINGS_PATH, ids=ids, text=text, image=image, has_image=has_image)
    print(f"Saved {len(ids):,} products ({has_image.sum():,} with images) to {EMBEDDINGS_PATH}")


if __name__ == "__main__":
    main()
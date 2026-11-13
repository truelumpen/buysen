"""Phase 3, step 2: Related items by content similarity.

For every product, find the TOP_K products whose CLIP vectors are closest and save
them to similar_items with method='content'. When both products have a real photo
they are compared mostly by image; if either has no photo, by text only.

Run from the project root:  uv run python -m recsys.content
Needs data/embeddings.npz, written by recsys.embed.
"""

import numpy as np

from app import db

EMBEDDINGS_PATH = db.DB_PATH.parent / "embeddings.npz"
IMAGE_WEIGHT = 0.1  # share of image similarity when both products have a photo
TOP_K = 30


def similarity_matrix(text, image, has_image, image_weight=IMAGE_WEIGHT):
    """Similarity of every product (rows) to every product (columns)."""
    # The vectors have length 1, so a dot product is the cosine similarity.
    text_sim = text @ text.T
    image_sim = image @ image.T
    both_have_images = has_image[:, None] & has_image[None, :]
    blended = image_weight * image_sim + (1 - image_weight) * text_sim
    return np.where(both_have_images, blended, text_sim)


def top_k(similarity, k=TOP_K):
    """For each row, the column positions of its k highest scores, best first."""
    similarity = similarity.copy()
    np.fill_diagonal(similarity, -np.inf)  # a product is never related to itself
    # argpartition finds the k best without fully sorting each row; then sort only those k.
    best = np.argpartition(-similarity, k, axis=1)[:, :k]
    scores = np.take_along_axis(similarity, best, axis=1)
    order = np.argsort(-scores, axis=1)
    return np.take_along_axis(best, order, axis=1)


def main():
    data = np.load(EMBEDDINGS_PATH)
    ids = data["ids"]
    similarity = similarity_matrix(data["text"], data["image"], data["has_image"])
    neighbours = top_k(similarity)

    # One row per (product, related product): its id, score and rank 1..TOP_K.
    rows = [
        (int(ids[i]), int(ids[j]), float(similarity[i, j]), rank)
        for i in range(len(ids))
        for rank, j in enumerate(neighbours[i], start=1)
    ]
    db.replace_similar("content", rows)
    print(f"Saved {TOP_K} related items for each of {len(ids):,} products")


if __name__ == "__main__":
    main()
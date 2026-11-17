"""Measuring functions for recommendations.

Pure functions: no database and no model, so they are quick to test by hand.
`neighbours` is always a 2-D array where row i holds the positions of product i's
related products, best first; `categories` holds one category per position.
"""

import numpy as np


# Whats the chance that a pair of related products are from the same category
def category_agreement(neighbours, categories, k):
    """Share of each product's top-k related products that are in its own category."""
    top = neighbours[:, :k]
    return float((categories[top] == categories[:, None]).mean())


# Are some items underrepresented in the search and others dominate
def coverage(neighbours, n_products):
    """Share of the catalog that appears in at least one product's related list."""
    return len(np.unique(neighbours)) / n_products
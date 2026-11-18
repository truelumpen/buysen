"""The evaluation metrics compute exactly what they claim, on hand-worked examples."""

import numpy as np
import pytest

from recsys.metrics import category_agreement, coverage

# A tiny catalog: products 0 and 1 are Pet, product 2 is Toys.
CATEGORIES = np.array(["Pet", "Pet", "Toys"])
# Row i = product i's related products, best first.
NEIGHBOURS = np.array([[1, 2], [0, 2], [0, 1]])


def test_category_agreement_top_1():
    # Best related item: 0 -> 1 (Pet, match), 1 -> 0 (Pet, match), 2 -> 0 (Pet vs Toys, miss).
    assert category_agreement(NEIGHBOURS, CATEGORIES, k=1) == pytest.approx(2 / 3)


def test_category_agreement_top_2():
    # Matches among all six pairs: only the two above.
    assert category_agreement(NEIGHBOURS, CATEGORIES, k=2) == pytest.approx(2 / 6)


def test_coverage_every_product_shown():
    assert coverage(NEIGHBOURS, n_products=3) == 1.0


def test_coverage_one_product_never_shown():
    # Product 0 appears in nobody's list, so only 2 of 3 products are covered.
    assert coverage(np.array([[1, 2], [2, 1], [1, 2]]), n_products=3) == pytest.approx(2 / 3)
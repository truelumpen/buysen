# Cloneazon evaluation (Phase 3)

Generated 2026-11-20 by `uv run python -m benchmark.evaluate` on 4,999 products. Random choices use seed 42.

## 1. Related items

For every product, its top 10 related items. *Same category @k*: share of the top k that are in the product's own category. *Coverage*: share of the catalog that appears in anyone's related list (low = the same few products everywhere).

| IMAGE_WEIGHT | Same category @1 | Same category @10 | Coverage |
|---|---|---|---|
| 1.0 | 60% | 55% | 93% |
| 0.7 | 73% | 64% | 94% |
| 0.5 | 77% | 68% | 95% |
| 0.3 | 78% | 70% | 95% |
| 0.1 (current) | 79% | 70% | 96% |
| 0.0 | 79% | 70% | 96% |

Category is a rough proxy for relevance: a phone case under a phone counts as a miss if they sit in different categories, and a dog leash under a cat bowl counts as a hit.

## 2. Personalization (simulated users)

Each simulated user views 5 random products from one category. We then check how many of their top 10 *Items for You* come from that category, compared with *Popular items*, which ignore the user.

| Simulated user viewed 5 products from | Items for You in that category | Popular items in that category |
|---|---|---|
| Beauty & Personal Care | 100% | 10% |
| Cell Phones & Accessories | 100% | 30% |
| Clothing | 100% | 0% |
| Electronics | 80% | 10% |
| Home & Kitchen | 90% | 0% |
| Office Products | 90% | 20% |
| Pet Supplies | 100% | 10% |
| Sports & Outdoors | 30% | 0% |
| Tools & Home Improvement | 70% | 0% |
| Toys & Games | 70% | 20% |
| **Average** | **83%** | **10%** |

Simulated users are not real shoppers; this checks that personalization adapts, not that people would buy what it shows.

## 3. Search by meaning

Matches above MIN_SIMILARITY = 0.27 (QUERY_IMAGE_WEIGHT = 1.0). Keyword matches are not counted here.

| Query | Type | Meaning matches | Best meaning match |
|---|---|---|---|
| gift for a gamer | real | 12 | Fischertechnik Dynamic M Set |
| something to keep my dog busy | real | 25 | Durable Dog Toys for Aggressive Chewers, Indestructible Dog  |
| cozy winter outfit | real | 5 | Century Star Women's Fuzzy Hoodies Sport Pullover Hoodie Ath |
| kitchen gadgets | real | 36 | MegaChoice Stainless Steel Pot Rack with Shelf & 6pcs Hooks  |
| toys for toddlers | real | 18 | Wooden Baby Toys Activity Cube 6-in-1 Play Center Bead Maze  |
| hiking gear | real | 6 | WEPLAN Skateboard Backpack for Men,Water Resistant Laptop Ba |
| office desk organizer | real | 33 | Orcaa Multi-Function Pen Holder / Modern Desk Lamp with USB  |
| zzzzqqq | nonsense | 1 | Chubby Spotted Seal Pillow Stuffed Cotton Plush Animal Toy C |
| asdf jkl | nonsense | 0 | none |
| xkcd lorem ipsum | nonsense | 0 | none |

## 4. People buy with (co-purchases)

complements_data/complements.jsonl lists which products go together; the simulated shoppers (pipeline/s4) bought along those pairs, plus random noise. For every product that has complements, we take a row of 5 and check how many true complements it shows.

| Row of 5 from | Rows with a true complement | Shown products that are complements |
|---|---|---|
| People buy with (complements, then their related items) | 50% | 19% |
| Complements only (same-trip co-purchases) | 50% | 18% |
| Related items (similar products) | 27% | 7% |
| Random products | 1% | 0% |

The shoppers were generated from these pairs, so this shows the method recovers the pattern in the data, not how real shoppers would behave. Similar products (Related items) are a useful contrast: they rarely are complements.

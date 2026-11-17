# Cloneazon evaluation (Phase 3)

Generated 2026-11-16 by `uv run python -m recsys.evaluate` on 3,000 products. Random choices use seed 42.

## 1. Related items

For every product, its top 10 related items. *Same category @k*: share of the top k that are in the product's own category. *Coverage*: share of the catalog that appears in anyone's related list (low = the same few products everywhere).

| IMAGE_WEIGHT | Same category @1 | Same category @10 | Coverage |
|---|---|---|---|
| 1.0 | 60% | 54% | 93% |
| 0.7 | 71% | 63% | 94% |
| 0.5 | 76% | 66% | 95% |
| 0.3 | 78% | 67% | 96% |
| 0.1 (current) | 79% | 67% | 97% |
| 0.0 | 78% | 67% | 97% |

Category is a rough proxy for relevance: a phone case under a phone counts as a miss if they sit in different categories, and a dog leash under a cat bowl counts as a hit.

## 2. Personalization (simulated users)

Each simulated user views 5 random products from one category. We then check how many of their top 10 *Items for You* come from that category, compared with *Popular items*, which ignore the user.

| Simulated user viewed 5 products from | Items for You in that category | Popular items in that category |
|---|---|---|
| Beauty & Personal Care | 90% | 10% |
| Cell Phones & Accessories | 100% | 0% |
| Clothing | 90% | 10% |
| Electronics | 40% | 10% |
| Home & Kitchen | 80% | 30% |
| Office Products | 70% | 10% |
| Pet Supplies | 30% | 10% |
| Sports & Outdoors | 50% | 0% |
| Tools & Home Improvement | 70% | 10% |
| Toys & Games | 100% | 10% |
| **Average** | **72%** | **10%** |

Simulated users are not real shoppers; this checks that personalization adapts, not that people would buy what it shows.

## 3. Search by meaning

Matches above MIN_SIMILARITY = 0.27 (QUERY_IMAGE_WEIGHT = 1.0). Keyword matches are not counted here.

| Query | Type | Meaning matches | Best meaning match |
|---|---|---|---|
| gift for a gamer | real | 8 | FORTNITE Beanie Boys Kids Teens Official Battle Royale Gamin |
| something to keep my dog busy | real | 20 | Garifulsty Indestructible Dog Puppy Treat Dispenser Interact |
| cozy winter outfit | real | 1 | Dokotoo Womens 2023 Solid Color Casual Fleece Fluffy Crewnec |
| kitchen gadgets | real | 18 | Lanyihome Multifuctional 2 in 1 Small Silicone Pet Food Can  |
| toys for toddlers | real | 16 | CifToys Push and Go Friction Powered Car Toys for Boys - Con |
| hiking gear | real | 7 | Skip Work Extra Large Mesh Beach Bag with Drawstring Accesso |
| office desk organizer | real | 27 | Cisily Toilet Paper Holder with Shelf and Storage, Stainless |
| zzzzqqq | nonsense | 0 | none |
| asdf jkl | nonsense | 0 | none |
| xkcd lorem ipsum | nonsense | 0 | none |

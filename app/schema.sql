-- Cloneazon data model: every table the project uses.

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY,
    title       TEXT    NOT NULL,
    description_ TEXT    NOT NULL DEFAULT '',
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    category    TEXT    NOT NULL,
    image_path  TEXT    NOT NULL,
    rating      REAL    CHECK (rating BETWEEN 1 AND 5),
    times_bought INTEGER NOT NULL DEFAULT 0 CHECK (times_bought >= 0),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY,
    name_        TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    kind       TEXT    NOT NULL CHECK (kind IN ('view', 'buy')),
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    user_id    INTEGER NOT NULL REFERENCES users(id),
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    text_      TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS similar_items (
    product_id INTEGER NOT NULL REFERENCES products(id),
    similar_id INTEGER NOT NULL REFERENCES products(id),
    method     TEXT    NOT NULL CHECK (method IN ('content', 'collaborative', 'hybrid')),
    score      REAL    NOT NULL,
    rank       INTEGER NOT NULL,
    PRIMARY KEY (product_id, method, rank)
);

-- Full-text search index over product text. "External content" means it reads
-- title and description_ straight from products and stores only a word index,
-- so no data is duplicated. Rebuild it after loading products:
--   INSERT INTO products_fts(products_fts) VALUES ('rebuild');
CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
    title,
    description_,
    content = 'products',
    content_rowid = 'id',
    tokenize = 'porter unicode61'
);

CREATE INDEX IF NOT EXISTS idx_events_user      ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_product  ON reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_products_popular ON products(times_bought);
#!/bin/sh
# Container start: make sure data/ is filled, then run the website.
set -e

DATA_URL="https://github.com/truelumpen/buysen/releases/download/data-v1/buysen-data-v1.tar.gz"

# First start only: the prebuilt database, embeddings and catalog (29 MB).
if [ ! -f data/buysen.db ]; then
    echo "First start: downloading prebuilt data..."
    curl -fsSL "$DATA_URL" | tar -xz
fi

# Product photos: about 5 minutes the first time, then it skips the ones already saved.
python pipeline/s2_fetch_images.py

# 0.0.0.0 makes the server reachable from outside the container.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
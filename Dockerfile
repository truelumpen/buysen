# Buysen: the store and its recommenders, ready to run anywhere.
#   docker build -t buysen .
#   docker run -p 8000:8000 -v buysen-data:/app/data buysen

# Python 3.12 with uv already installed.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# curl downloads the prebuilt data on first start (see start.sh).
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first: Docker reuses this slow layer as long as these two files don't change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

# Download CLIP into the image, so the running container never contacts Hugging Face.
ENV HF_HOME=/app/hf-cache
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('clip-ViT-B-32')"
ENV HF_HUB_OFFLINE=1

# The code. data/ is not copied: start.sh fills it on first start.
COPY app ./app
COPY pipeline ./pipeline
COPY recsys ./recsys
COPY complements_data ./complements_data
COPY start.sh ./

EXPOSE 8000
CMD ["./start.sh"]
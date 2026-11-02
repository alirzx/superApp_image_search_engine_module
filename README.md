# SuperApp Module 4: Image Search Engine

CPU-only, private, standalone image-retrieval service for **two** user-facing search modes:

- **Image → Image:** upload a query image to retrieve semantically similar indexed images.
- **Text → Image:** search the same index with English or Persian text.

There is deliberately **no duplicate detection, image generation, hybrid retrieval, face recognition, or OCR search** in v0.1. Upload/collection/indexing operations are supporting infrastructure, not extra user-facing AI search modes.

## Architecture

```
React/Vite (RTL) → Nginx /api → FastAPI (X-API-Key)
                                       │
                        ┌──────────────┴──────────────┐
                        │                             │
                  Ingest images                  Query search
                        │                       (image OR text)
                 SQLite job queue                     │
                        │                             │
                CPU dual encoder <────────────────────┘
                        │                             │
                 normalized vectors               query vector
                        │                             │
                SQLite embedding BLOB ──────> FAISS inner-product search
                        │                             │
                    .webp media                ranked thumbnail IDs
```

**Source of truth:** SQLite. Its embedding BLOBs are reloaded into FAISS at every startup; FAISS snapshots are derived caches. This avoids a corrupt/restarted process claiming that a vector has been indexed when it hasn't. One API process and one indexing worker are required in this baseline. No Redis, Qdrant or PostgreSQL required.

## Model

`google/siglip2-base-patch32-256`, CPU FP32 via Hugging Face Transformers. Original weights are **not included**. The model has permissive Apache-2.0 metadata, but verify the license and model revision independently before commercial release. Image and text features are L2-normalized into the same embedding space; FAISS `IndexFlatIP` performs exact cosine-equivalent similarity search. Returned scores are **not probabilities**. Persian quality is **not yet benchmarked**. This repository supports the selected candidate only; it does not silently swap models.

The source model's Hugging Face `config.json` identifies a `siglip` model_type despite the SigLIP2 checkpoint name. The adapter intentionally uses `AutoModel` and extracts pooled embeddings from the class actually resolved by Transformers. See [MODEL.md](docs/MODEL.md).

## Quick start (Ubuntu/Linux)

**Requirements:** Python 3.11 to download the model, Docker Engine + Docker Compose v2, ~3GB free disk for weights/cache, and sufficient CPU/RAM. The example 6GB memory limit has **not** been validated with real inference on the target server.

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(36))'
# Put the generated token in API_KEY= in .env (DO NOT commit)
./scripts/prepare_local.sh
# Set RUN_UID / RUN_GID in .env to the values printed above.
python3 -m venv .venv
. .venv/bin/activate
pip install 'huggingface_hub==0.30.2'
python scripts/download_model.py --output .models/siglip2
python scripts/verify_model.py --path .models/siglip2
# Set MODEL_REVISION in .env to the SHA printed by the downloader.
docker compose config --quiet
docker compose build
docker compose up -d
```

Visit **http://127.0.0.1:8085**, enter the API key in the connection panel and choose a collection. Upload JPG/PNG/WebP images, watch their indexing jobs finish, then run image or Persian/English text searches. Swagger/OpenAPI is available locally at **http://127.0.0.1:8004/docs** (do not expose on a public interface without an appropriate gateway).

**Model download is deliberately explicit and separate from Docker builds.** Production runtime uses `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. If the model is absent, `/health/live` returns 200, `/health/ready` returns 503 and protected inference calls fail until the model is installed and the API restarted.

### CLI smoke

```bash
set -a; . ./.env; set +a
python scripts/smoke_test.py --url http://127.0.0.1:8004
curl -H "X-API-Key: $API_KEY" http://127.0.0.1:8004/v1/collections
curl -H "X-API-Key: $API_KEY" -F collection_id=default \
  -F file=@example.jpg http://127.0.0.1:8004/v1/images
# Poll returned job_id until completed.
curl -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"collection_id":"default","query":"یک گربه سفید روی مبل","top_k":5}' \
  http://127.0.0.1:8004/v1/search/text
curl -H "X-API-Key: $API_KEY" -F collection_id=default -F top_k=5 \
  -F file=@query.jpg http://127.0.0.1:8004/v1/search/image
```

For complete contracts see [API.md](docs/API.md), and for deployment see [DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Local tests (no model download)

```bash
python -m pip install -r backend/requirements-ci.txt
PYTHONPATH=backend pytest -q backend/tests
```

The tests inject a deterministic **fake encoder** and use a test-only NumPy index adapter. These verify API behavior and persistence, **not SigLIP2 inference quality or FAISS native bindings**. Real CPU benchmarks and container builds remain mandatory before release. See [TESTING.md](docs/TESTING.md).

## Layout

| Path | Contents |
|---|---|
| `backend/app/api/` | API payload schemas |
| `backend/app/inference/` | CPU SigLIP2 adapter; embedding protocol |
| `backend/app/processing/` | Image validation, EXIF handling, canonical WebP/thumbnail |
| `backend/app/storage/` | SQLite repository, private object files, FAISS adapter |
| `backend/app/services/` | Ingestion, search and durable indexing worker |
| `frontend/` | React + vanilla CSS + TypeScript, RTL |
| `scripts/` | Offline model download/checksum, smoke test |
| `ops/` | Nginx config |
| `docs/` | Architecture, API, model, operations and security |

## Operational boundaries

The baseline is **single-instance and single-tenant** using one shared API key. Collections separate datasets but are **not** per-user access-control boundaries. DO NOT expose it as a public multi-user SaaS without per-principal authentication, authorization and quota isolation. It supports small and medium catalogs, not unbounded enterprise ingest, and needs measured capacity planning. No actual server deployment has been performed by this deliverable.

## Model and project license

Project source is Apache-2.0. Pretrained weights and third-party packages retain their respective licenses and terms; check and record all of them at deployment. The model is fetched independently at a pinned upstream commit.

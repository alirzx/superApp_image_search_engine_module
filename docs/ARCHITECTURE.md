# Architecture and workflows

## Scope
Only two search features: image-to-image and text-to-image. Upload, indexing, collections, media delivery and deletion support those two features. No duplicate search or hybrid search in v0.1.

## Components

1. FastAPI + Pydantic controls HTTP contracts and `X-API-Key` authentication.
2. Pillow validates and canonicalizes JPEG/PNG/WebP files to WebP (EXIF stripped); a 360px thumbnail is generated.
3. A SQLite `jobs` table is a durable, ordered ingestion queue. At boot, `processing` jobs are returned to `queued`.
4. A single background coroutine takes jobs and uses `asyncio.to_thread` for CPU inference, guarded by a lock shared with incoming queries.
5. The SigLIP2 CPU provider loads only a locally verified checkpoint, implements image/text feature extraction and L2 normalization.
6. SQLite transactionally stores each embedding as float32 bytes and marks the image `ready`. FAISS `IndexIDMap2(IndexFlatIP)` indexes these vectors per collection. Its snapshots are derived, not authoritative.
7. On startup the in-memory FAISS index is rebuilt from SQLite, avoiding snapshot/metadata divergence.
8. The frontend calls `/api/...` via Nginx proxy, which strips `/api`. It stores the API token in sessionStorage only. Private thumbnails are requested through authorized `fetch` and displayed with temporary blob URLs. The API key is never embedded in image URLs.

## Image ingestion

```
Upload → auth → collection check → byte/pixel/type validation
       → orientation + alpha composition → canonical WebP and thumbnail
       → insert image + queued job (SQLite transaction) → 202 response
       → worker → image preprocessing → vision encoder → normalized embedding
       → embedding insert + ready flag (SQLite transaction)
       → FAISS update (rebuild on failure) → searchable
```

The main request does not block for model inference. Job results are retrieved at `/v1/jobs/{job_id}`. Worker failures are recorded with a bounded error message, without content logs. On interrupted processes, queued and in-progress jobs survive in SQLite. The one-process rule prevents two workers from competing for the same job; horizontal scaling needs an upgraded queue and storage design.

## Image search

```
Multipart image → validate → decode/exif/RGB → vision encoder
                → L2-normalized query → scoped FAISS cosine search
                → resolve ready metadata in SQLite → ranked results
```

## Text search

```
Persian/English string → validate/trim → checkpoint tokenizer
                       → text encoder → L2-normalized query
                       → collection-scoped FAISS → ranked results
```

Minimal text normalization avoids damaging model/tokenizer semantics. The same model checkpoint **must** encode indexed images and query text. Scores are cosine similarities, not probabilities of matches. The API does not translate Persian into English, and no external AI API is needed.

## Index consistency and model versioning

- Primary source: `embeddings.vector` in SQLite, with model signature and dimension.
- FAISS snapshots: rebuilt and overwritten at startup, and occasionally refreshed during indexing; no deployment should rely only on snapshots.
- Updates are scoped by collection and use stable SQLite `vector_id` values.
- After a crash between transaction commit and FAISS update, startup rebuild recovers the missing entry.
- An incompatible model signature fails initialization instead of mixing vectors.
- Model changes require an explicit reindex procedure (not automated in v0.1). Back up the dataset, create a new storage volume/index, index the originals, validate, then switch over.
- Queries arriving while indexing see only committed, ready images. An index-update failure triggers an immediate rebuild, or readiness becomes unavailable.

## Known boundaries

- One service process; single writer. Separate scalable serving/worker components are intentionally out of scope.
- SQLite uses WAL and foreign keys; production requires reliable persistent local block storage.
- Collections are logical data groupings, not security tenants.
- No search pagination, tag filtering, per-user ACLs, advanced retries or distributed job coordination.
- Video, animated GIF, PDF, OCR, image generation and text+image fusion are not supported.

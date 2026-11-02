# Module 4 v0.1.0 source handoff

Scope: image-to-image and Persian/English text-to-image retrieval only.

## Implemented

- Versioned FastAPI API with key authentication and request validation.
- Model-adapter contract; CPU-only local SigLIP2 provider using upstream processor.
- Strict JPEG/PNG/WebP decoding, EXIF orientation, sanitized WebP media and thumbnails.
- Durable SQLite collection/job/image/embedding repository and single indexing worker.
- FAISS IDMap/FlatIP per-collection vector search, with SQLite-backed index recovery.
- Private authenticated thumbnails; image deletion; collection creation and listing.
- RTL React/TypeScript/Vite frontend with vanilla CSS and no component framework.
- Docker CPU backend, Nginx frontend, Compose, CI/build/deploy templates, docs, benchmark scripts.

## Verified in artifact environment

- 6 offline backend tests pass with an injected deterministic dual encoder.
- Python source compiled without errors.
- TypeScript/TSX syntax transpilation completed without diagnostics.
- Compose and GitLab CI YAML successfully parsed.

## Requires verification before production

- Real pretrained SigLIP2 model weights are **not bundled or executed** here.
- FAISS native bindings were unavailable locally; a test-only NumPy index was used.
- React packages were unavailable in this environment; a complete npm/Vite build could not run.
- Docker Engine was unavailable; no real image build or Compose bring-up performed.
- Test and tune real CPU memory/latency, Persian retrieval accuracy and indexing throughput.
- Generate and commit `frontend/package-lock.json` via `npm install` before tightening CI to `npm ci`.
- Configure deployment secrets, host permissions, ingress TLS and model checksum validation.

No repository was pushed or created remotely, and no server changes were made.

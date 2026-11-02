# Deployment and CI/CD

## Local and server prerequisites

- Docker Engine and Docker Compose v2, Linux x86-64 CPU host.
- Python 3.11 for model-download script (may use a venv).
- Persistent SSD volume for SQLite, originals, thumbnails, FAISS and jobs.
- Memory budget and latency tuned only after real SigLIP2 tests; initial Docker limit 6GB and CPU 4 cores are **examples**.
- Host port assignments are proposed: API `127.0.0.1:8004`, UI `127.0.0.1:8085`. Check for collisions.
- TLS-enabled ingress/reverse proxy is required for remote/public exposure.

## Setup

```bash
cp .env.example .env
python3 -c 'import secrets;print(secrets.token_urlsafe(36))'
# Set API_KEY; change APP_ENV=production for server
./scripts/prepare_local.sh
id -u; id -g    # enter both in RUN_UID/RUN_GID
python3 -m venv .venv && . .venv/bin/activate
pip install huggingface_hub==0.30.2
python scripts/download_model.py --output .models/siglip2
python scripts/verify_model.py --path .models/siglip2
# Put the revision SHA in MODEL_REVISION

docker compose config --quiet
docker compose build
docker compose up -d
docker compose logs -f api ui
```

Because the backend runs non-root, `.data` must be writable by `RUN_UID:RUN_GID`; `.models/siglip2` is mounted read-only and must be readable. On host systems where your service user is not UID 1000, explicitly set the correct values before the first `up`. Avoid `chmod 777` or running the API as root.

The API readiness may remain 503 when the model path is absent, its checksum manifest is missing, or inference fails. This is intentional; inspect backend logs for the precise error. Neither Nginx nor API should download model weights dynamically.

## Production images and manual GitLab deployment

`.gitlab-ci.yml` includes:

- Backend offline unit/integration tests with fake embeddings and a test-only NumPy index.
- Frontend TypeScript/Vite build (using `npm install` because the lockfile has not yet been generated in an online environment).
- Manual Docker image builds for API and UI, pushed with immutable `$CI_COMMIT_SHA` tags.
- Manual SSH deployment running `docker compose -f docker-compose.yml -f docker-compose.production.yml pull/up` using `API_IMAGE` and `UI_IMAGE`.

**GitLab variables needed:** `DEPLOY_SSH_PRIVATE_KEY`, `DEPLOY_SSH_KNOWN_HOSTS`, `DEPLOY_SSH_USER`, `DEPLOY_SSH_HOST`, `DEPLOY_DIRECTORY`; GitLab registry credentials already supplied in a configured registry runner. Prefer protected/masked CI variables, and restrict manual jobs to authorized maintainers. A Docker-in-Docker runner is required for build jobs. The server must already have the repo's compose files, `.env`, persistent `.data`, verified `.models` and a valid registry login. The pipeline does **not** perform initial server bootstrap automatically.

**Before first CI build:** run `npm install` inside `frontend/` on a network-enabled workstation to create `package-lock.json`; commit that file, then replace `npm install` with `npm ci` in the frontend Dockerfile and `.gitlab-ci.yml` for reproducible dependencies.

## Rollout gates

1. `docker compose config --quiet` succeeds with real `.env`.
2. Model manifest verifies against downloaded weights.
3. Image builds with CPU-only torch; no GPU runtime required.
4. `/health/live` 200 and `/health/ready` 200.
5. Real image indexing succeeds, job transitions to completed and query returns the image.
6. Persian and English query quality evaluated on representative data.
7. Restart and recover index without re-embedding.
8. CPU/RAM quotas, throughput and latency measured under expected concurrent load.
9. Authentication, source storage and TLS ingress reviewed.
10. Backups and restoration verified.

## Backup/restore

While ingestion is paused, back up `.data/metadata/image-search.sqlite` with SQLite's online backup API (preferred over raw file copy while WAL is active), and `.data/images/`. FAISS snapshots can be rebuilt from SQLite BLOBs. Preserve the matching `.models/siglip2` and model manifest, or re-download the *same* immutable revision. The metadata/index is tied to a specific model signature.

**Do not** copy only `*.sqlite` while WAL is active and assume all transactions are included. For production use a database-native backup procedure or a clean, verified stop. Restore to a test instance first, then verify search after restart.

# GitLab deployment for SuperApp Image Search (Module 04)

The organizational runner uses tags `linux`, `bina`, `shell`. Pipeline runs on GitLab `main`.

- `validate-source`: file checks, Docker Compose configuration, Python syntax.
- `backend-tests`: deterministic offline tests; no pretrained model download.
- `frontend-build`: TypeScript/Vite build. Switch npm install to npm ci when a reviewed lockfile is committed.
- `build-images`: manual Docker build on the shell runner; no Docker-in-Docker and no automatic startup.
- `deploy`: manual SSH, uploads server env from CI File variable, fast-forwards `origin/main`, builds the images. `RUN_SERVICES=0` intentionally keeps containers stopped/unchanged. Only `RUN_SERVICES=1` verifies the model manifest and brings up API/UI.

## GitLab CI/CD variables

Use GitLab **File** variables `SSH_PRIVATE_KEY`, `SSH_KNOWN_HOSTS`, `ENV_FILE`. Use normal variables `SSH_USER`, `SSH_PORT`, `VM_IPADDRESS`. Optional variables: `DEPLOY_DIR=/opt/apps/ai-service/image_search_engine_module` and `RUN_SERVICES=0`. Validate known-host fingerprints out of band; protect variables, runner and production environment.

The target server must have an existing GitLab checkout at DEPLOY_DIR, Docker Compose, a verified `.models/siglip2`, writable `.data` and a valid server `.env`. Download model weights separately with `scripts/download_model.py`, then run `scripts/verify_model.py` and set the model revision SHA in the env file. A server-only deployment without model setup will not be ready.

## Validation status

CI syntax and offline Python tests were checked in the source workspace; the organizational runner, full npm/Vite build, Docker Engine and real SigLIP2 inference were not available there. The 6g memory setting is an initial estimate, not a benchmarked requirement. Do not expose direct HTTP externally without TLS ingress and access control. Do not scale API replicas against the same SQLite database.

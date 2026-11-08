# Server 209 automated model bootstrap / build mirror priority

This module's GitLab `.gitlab-ci.yml` is owned by the deployment team and is intentionally unchanged.

## Deployment contract

Existing CI copies the File variable `ENV_FILE` as `.env` on server 209 and runs
`docker compose up --build -d` in `/opt/apps/ai-service/image_search_engine_module`.
The Compose `model-setup` one-shot service now runs before API startup. If the
model manifest is absent it downloads SigLIP2 from Hugging Face to the
persistent read/write `MODEL_PATH`. On subsequent deploys it verifies all
model hashes; invalid/mismatched manifests abort startup instead of silently
switching the vector space. The API is always offline and mounts models read-only.
The `data-init` service remains unchanged.

The first build requires network access to Debian apt repositories, Docker
base image registries, npm (frontend), and Hugging Face (model weights). Liara
and Chabokan are *PyPI* mirrors only and cannot replace these sources.

## Python index order

The backend Docker build tries Liara, then Chabokan, then the official PyPI
index for Python requirements. Because PyPI's regular Linux torch wheel may
pull CUDA runtimes, PyTorch is pinned to `torch==2.5.1+cpu`. The build first
checks both PyPI mirrors for this CPU-specific wheel, then falls back to
PyTorch's **official CPU wheel index**. A runtime assertion prevents an
accidental CUDA-enabled torch installation.

The mirror URLs are build arguments supplied by Docker Compose, and can be
changed through the server `.env`.

## LAN/VPN access

Set `WEB_BIND=192.168.4.209`, `WEB_PORT=8085` on the server if that IP is
assigned to its host interface. The UI is at `http://192.168.4.209:8085`.
Keep `API_BIND_IP=127.0.0.1` (port 8004): Nginx proxies UI `/api/` to the
internal Docker `api:8004`. Do not expose the API port directly. If LAN/VPN
routes do not reach that interface, network administrators must configure
routing or a trusted TLS reverse proxy. Firewall rules should limit 8085 to
approved LAN/VPN subnets. Plain HTTP transmits the API key without TLS.

## CI secret and model considerations

GitLab CI requires valid SSH configuration and an `ENV_FILE` File variable.
Rotate any token that was pasted in a chat or other shared location. Keep
`API_KEY` private. The `MODEL_REVISION` value can initially be empty: setup
resolves the current upstream SHA on first download, writes the immutable
manifest, and reuses it afterward. For reproducibility pin the printed SHA
in the next deployment's environment.

The current deployment script has `ssh-keyscan` without out-of-band host key
pinning and copies a secret file before validating model availability. We
did **not** modify CI, per the requested ownership boundary. The DevOps team
should independently verify SSH host fingerprints and File variable handling.
`docker compose up --build -d` can still fail if the host cannot reach a
required registry or Hugging Face; inspect setup and API logs.

## Debian APT build network recovery

The Docker build previously used Debian Bookworm's default HTTP port 80 URL
and failed to download signed package indexes, causing `libgomp1` not found.
The backend now uses the **same APT installer as the Speaker Diarization
module**: `ops/install-debian-packages.sh`, with signed HTTPS package indexes,
strict `APT::Update::Error-Mode=any`, bounded 20-second APT timeouts and
primary/fallback mirrors:

- Primary: `https://mirror.metanet.ch/debian`, `https://mirror.metanet.ch/debian-security`
- Fallback: `https://mirrors.huaweicloud.com/repository/debian`,
  `https://mirrors.huaweicloud.com/repository/debian-security`

These URLs may be overridden with `APT_*` in the GitLab `ENV_FILE`; no new
variables are required because the Dockerfile has defaults. All repositories
remain signature-verified by the Debian archive keyring. No disabled TLS,
insecure APT setting or unauthenticated packages.

Liara -> Chabokan -> PyPI remains the **Python** package order. CPU-only Torch
keeps its official CPU-specific wheel index fallback. Other network
dependencies remain Docker Hub, Debian HTTPS, npm and Hugging Face.
If both Debian mirrors fail, verify Docker-build DNS/HTTPS egress or proxy
settings on server 209; a repository-only change cannot fix a blocked network.

The teammate-owned `.gitlab-ci.yml` is unchanged and still executes
`docker compose up --build -d` on server 209 via SSH.

# Environment variables

| Variable | Default/example | Purpose |
|---|---|---|
| `APP_ENV` | development | Use production on server; disables unsafe auth-off option |
| `API_KEY` | **required** | Shared key (at least 24 characters) |
| `API_AUTH_ENABLED` | true | Must remain true in production |
| `API_PORT` | 8004 | Host-bound API port |
| `WEB_PORT` | 8085 | Host-bound React/Nginx port |
| `WEB_BIND` | 127.0.0.1 | Safe default interface for UI |
| `MODEL_ID` | google/siglip2-base-patch32-256 | Expected checkpoint identity |
| `MODEL_REVISION` | blank until downloaded | Match exact verified upstream SHA |
| `MODEL_PATH` | ./.models/siglip2 | Host-side directory mounted read-only |
| `DATA_PATH` | ./.data | Persistent host-side SQLite/media/index storage |
| `RUN_UID`, `RUN_GID` | 1000 | Host permissions for non-root API process |
| `INFERENCE_THREADS` | 2 | CPU model threads |
| `API_CPUS` | 4 | API container CPU quota (benchmark-dependent) |
| `API_MEMORY_LIMIT` | 6g | Container memory cap, not validated yet |
| `MAX_IMAGE_SIZE_MB` | 10 | Individual image max bytes |
| `MAX_IMAGE_PIXELS` | 20000000 | Decompression bomb protection |
| `MAX_TOP_K` | 50 | Search result cap |
| `MAX_BATCH_IMAGES` | 20 | Ingestion batch cap |
| `API_IMAGE`, `UI_IMAGE` | unset | Registry image tags for production compose override |

Backend-only settings are also in `backend/app/config.py` (`DATA_DIR`, `MODEL_LOCAL_PATH`, `VECTOR_BACKEND`, `JOB_POLL_INTERVAL`, `METRICS_ENABLED`, `CORS_ORIGINS`). Their Docker values are supplied in `docker-compose.yml`. `VECTOR_BACKEND=numpy` is valid **only** for hermetic tests when `APP_ENV=test`; real deployments require `faiss`.

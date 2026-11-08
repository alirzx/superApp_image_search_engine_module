FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /srv
# Signed Bookworm HTTPS APT mirrors with fallback, aligned with Speaker Diarization.
ARG APT_PRIMARY_DEBIAN_URL=https://mirror.metanet.ch/debian
ARG APT_PRIMARY_SECURITY_URL=https://mirror.metanet.ch/debian-security
ARG APT_FALLBACK_DEBIAN_URL=https://mirrors.huaweicloud.com/repository/debian
ARG APT_FALLBACK_SECURITY_URL=https://mirrors.huaweicloud.com/repository/debian-security
COPY ops/install-debian-packages.sh /usr/local/bin/install-debian-packages
RUN sh /usr/local/bin/install-debian-packages libgomp1 ca-certificates
# CPU wheels only. Never install CUDA-enabled PyTorch packages in this image.
# Public Python dependencies: Liara -> Chabokan -> official PyPI.
# CPU-only torch uses the exact +cpu wheel. PyPI mirrors may not carry it,
# so official PyTorch CPU wheel index is the final architecture-safe fallback.
ARG PIP_PRIMARY_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple
ARG PIP_SECONDARY_INDEX_URL=https://mirror2.chabokan.net/pypi/simple/
ARG PIP_FALLBACK_INDEX_URL=https://pypi.org/simple
ARG PYTORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN set -eu; \
    if python -m pip install --no-cache-dir --retries 1 --timeout 25 --index-url "$PIP_PRIMARY_INDEX_URL" 'torch==2.5.1+cpu'; then \
      echo "CPU torch installed from Liara mirror"; \
    elif python -m pip install --no-cache-dir --retries 1 --timeout 25 --index-url "$PIP_SECONDARY_INDEX_URL" 'torch==2.5.1+cpu'; then \
      echo "CPU torch installed from Chabokan mirror"; \
    else \
      echo "CPU torch not available from PyPI mirrors: using official CPU wheel index"; \
      python -m pip install --no-cache-dir --retries 2 --timeout 60 --index-url "$PYTORCH_CPU_INDEX_URL" --extra-index-url "$PIP_FALLBACK_INDEX_URL" 'torch==2.5.1+cpu'; \
    fi; \
    python -c "import torch; assert torch.version.cuda is None, 'Expected CPU-only PyTorch'"
COPY backend/requirements.txt /srv/requirements.txt
RUN set -eu; \
    python -m pip install --no-cache-dir --retries 1 --timeout 25 --index-url "$PIP_PRIMARY_INDEX_URL" -r requirements.txt || \
    python -m pip install --no-cache-dir --retries 1 --timeout 25 --index-url "$PIP_SECONDARY_INDEX_URL" -r requirements.txt || \
    python -m pip install --no-cache-dir --retries 2 --timeout 60 --index-url "$PIP_FALLBACK_INDEX_URL" -r requirements.txt
COPY backend/app /srv/app
COPY scripts/download_model.py scripts/verify_model.py scripts/ensure_model.py /srv/scripts/
RUN addgroup --system app && adduser --system --ingroup app app && mkdir -p /data /models && chown -R app:app /data
USER app
EXPOSE 8004
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8004/health/ready', timeout=3)" || exit 1
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8004","--workers","1","--proxy-headers","--forwarded-allow-ips","127.0.0.1"]

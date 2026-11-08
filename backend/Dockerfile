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
# CPU-only torch is installed ONLY from the dedicated PyTorch CPU index;
# the generic PyPI mirrors are used for its Python dependencies.
ARG PIP_PRIMARY_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple
ARG PIP_SECONDARY_INDEX_URL=https://mirror2.chabokan.net/pypi/simple/
ARG PIP_FALLBACK_INDEX_URL=https://pypi.org/simple
ARG PYTORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu
# Resolve all ordinary Python packages and Torch CPU runtime dependencies
# via Liara -> Chabokan -> official PyPI (only as last fallback).
# Do not request the CPU-specific torch distribution from generic PyPI mirrors.
COPY backend/requirements.txt /srv/requirements.txt
COPY backend/requirements-torch-cpu.txt /srv/requirements-torch-cpu.txt
RUN set -eu; \
    if python -m pip install --no-cache-dir --retries 1 --timeout 25 \
        --index-url "$PIP_PRIMARY_INDEX_URL" \
        -r /srv/requirements.txt -r /srv/requirements-torch-cpu.txt; then \
      echo "Python dependencies installed from Liara"; \
    elif python -m pip install --no-cache-dir --retries 1 --timeout 25 \
        --index-url "$PIP_SECONDARY_INDEX_URL" \
        -r /srv/requirements.txt -r /srv/requirements-torch-cpu.txt; then \
      echo "Python dependencies installed from Chabokan"; \
    else \
      echo "Regional mirrors unavailable; trying official PyPI as last fallback"; \
      python -m pip install --no-cache-dir --retries 1 --timeout 45 \
        --index-url "$PIP_FALLBACK_INDEX_URL" \
        -r /srv/requirements.txt -r /srv/requirements-torch-cpu.txt; \
    fi
# PyTorch's official CPU-only index hosts torch==2.5.1+cpu for Python 3.11.
# --no-deps is intentional: dependencies were installed from regional mirrors.
# Crucially, no --extra-index-url=pypi.org here (it caused 60 s timeouts).
RUN set -eu; \
    python -m pip install --no-cache-dir --retries 2 --timeout 60 --no-deps \
      --index-url "$PYTORCH_CPU_INDEX_URL" 'torch==2.5.1+cpu'; \
    python -m pip check; \
    python -c "import torch; assert torch.__version__.startswith('2.5.1+cpu'), torch.__version__; assert torch.version.cuda is None, 'Expected CPU-only PyTorch'; print('Verified PyTorch CPU:', torch.__version__)"

COPY backend/app /srv/app
COPY scripts/download_model.py scripts/verify_model.py scripts/ensure_model.py /srv/scripts/
RUN addgroup --system app && adduser --system --ingroup app app && mkdir -p /data /models && chown -R app:app /data
USER app
EXPOSE 8004
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8004/health/ready', timeout=3)" || exit 1
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8004","--workers","1","--proxy-headers","--forwarded-allow-ips","127.0.0.1"]

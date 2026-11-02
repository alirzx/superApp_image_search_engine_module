FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 ca-certificates && \
    rm -rf /var/lib/apt/lists/*
# CPU wheels only. Never install CUDA-enabled PyTorch packages in this image.
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app /srv/app
RUN addgroup --system app && adduser --system --ingroup app app && mkdir -p /data /models && chown -R app:app /data
USER app
EXPOSE 8004
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8004/health/live', timeout=3)" || exit 1
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8004","--workers","1","--proxy-headers","--forwarded-allow-ips","127.0.0.1"]

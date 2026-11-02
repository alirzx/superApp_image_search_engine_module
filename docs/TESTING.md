# Testing and quality gates

## Automated offline tests

`PYTHONPATH=backend pytest -q backend/tests`

Current test suite validates image byte/pixel rules, canonical media, embedding normalization, model signature guards, API authentication, collections, uploads, background jobs, Persian mocked queries, English mocked queries, image queries, collection-scoped retrieval, deletion, thumbnail access and SQLite recovery across restart. It uses a **test-only deterministic encoder** plus NumPy exact search to avoid downloading the 1.5GB model in CI.

These do NOT validate actual PyTorch model initialization, Hugging Face tokenizer inputs, the FAISS native library, Docker builds, the React bundle or end-to-end CPU throughput. Never interpret them as real retrieval quality tests.

## Required release tests on an actual CPU machine

- Load pinned SigLIP2 on CPU; record actual model type, dimension, feature norms and processor behavior.
- Ensure image/image and text/image vectors occupy the expected shared embedding space.
- Run paired Persian/English retrieval tests, including ZWNJ, colloquial phrasing, objects, colors, scene descriptions and hard negatives.
- Compare retrieval with a separate multilingual CLIP baseline before locking model choice.
- Load a realistic collection of 1k/10k images, record indexing images/s and model peak RSS.
- Measure text and image search end-to-end P50/P95 with concurrency 1/2/4/8, including retrieval, database, model and HTTP overhead.
- Kill the API during a job; confirm queued jobs recover on restart and already completed vectors survive.
- Validate FAISS real binding via a smoke test and compare exact search scores with NumPy dot product.
- Verify no image/thumbnail access without API key and no leakage through another collection.
- Verify Docker Compose on the target Linux distribution, CPU quotas, memory caps, disk permissions and restart behavior.
- Test React frontend with actual production Nginx reverse proxy and a browser.

## Known unverified status at source packaging

The code was assembled in a sandbox without access to pretrained model weights, npm dependencies, Docker and FAISS bindings. The offline FastAPI integration tests pass, but **full deployment readiness is NOT established**. Don't label as production-ready before performing the above real validations.

## Benchmark scripts

```bash
# With real model/dependencies installed on the CPU target:
PYTHONPATH=backend python scripts/benchmark_cpu.py --model-path .models/siglip2 --threads 2 --runs 20
PYTHONPATH=backend python scripts/faiss_smoke.py

# After indexing your labeled example collection, with API_KEY exported:
python scripts/benchmark_retrieval.py --dataset benchmarks/datasets/text_queries.example.json --top-k 10
```

The supplied retrieval test corpus file is a **schema example**, not a validated ground-truth benchmark. Build and label a representative Persian/English benchmark before selecting the final model.

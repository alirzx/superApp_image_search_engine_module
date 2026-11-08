#!/usr/bin/env python3
"""Idempotent, checksum-verified model bootstrap for GitLab Compose deployment.

No model weights are included in git or the Docker image. Runtime stays offline.
This process is the only container allowed to download model files.
"""
import json
import os
import sys
from pathlib import Path
from download_model import main as download_model
from verify_model import digest

def verify(path: Path, model_id: str, expected_revision: str) -> str:
    manifest_path = path / "model-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sha = manifest.get("revision", "")
    if manifest.get("model_id") != model_id or not sha:
        raise RuntimeError("Model manifest does not match MODEL_ID")
    if expected_revision and expected_revision != sha:
        raise RuntimeError("MODEL_REVISION differs from installed weights; coordinate reindex before changing model")
    entries = manifest.get("sha256")
    if not isinstance(entries, dict) or not entries:
        raise RuntimeError("Model manifest has no checksums")
    root = path.resolve()
    for rel, expected in entries.items():
        target = (path / rel).resolve()
        if not target.is_relative_to(root) or not target.is_file() or digest(target) != expected:
            raise RuntimeError("Model checksum verification failed for " + str(rel))
    if not any(n.endswith(".safetensors") for n in entries):
        raise RuntimeError("No model weight file in verified manifest")
    print("VERIFIED_MODEL_REVISION=" + sha, flush=True)
    return sha

def main():
    path = Path(os.getenv("MODEL_LOCAL_PATH", "/models/siglip2"))
    model_id = os.getenv("MODEL_ID", "google/siglip2-base-patch32-256")
    revision = os.getenv("MODEL_REVISION", "").strip()
    path.mkdir(parents=True, exist_ok=True)
    if not (path / "model-manifest.json").is_file():
        print("Model manifest absent: starting initial pinned Hugging Face download", flush=True)
        sys.argv = ["download_model.py", "--model-id", model_id, "--output", str(path)]
        if revision:
            sys.argv += ["--revision", revision]
        download_model()
    verify(path, model_id, revision)

if __name__ == "__main__":
    main()

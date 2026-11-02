# Model card and inference contract

**Checkpoint:** `google/siglip2-base-patch32-256`

**Provider:** Google. **Task:** multimodal image-text embedding for retrieval. **Runtime in this release:** PyTorch / Transformers CPU, float32. **Input:** PIL RGB image or Unicode text (including Persian). **Output:** one finite unit-normalized vector per input. **Image processor and tokenizer:** loaded from the exact same local model folder as weights.

**License:** the checkpoint page currently advertises Apache-2.0; ensure code and model-weight terms are reviewed before redistribution or commercial use. The checkpoint files are downloaded from the upstream repository by the operator, not redistributed.

Source: https://huggingface.co/google/siglip2-base-patch32-256

## Implementation compatibility note

Although the repository is named `siglip2`, the current `config.json` in the official checkpoint identifies its `model_type` as `siglip`. For compatibility across Transformers versions the adapter uses `AutoModel` and `AutoProcessor`, calls `get_image_features` and `get_text_features`, and supports either pooled-output structures or tensors. Its actual output dimension is read from the model config. These paths MUST be validated with the downloaded checkpoint before production deployment, since no real pretrained weight inference is executed in offline CI.

## Explicit download + integrity

```bash
pip install 'huggingface_hub==0.30.2'
python scripts/download_model.py --output .models/siglip2
python scripts/verify_model.py --path .models/siglip2
```

The downloader resolves `main` to the current immutable Hugging Face commit and creates `model-manifest.json` with individual file SHA256 checksums. An operator may pass `--revision <SHA>` to pin an earlier model. Set `MODEL_REVISION=<printed SHA>` in `.env`. Runtime checks model ID/revision, loads only from local disk and requires safetensors. No model download is permitted at inference time.

## Embedding correctness gate

With downloaded weights, perform this manual smoke before rollout:

1. Load `Siglip2CPU` and inspect reported signature/dimension.
2. Generate embeddings for a known cat image, a different vehicle image, a matching English caption and the equivalent Persian caption.
3. Check all embeddings are finite, unit length and equal dimension.
4. Verify image-image similarity ranks the same/corresponding image highly.
5. Compare English and Persian text retrieval quality on a labeled image collection.
6. Record latency, peak RSS, physical CPU, threads and revision.

The model has multilingual training, but **Persian retrieval accuracy is unverified on the target workload**. A future release may compare Sentence Transformers' multilingual CLIP as an alternate provider, which must have its own index namespace and full reindex because embeddings are incompatible.

## ONNX / quantization status

ONNX Runtime and INT8 are **research extensions, not wired into the MVP**. Adding them requires verified export, preprocessing parity, numerical regression, new model signatures, and a complete reindex if vectors differ materially. No speedup claim is made without measurements.

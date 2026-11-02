"""SigLIP2 CPU dual encoder. All imports are lazy to keep offline CI lightweight."""
import json
from pathlib import Path
import numpy as np
from PIL.Image import Image
from .base import normalize


class Siglip2CPU:
    def __init__(self, model_path: Path, model_id: str, revision: str, threads: int = 2):
        import torch
        from transformers import AutoModel, AutoProcessor
        if not model_path.exists():
            raise FileNotFoundError(f'Model missing at {model_path}; run scripts/download_model.py')
        manifest_path = model_path / 'model-manifest.json'
        if not manifest_path.is_file():
            raise ValueError('Model manifest missing; use the provided verified download script')
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('model_id') != model_id:
            raise ValueError('Model identity mismatch: manifest vs MODEL_ID')
        sha = manifest.get('revision', '')
        if not sha or (revision and revision != sha):
            raise ValueError('Model revision mismatch or missing revision')
        torch.set_num_threads(threads)
        self._torch = torch
        self.model = AutoModel.from_pretrained(str(model_path), local_files_only=True, use_safetensors=True).eval().to('cpu')
        self.processor = AutoProcessor.from_pretrained(str(model_path), local_files_only=True)
        self._dimension = int(getattr(self.model.config, 'projection_dim', None) or
                              getattr(self.model.config.text_config, 'projection_size', None) or
                              self.model.config.text_config.hidden_size)
        self._signature = f'{model_id}@{sha}:siglip2:cpu:fp32'
        self._text_length = int(self.model.config.text_config.max_position_embeddings)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def signature(self) -> str:
        return self._signature

    def encode_image(self, image: Image) -> np.ndarray:
        tensors = self.processor(images=image, return_tensors='pt')
        with self._torch.inference_mode():
            output = self.model.get_image_features(**tensors)
        # Transformers SigLIP2 returns a BaseModelOutputWithPooling.
        feature = output.pooler_output if hasattr(output, 'pooler_output') else output
        return normalize(feature[0].detach().cpu().float().numpy(), self.dimension)

    def encode_text(self, text: str) -> np.ndarray:
        tensors = self.processor(text=[text], padding='max_length', truncation=True,
                                 max_length=self._text_length, return_tensors='pt')
        with self._torch.inference_mode():
            output = self.model.get_text_features(**tensors)
        feature = output.pooler_output if hasattr(output, 'pooler_output') else output
        return normalize(feature[0].detach().cpu().float().numpy(), self.dimension)

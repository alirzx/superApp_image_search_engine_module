"""Model-independent contracts. Every embedding must be finite, float32, unit-length."""
from typing import Protocol
from PIL.Image import Image
import numpy as np


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    @property
    def signature(self) -> str: ...

    def encode_image(self, image: Image) -> np.ndarray: ...

    def encode_text(self, text: str) -> np.ndarray: ...


def normalize(vector: np.ndarray, dimension: int) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32).reshape(-1)
    if arr.shape[0] != dimension or not np.all(np.isfinite(arr)):
        raise ValueError('Model returned invalid embedding')
    norm = np.linalg.norm(arr)
    if not np.isfinite(norm) or norm < 1e-10:
        raise ValueError('Model returned zero or invalid embedding')
    return np.ascontiguousarray(arr / norm, dtype=np.float32)

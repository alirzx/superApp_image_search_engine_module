"""All runtime configuration is explicit and read from environment/.env."""
from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', case_sensitive=False)
    app_env: str = 'development'
    api_host: str = '0.0.0.0'
    api_port: int = 8004
    api_auth_enabled: bool = True
    api_key: str = ''
    cors_origins: str = ''
    model_id: str = 'google/siglip2-base-patch32-256'
    model_local_path: Path = Path('.models/siglip2')
    model_revision: str = ''
    inference_threads: int = Field(default=2, ge=1, le=64)
    inference_concurrency: int = Field(default=1, ge=1, le=8)
    data_dir: Path = Path('.data')
    max_image_size_mb: int = Field(default=10, ge=1, le=50)
    max_image_pixels: int = Field(default=20_000_000, ge=1_000, le=50_000_000)
    max_top_k: int = Field(default=50, ge=1, le=500)
    max_batch_images: int = Field(default=20, ge=1, le=100)
    job_poll_interval: float = Field(default=0.5, ge=0.05, le=10)
    vector_backend: str = 'faiss'
    metrics_enabled: bool = True

    @model_validator(mode='after')
    def validate_security(self):
        if self.api_auth_enabled and len(self.api_key) < 24:
            raise ValueError('API_KEY must be at least 24 chars when API_AUTH_ENABLED=true')
        if self.app_env == 'production' and not self.api_auth_enabled:
            raise ValueError('Production cannot disable API authentication')
        if self.vector_backend not in ('faiss', 'numpy'):
            raise ValueError('VECTOR_BACKEND must be faiss (numpy only for tests)')
        if self.vector_backend == 'numpy' and self.app_env != 'test':
            raise ValueError('VECTOR_BACKEND=numpy is test-only')
        return self

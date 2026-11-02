Model binaries are not committed to source control or bundled in the ZIP.
Download to `.models/siglip2` using `scripts/download_model.py` and verify with
`scripts/verify_model.py`. The downloader pins and records the immutable upstream
revision, as well as SHA256 checksums. The API loads only local safetensors.

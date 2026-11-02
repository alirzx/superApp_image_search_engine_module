# Security decisions and limitations

- `X-API-Key` enforced on all image/collection/job/search/media/metrics endpoints. `/health/live` and `/health/ready` are public and can be restricted by an outer proxy.
- API key is provided at runtime through `.env` or secrets injection, not bundled into the frontend. Frontend stores it in **sessionStorage**, which limits persistence but does not protect against browser XSS. For an internet-facing system replace this arrangement with an authenticated gateway and HttpOnly secure session cookies.
- No arbitrary image URLs or remote media fetching. Input bytes must decode as JPEG, PNG or WebP, respect max upload bytes/pixels and pass decoder validation.
- Original EXIF metadata is removed in canonical WebP storage, and alpha images are composited onto white. Uploaded originals are not retained byte-for-byte.
- Client filenames are displayed as metadata only. File paths are generated from random IDs and checked against traversal.
- Thumbnail access requires the same API key and uses `Cache-Control: private, no-store`; frontend fetches blobs with credentials.
- One shared key means **single-tenant authorization**. Different collections are NOT users/tenants. To support untrusted users, add user principals, collection ACLs, upload quotas and audit logging before exposure.
- CPU inference concurrency is restricted and requests have input size, text length and top-K caps. Nginx caps total request body.
- Runtime model loading is local-only and uses safetensors. Release operators should verify every model hash against the download manifest.
- No private images are intentionally written to logs. Error messages from model dependencies may reveal paths; review log shipping and access controls.
- Docker image uses a nonroot UID/GID, `no-new-privileges`, CPU/memory/PID limits and internal API binding. TLS is the responsibility of the external ingress.
- SQLite and image files are sensitive: encrypt at rest where needed, back up securely, restrict host mounts and define a retention policy.
- Public multi-user SaaS, malware/content moderation, request rate limits beyond worker constraints and distributed ingestion are NOT implemented.

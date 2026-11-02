# REST API v1 contract

Service port: `8004`; UI proxy base `/api`. All protected endpoints require `X-API-Key: <secret>`; `/health/live` and `/health/ready` are public liveness/readiness routes. Health details should be protected at the outer gateway if published.

| Method | Route | Request | Status |
|---|---|---|---|
| GET | `/health/live` | none | 200 |
| GET | `/health/ready` | none | 200 or 503 |
| GET | `/metrics` | key | 200 |
| GET | `/v1/models` | key | 200 |
| GET | `/v1/collections` | key | 200 |
| POST | `/v1/collections` | JSON `{ "name": "Gallery" }` | 201 |
| POST | `/v1/images` | multipart `file`, `collection_id` | 202 |
| POST | `/v1/images/batch` | multipart repeated `files`, `collection_id` | 202 |
| GET | `/v1/images/{image_id}` | key | 200 or 404 |
| GET | `/v1/images/{image_id}/thumbnail` | key | 200 image/webp or 404 |
| DELETE | `/v1/images/{image_id}` | key | 204 or 404 |
| GET | `/v1/jobs/{job_id}` | key | 200 or 404 |
| POST | `/v1/search/text` | JSON `collection_id`, `query`, `top_k` | 200 |
| POST | `/v1/search/image` | multipart `file`, `collection_id`, `top_k` | 200 |

No duplicate or hybrid search endpoint is implemented.

## Ingestion example

```http
POST /v1/images
X-API-Key: YOUR_SECRET
Content-Type: multipart/form-data
file=@cat.jpg
collection_id=default
```

```json
{"image_id":"e0...","job_id":"3a...","status":"queued","collection_id":"default"}
```

Poll `/v1/jobs/{job_id}`. Statuses: `queued`, `processing`, `completed`, `failed`; error is `null` or a truncated technical reason. For batch ingestion, response has `accepted` and `rejected` arrays with per-file errors. No all-or-nothing batch transaction is promised.

## Text request

```json
{"collection_id":"default","query":"یک گربه سفید روی مبل","top_k":5}
```

## Image request

`multipart/form-data` with `file=<JPEG,PNG,WebP>`, `collection_id=default`, `top_k=5`.

## Search response

```json
{
  "request_id":"d1...",
  "collection_id":"default",
  "query_type":"text",
  "model_id":"google/siglip2-base-patch32-256",
  "model_revision":"google/siglip2-base-patch32-256@<sha>:siglip2:cpu:fp32",
  "results":[{
    "image_id":"a1...",
    "score":0.735,
    "rank":1,
    "thumbnail_url":"/v1/images/a1.../thumbnail",
    "metadata":{"filename":"cat.jpg","width":640,"height":480}
  }],
  "processing_time_ms":42.0
}
```

All IDs, scores and times shown above are synthetic examples. Scores are inner products of L2-normalized vectors, not calibrated probabilities. Relative thumbnail URLs are at the backend root; when using Nginx UI, prefix `/api`. Thumbnails **require** the API key header; using an ordinary unauthenticated HTML `<img src>` will not work.

Errors: `401` invalid API key, `404` missing image/collection/job, `413` over byte limit, `422` invalid image/request, `503` unavailable model/index. Exception details are kept short. OpenAPI is exposed at `/docs` for local deployments; protect/block it at your gateway on public deployments if desired.

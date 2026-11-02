.PHONY: test compose-check up down logs build model-download verify-model
help:
	@echo 'Targets: test compose-check build up down logs model-download verify-model'
test:
	PYTHONPATH=backend pytest -q backend/tests
compose-check:
	docker compose config --quiet
build:
	docker compose build
up:
	docker compose up -d
logs:
	docker compose logs -f api ui
down:
	docker compose down
model-download:
	python scripts/download_model.py --output .models/siglip2
verify-model:
	python scripts/verify_model.py --path .models/siglip2

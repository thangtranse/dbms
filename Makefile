.PHONY: config build up up-all down logs status test-qdrant test-teradata

config:
	docker compose config

build:
	docker compose --profile teradata build

up:
	docker compose up -d --build office-lunch qdrant

up-all:
	docker compose --profile teradata up -d --build

down:
	docker compose --profile teradata down

logs:
	docker compose --profile teradata logs -f

status:
	docker compose --profile teradata ps

test-qdrant:
	curl --fail --silent --show-error \
		-H "api-key: $${QDRANT_API_KEY:-local-dev-key-change-me}" \
		http://localhost:$${QDRANT_HTTP_PORT:-6333}/healthz

test-teradata:
	docker compose --profile teradata run --rm teradata-client python /app/healthcheck.py


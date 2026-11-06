.PHONY: config build up up-all down logs status test-qdrant test-teradata

export BUILD_COMMIT := $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
export BUILD_DIRTY := $(shell test -z "$$(git status --porcelain 2>/dev/null)" && echo false || echo true)

config:
	docker compose config --quiet

build:
	docker compose --profile teradata build

up:
	docker compose up -d --build office-lunch api

up-all:
	docker compose --profile teradata up -d --build office-lunch api teradata-client

down:
	docker compose --profile teradata --profile local-worker down

logs:
	docker compose --profile teradata --profile local-worker logs -f

status:
	docker compose --profile teradata --profile local-worker ps

test-qdrant:
	docker compose run --rm --no-deps api python -c 'from ol.config import qclient; c=qclient(); c.get_collections(); print("Qdrant authenticated connection is healthy"); c.close()'

test-teradata:
	docker compose --profile teradata run --rm teradata-client python /app/healthcheck.py


.PHONY: config build up up-all down logs status test-qdrant test-teradata

config:
	docker compose config --quiet

build:
	docker compose --profile teradata build

up:
	docker compose up -d --build office-lunch api vector-worker

up-all:
	docker compose --profile teradata up -d --build office-lunch api vector-worker teradata-client

down:
	docker compose --profile teradata down

logs:
	docker compose --profile teradata logs -f

status:
	docker compose --profile teradata ps

test-qdrant:
	docker compose run --rm --no-deps api python -c 'from ol.config import qclient; c=qclient(); c.get_collections(); print("Qdrant authenticated connection is healthy"); c.close()'

test-teradata:
	docker compose --profile teradata run --rm teradata-client python /app/healthcheck.py


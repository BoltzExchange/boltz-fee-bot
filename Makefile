POSTGRES_USER=boltz
POSTGRES_PASSWORD=boltz
POSTGRES_DB=fees
POSTGRES_PORT=5433

.PHONY: postgres postgres-stop

postgres:
	@docker start boltz-fees-postgres 2>/dev/null || \
		docker run --rm -d \
			--name boltz-fees-postgres \
			-e POSTGRES_USER=$(POSTGRES_USER) \
			-e POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) \
			-e POSTGRES_DB=$(POSTGRES_DB) \
			-p $(POSTGRES_PORT):5432 \
			postgres:17-alpine
	@docker exec boltz-fees-postgres bash -c "while ! pg_isready -U $(POSTGRES_USER) -d $(POSTGRES_DB) -q; do sleep 1; done"

postgres-stop:
	-docker stop boltz-fees-postgres

run:
	uv run alembic upgrade head
	uv run bot.py

test:
	uv run pytest --ignore=tests/e2e -m "not db"

test-all: postgres
	uv run pytest

format:
	uv run ruff format

check:
	uv run ruff check --fix

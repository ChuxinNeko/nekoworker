.PHONY: up down test check
up:
	./scripts/up.sh
down:
	docker compose down
check:
	.venv/bin/ruff check src tests
	.venv/bin/ruff format --check src tests
	.venv/bin/pytest -q

test:
	.venv/bin/pytest -q

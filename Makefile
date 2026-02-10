.PHONY: lint lint-verify python-lint python-lint-verify test build sync clean

lint: python-lint

lint-verify: python-lint-verify

python-lint:
	uv run ruff format .
	uv run ruff check . --fix
	uv run ty check src tests

python-lint-verify:
	uv run ruff format --check .
	uv run ruff check .
	uv run ty check src tests

test:
	uv run pytest

build:
	uv build

sync:
	uv sync --dev

clean:
	rm -rf .ruff_cache .pytest_cache dist

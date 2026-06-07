.PHONY: install test lint build docker run clean help

help:
	@echo "OPP targets:"
	@echo "  install  - uv sync --all-extras"
	@echo "  test     - run pytest suite"
	@echo "  lint     - ruff check src/ tests/"
	@echo "  build    - uv build (wheel + sdist)"
	@echo "  docker   - build the Docker image (tag: opp:dev)"
	@echo "  run      - show opp --help via uv"
	@echo "  clean    - remove build artifacts and __pycache__ dirs"

install:
	uv sync --all-extras

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/

build:
	uv build

docker:
	docker build -t opp:dev .

run:
	uv run opp --help

clean:
	rm -rf .venv build/ dist/ *.egg-info
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

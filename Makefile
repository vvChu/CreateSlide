.PHONY: help run test lint format typecheck clean docker-build docker-run install

PYTHON := .venv/bin/python
MESOP  := .venv/bin/mesop
PORT   := 32123

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies into .venv
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install ruff mypy pytest pytest-asyncio
	@echo "✅ Installed. Activate with: source .venv/bin/activate"

run: ## Start the Mesop dev server
	$(MESOP) main.py --port $(PORT)

test: ## Run unit tests
	$(PYTHON) -m pytest tests/ -v --tb=short

test-integration: ## Run integration tests (requires live Ollama)
	$(PYTHON) -m pytest tests/ -v --run-integration

lint: ## Run ruff linter
	$(PYTHON) -m ruff check app/ tests/

format: ## Auto-format code with ruff
	$(PYTHON) -m ruff format app/ tests/
	$(PYTHON) -m ruff check --fix app/ tests/

typecheck: ## Run mypy type checker
	$(PYTHON) -m mypy app/ --ignore-missing-imports

clean: ## Remove build artefacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .pytest_cache .ruff_cache htmlcov .coverage
	rm -f *.pptx *.pdf cancel_signal.flag app.log

docker-build: ## Build Docker image
	docker build -t createslide:latest .

docker-run: ## Run in Docker (uses .env for config)
	docker run --rm -p $(PORT):32123 --env-file .env \
		--add-host=host.docker.internal:host-gateway \
		createslide:latest

ci: lint test ## Run CI checks locally (lint + test)

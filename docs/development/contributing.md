# Contributing

Thank you for your interest in contributing to SlideGenius!

## Development Setup

```bash
# Clone and set up
git clone https://github.com/vvChu/CreateSlide.git
cd CreateSlide
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install dev tools
pip install pytest pytest-cov pytest-asyncio ruff mypy pre-commit

# Set up pre-commit hooks
pre-commit install
```

## Code Style

We use **ruff** for linting and formatting:

```bash
# Check style
make lint

# Auto-fix
make format
```

Key conventions:

- **Line length**: 99 characters
- **Docstrings**: Google style
- **Type hints**: Encouraged on all public functions
- **Imports**: Sorted by ruff (isort-compatible)

## Project Structure

Follow the existing module layout:

| Layer | Location | Purpose |
|---|---|---|
| Config | `app/config.py` | Settings and validation |
| Core | `app/core/` | Utilities (logging, JSON, cancel) |
| Prompts | `app/prompts/` | LLM prompt templates |
| Providers | `app/providers/` | LLM API integrations |
| Services | `app/services/` | Business logic |
| Rendering | `app/rendering/` | PDF/PPTX generation |
| UI | `app/ui/` | Mesop web interface |
| Tests | `tests/` | pytest test suite |

## Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Write code** following the patterns in existing modules

3. **Add tests** — target >85% coverage for new code:
   ```bash
   make test        # Run all tests
   make coverage    # Run with coverage report
   ```

4. **Run checks**:
   ```bash
   make lint        # Linting
   make format      # Auto-format
   make typecheck   # Type checking (if mypy is configured)
   ```

5. **Commit** using conventional commits:
   ```
   feat: add new provider for X
   fix: handle edge case in JSON parsing
   docs: update configuration reference
   test: add coverage for review service
   ```

6. **Open a Pull Request** against `main`

## Adding a New LLM Provider

See the [Provider Architecture](../architecture/providers.md) guide for step-by-step instructions.

## Reporting Issues

Open an issue on GitHub with:

- **Description** of the problem
- **Steps to reproduce**
- **Expected vs actual behaviour**
- **Environment** (Python version, OS, provider)

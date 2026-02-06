# Installation

## Prerequisites

- Python 3.11+ (3.12 recommended)
- Git

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/vvChu/CreateSlide.git
cd CreateSlide
```

### 2. Create virtual environment and install dependencies

```bash
make install
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv/bin/pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Run the application

```bash
make run
# Opens at http://localhost:32123
```

## Docker Installation

```bash
make docker-build
make docker-run
```

## Optional Dependencies

For additional providers:

```bash
pip install anthropic    # Anthropic Claude support
pip install litellm      # LiteLLM universal adapter (100+ providers)
```

## Development Tools

```bash
pip install ruff mypy pytest pytest-asyncio pytest-cov pre-commit
pre-commit install
```

# Python Development Guide

Reference for environment setup and commands (dev, tests, lint). Package: `derush/` (not `src/`).

## Setup (once)

Python 3.10–3.14. From project root:

```bash
python3 -m venv venv
./venv/bin/pip install -e ".[dev,lint]"
```

For local FCPXML export, add the `export` extra: `".[dev,lint,export]"`.

## Commands

| Action   | Command |
|----------|---------|
| Tests    | `make test` or `./venv/bin/pytest tests/ -v` |
| Lint     | `make lint` or `./venv/bin/ruff check derush/ tests/` |
| Format   | `make format` or `./venv/bin/ruff format derush/ tests/` |
| App      | `./venv/bin/derush --help` (or `derush` with venv activated) |

Always run from repository root. Don't assume `python`, `pytest` or `ruff` are in PATH (use `make` or `./venv/bin/...`). If venv doesn't exist: `make install` or commands above.

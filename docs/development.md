# Development

This repository uses `uv` for dependency management, build execution, and developer tooling.

## Local setup

1. Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Sync the project dependencies:

```bash
uv sync
```

3. Run the package locally:

```bash
uv run python -m stelint
```

## Pre-commit and quality checks

Run the configured pre-commit hooks with:

```bash
uv run pre-commit run --all-files
```

This project includes hooks to ensure:

- `uv.lock` is present and tracked
- `ruff` linting passes
- `pytest` test suite passes

## Build and publishing

Build the package for distribution:

```bash
uv run python -m build
```

Publish to PyPI:

```bash
uv run python -m twine upload --repository pypi dist/*
```

## Documentation site

Build the documentation site with Zensical:

```bash
uv run python -m zensical build
```

The site is published via GitHub Pages from the `gh-pages` branch.

## GitHub Actions

All CI workflows use `uv` for dependency management, environment sync, and Python execution.

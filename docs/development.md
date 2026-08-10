# Development

This repository uses `uv` for dependency management, the package building, and the developer tooling.

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

Do the configured pre-commit hooks for all files:

```bash
uv run pre-commit run --all-files
```

This project uses these hooks:

- Verify that the `uv.lock` file exists, is in the git index, and up-to-date.
- Run `ruff` for linting
- Run the pytest suite

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

GitHub Actions publishes the site via GitHub Pages from the gh-pages branch.

## GitHub Actions

All CI workflows use `uv` for dependency management, the environment sync, and the Python execution.

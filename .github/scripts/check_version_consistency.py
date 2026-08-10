#!/usr/bin/env python3
"""Check that pyproject.toml version and CHANGELOG.md version are in sync."""

import re
import sys
from pathlib import Path


def get_pyproject_version() -> str:
    """Get version from pyproject.toml."""
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        print("Error: pyproject.toml not found", file=sys.stderr)
        sys.exit(1)

    match = re.search(r"^version\s*=\s*\"([^\"]+)\"", pyproject.read_text(), re.MULTILINE)
    if not match:
        print("Error: Could not find version in pyproject.toml", file=sys.stderr)
        sys.exit(1)

    return match.group(1)


def get_changelog_version() -> str:
    """Get version from CHANGELOG.md (first version under Unreleased)."""
    changelog = Path("CHANGELOG.md")
    if not changelog.exists():
        print("Error: CHANGELOG.md not found", file=sys.stderr)
        sys.exit(1)

    content = changelog.read_text()

    # Find the first version after [Unreleased]
    unreleased_match = re.search(r"## \[Unreleased\]", content)
    if not unreleased_match:
        print("Error: [Unreleased] section not found in CHANGELOG.md", file=sys.stderr)
        sys.exit(1)

    # Get content after Unreleased
    after_unreleased = content[unreleased_match.end() :]

    # Find first version match
    match = re.search(r"## \[(\d+\.\d+\.\d+)\]", after_unreleased)
    if not match:
        print("Warning: No version found in CHANGELOG.md after [Unreleased]", file=sys.stderr)
        return None

    return match.group(1)


def main() -> None:
    pyproject_ver = get_pyproject_version()
    changelog_ver = get_changelog_version()

    errors = []

    if changelog_ver and pyproject_ver != changelog_ver:
        errors.append(f"pyproject.toml version ({pyproject_ver}) != CHANGELOG.md version ({changelog_ver})")

    if errors:
        print("Version consistency check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)

    print(f"Versions in sync: {pyproject_ver}")


if __name__ == "__main__":
    main()

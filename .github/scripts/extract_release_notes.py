"""Extract release notes for a given version from CHANGELOG.md."""

import re
import sys
from pathlib import Path

CHANGELOG_PATH = Path("CHANGELOG.md")
VERSION_HEADING_RE = re.compile(r'^## \[([^\]]+)\]', re.MULTILINE)


def extract_release_notes(version: str) -> str:
    if not CHANGELOG_PATH.is_file():
        raise SystemExit(
            f"Error: {CHANGELOG_PATH} not found. "
            f"Cannot extract release notes for version {version!r}."
        )

    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        rf'^## \[{re.escape(version)}\].*?$', re.MULTILINE
    )
    matches = list(pattern.finditer(text))

    if not matches:
        # Try matching the version as a prefix (e.g., version="1.0" matches "[1.0.0]")
        prefix_pattern = re.compile(
            rf'^## \[{re.escape(version)}(\.[\d+]*)?\].*?$', re.MULTILINE
        )
        matches = list(prefix_pattern.finditer(text))

    if not matches:
        raise SystemExit(
            f"No changelog section found for version {version!r}. "
            f"Available versions: "
            f"{', '.join(m.group(1) for m in VERSION_HEADING_RE.finditer(text))}"
        )

    match = matches[0]
    start = match.start()
    remaining = text[match.end():]
    next_section = VERSION_HEADING_RE.search(remaining)
    end = match.end() + next_section.start() if next_section else len(text)

    return text[start:end].strip()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: extract_release_notes.py <version>")
    version = sys.argv[1]
    print(extract_release_notes(version))


if __name__ == "__main__":
    main()

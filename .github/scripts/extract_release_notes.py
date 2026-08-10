#!/usr/bin/env python3
import re
from pathlib import Path
import sys

def extract_release_notes(version: str) -> str:
    text = Path('CHANGELOG.md').read_text(encoding='utf-8')
    pattern = rf'^## \[{re.escape(version)}\].*?$'
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
    if not matches:
        raise SystemExit(f'No changelog section found for {version}')

    start = matches[0].start()
    next_section = re.search(r'^## \[', text[matches[0].end():], flags=re.MULTILINE)
    end = matches[0].end() + next_section.start() if next_section else len(text)

    return text[start:end].strip()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit('Usage: extract_release_notes.py <version>')
    version = sys.argv[1]
    print(extract_release_notes(version))


if __name__ == '__main__':
    main()

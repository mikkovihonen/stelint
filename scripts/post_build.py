"""Post-build script to fix asset paths in generated HTML.

Rewrites paths that reference the docs/ directory to their site-relative equivalents.
"""

import re
import sys
from pathlib import Path


def fix_asset_paths(site_dir: Path) -> None:
    """Fix asset paths in all HTML files in the site directory."""
    for html_file in site_dir.rglob("*.html"):
        content = html_file.read_text()
        # Rewrite docs/assets/... to assets/...
        content = re.sub(r'src="docs/assets/(.*?)"', r'src="assets/\1"', content)
        content = re.sub(r'href="docs/assets/(.*?)"', r'href="assets/\1"', content)
        html_file.write_text(content)


if __name__ == "__main__":
    site_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("site")
    fix_asset_paths(site_dir)

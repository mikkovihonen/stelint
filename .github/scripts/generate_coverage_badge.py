"""Generate a coverage.svg badge from the .coverage file."""

import argparse
import os
import sys

from coverage import Coverage
from coverage.exceptions import NoDataError

DEFAULT_OUTPUT_DIR = os.path.join("docs", "assets")
DEFAULT_OUTPUT_FILE = os.path.join(DEFAULT_OUTPUT_DIR, "coverage.svg")

# Shields.io-style badge dimensions (3/5 label, 2/5 value)
WIDTH = 114
LEFT_WIDTH = 68
RIGHT_WIDTH = 46
HEIGHT = 20

# Text content
LEFT_TEXT = "coverage"

# Text positions (scaled by 10 to match font-size 110)
LEFT_X = 340  # center of 68px section (68/2 * 10)
RIGHT_X = 910  # center of right section ((68 + 46/2) * 10)

# Text lengths tuned for visual centering
LEFT_TEXT_LENGTH = 530
RIGHT_TEXT_LENGTH = 280

# Reasonable blur for a 20px badge
BLUR_STD_DEVIATION = 0.8


def generate_badge(coverage_pct: float, precision: int = 0) -> str:
    """Generate a Shields.io-style coverage badge SVG.

    Args:
        coverage_pct: Coverage percentage (0–100).
        precision: Number of decimal places for the percentage display.
    """
    if coverage_pct >= 90:
        right_color = "#4c1"  # bright green
    elif coverage_pct >= 75:
        right_color = "#dfb317"  # yellow
    else:
        right_color = "#e05d44"  # red

    coverage_str = f"{coverage_pct:.{precision}f}%"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="coverage: {coverage_str}">
  <title>coverage: {coverage_str}</title>
  <filter id="blur"><feGaussianBlur stdDeviation="{BLUR_STD_DEVIATION}"/></filter>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{WIDTH}" height="{HEIGHT}" rx="3"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{LEFT_WIDTH}" height="{HEIGHT}" fill="#555"/>
    <rect x="{LEFT_WIDTH}" width="{RIGHT_WIDTH}" height="{HEIGHT}" fill="{right_color}"/>
    <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
    <g transform="scale(.1)">
      <g aria-hidden="true" fill="#010101">
        <text x="{LEFT_X}" y="150" fill-opacity=".8" filter="url(#blur)">{LEFT_TEXT}</text>
        <text x="{LEFT_X}" y="150" fill-opacity=".3" textLength="{LEFT_TEXT_LENGTH}">{LEFT_TEXT}</text>
      </g>
      <text x="{LEFT_X}" y="140" textLength="{LEFT_TEXT_LENGTH}">{LEFT_TEXT}</text>
    </g>
    <g transform="scale(.1)">
      <g aria-hidden="true" fill="#010101">
        <text x="{RIGHT_X}" y="150" fill-opacity=".8" filter="url(#blur)">{coverage_str}</text>
        <text x="{RIGHT_X}" y="150" fill-opacity=".3" textLength="{RIGHT_TEXT_LENGTH}">{coverage_str}</text>
      </g>
      <text x="{RIGHT_X}" y="140" textLength="{RIGHT_TEXT_LENGTH}">{coverage_str}</text>
    </g>
  </g>
</svg>"""

    return svg


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a coverage.svg badge from the .coverage file.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help=f"Output SVG path (default: {DEFAULT_OUTPUT_FILE})",
        default=DEFAULT_OUTPUT_FILE,
    )
    parser.add_argument(
        "--precision",
        "-p",
        type=int,
        default=1,
        help="Decimal places for coverage percentage (default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the SVG to stdout without writing to disk",
    )
    args = parser.parse_args()

    c = Coverage()
    try:
        c.load()
    except FileNotFoundError:
        print("No .coverage data file found — skipping badge generation.", file=sys.stderr)
        sys.exit(0)

    try:
        total = c.report()
    except NoDataError:
        print("No .coverage data found — skipping badge generation.", file=sys.stderr)
        sys.exit(0)

    svg = generate_badge(total, precision=args.precision)

    if args.dry_run:
        print(svg)
        return

    output_dir = os.path.dirname(args.output)
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as exc:
        raise SystemExit(f"Cannot create output directory {output_dir!r}: {exc}")

    try:
        with open(args.output, "w") as f:
            f.write(svg)
    except OSError as exc:
        raise SystemExit(f"Cannot write to {args.output!r}: {exc}")

    print(f"Coverage badge written: {total:.{args.precision}f}% → {args.output}")


if __name__ == "__main__":
    main()

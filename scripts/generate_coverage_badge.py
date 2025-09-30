#!/usr/bin/env python3
"""Generate a dynamic test coverage badge from coverage.json."""

import json
import sys
from pathlib import Path


def get_coverage_color(percentage: float) -> str:
    """Determine badge color based on coverage percentage."""
    if percentage >= 90:
        return "#4c1"  # Bright green
    elif percentage >= 80:
        return "#97ca00"  # Green
    elif percentage >= 70:
        return "#a4a61d"  # Yellow-green
    elif percentage >= 60:
        return "#dfb317"  # Yellow
    elif percentage >= 50:
        return "#fe7d37"  # Orange
    else:
        return "#e05d44"  # Red


def generate_badge_svg(coverage_percent: int, color: str) -> str:
    """Generate SVG badge content."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="140" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="a">
    <rect width="140" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#a)">
    <path fill="#555" d="M0 0h99v20H0z"/>
    <path fill="{color}" d="M99 0h41v20H99z"/>
    <path fill="url(#b)" d="M0 0h140v20H0z"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="110">
    <text x="505" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="890">Test coverage</text>
    <text x="505" y="140" transform="scale(.1)" textLength="890">Test coverage</text>
    <text x="1195" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="310">{coverage_percent}%</text>
    <text x="1195" y="140" transform="scale(.1)" textLength="310">{coverage_percent}%</text>
  </g>
</svg>"""


def main() -> None:
    """Generate coverage badge from coverage.json."""
    coverage_file = Path("coverage.json")

    if not coverage_file.exists():
        print("Error: coverage.json not found. Run pytest with --cov-report=json first.")
        sys.exit(1)

    try:
        with open(coverage_file) as f:
            coverage_data = json.load(f)

        coverage_percent = round(coverage_data["totals"]["percent_covered"])
        color = get_coverage_color(coverage_percent)

        # Create badges directory
        badges_dir = Path(".github/badges")
        badges_dir.mkdir(parents=True, exist_ok=True)

        # Generate and write badge
        badge_svg = generate_badge_svg(coverage_percent, color)
        badge_file = badges_dir / "coverage.svg"

        with open(badge_file, "w") as f:
            f.write(badge_svg)

        print(f"Generated coverage badge: {coverage_percent}% ({color})")
        print(f"Badge saved to: {badge_file}")

    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error reading coverage data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

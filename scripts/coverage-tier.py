#!/usr/bin/env python3
"""Print one coverage tier floor from services/app/pyproject.toml.

Usage: coverage-tier.py <unit|integration|floor>

pyproject's [tool.studyaio.coverage-tiers] is the single source of truth, so the
Makefile, scripts/test-integration.sh and .gitlab-ci.yml read it here instead of
repeating the number. Exits non-zero (and prints nothing on stdout) if the tier is
missing, so a typo fails the gate rather than silently disabling it.

COVERAGE_TIERS_FILE overrides the pyproject path (used to prove a raised floor
fails the gate without editing the tree).
"""

import os
import sys
import tomllib
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent.parent / "services" / "app" / "pyproject.toml"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <tier>", file=sys.stderr)
        return 2
    path = Path(os.environ.get("COVERAGE_TIERS_FILE", DEFAULT))
    tiers = tomllib.loads(path.read_text())["tool"]["studyaio"]["coverage-tiers"]
    if argv[1] not in tiers:
        print(
            f"unknown coverage tier {argv[1]!r}; known: {sorted(tiers)}",
            file=sys.stderr,
        )
        return 1
    print(tiers[argv[1]])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

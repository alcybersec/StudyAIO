"""Pin the coverage tier thresholds from docs/strategy.md section 3."""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _load() -> dict:
    return tomllib.loads(PYPROJECT.read_text())


def test_tier_thresholds_match_strategy() -> None:
    tiers = _load()["tool"]["studyaio"]["coverage-tiers"]
    assert tiers == {"unit": 75, "integration": 70, "floor": 95}


def test_coverage_py_fail_under_is_the_unit_tier() -> None:
    cfg = _load()["tool"]
    assert cfg["coverage"]["report"]["fail_under"] == cfg["studyaio"]["coverage-tiers"]["unit"]

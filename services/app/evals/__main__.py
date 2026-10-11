"""Command line for the summary evals: ``python -m evals``.

Two modes:

* ``--offline`` (the CI mode) scores the stored summaries in ``evals/fixtures/``
  with deterministic checks. No AI call, no secrets. Add ``--check`` to compare
  with ``evals/baseline.json`` and exit non-zero on a regression.
* ``--live`` generates summaries through the agent adapter, exactly as the
  existing ``python -m app.cli evals`` path does (it reuses ``evals.runner.run``,
  the one place the evals obtain an adapter). For an operator refreshing
  fixtures and the baseline; costs AI calls.

Refreshing, as an operator::

    python -m evals --live --no-judge --save-fixtures
    python -m evals --offline --write-baseline
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from evals.offline import (
    BASELINE_PATH,
    DEFAULT_THRESHOLD,
    FIXTURES_DIR,
    check_against_baseline,
    format_offline_report,
    load_baseline,
    run_offline,
)
from evals.runner import format_report, load_cases


def _offline(args: argparse.Namespace) -> int:
    cases = load_cases(args.case)
    run = run_offline(cases, Path(args.fixtures))

    if args.write_baseline:
        if run.missing_fixtures:
            print(f"cannot write a baseline: no fixture for {', '.join(run.missing_fixtures)}")
            return 1
        provenance = None
        if args.model:
            provenance = {
                "source": "live",
                "model": args.model,
                "date": args.date,
                "judge": not args.no_judge,
            }
        text = json.dumps(run.to_baseline(args.threshold, provenance), indent=2, sort_keys=True)
        BASELINE_PATH.write_text(text + "\n")
        print(format_offline_report(run, None, []))
        print(f"\nBaseline written to {BASELINE_PATH}")
        return 0

    baseline = None
    failures: list[str] = []
    if args.check:
        try:
            baseline = load_baseline()
        except FileNotFoundError as e:
            print(f"RESULT: FAIL\n  - {e}")
            return 1
        failures = check_against_baseline(run, baseline, expect_all_cases=args.case is None)

    print(format_offline_report(run, baseline, failures))
    if args.out:
        Path(args.out).write_text(json.dumps(run.to_baseline(args.threshold), indent=2) + "\n")
    return 1 if failures else 0


async def _live(args: argparse.Namespace) -> int:
    from evals.runner import run

    save_to = Path(args.fixtures) if args.save_fixtures else None
    report = await run(only=args.case, judge=not args.no_judge, n=args.n, save_summaries_to=save_to)
    print(format_report(report))
    if save_to:
        print(f"\nSummaries written to {save_to}")
    if args.out:
        Path(args.out).write_text(json.dumps(report.to_dict(), indent=2) + "\n")
    return 0 if report.passed == len(report.cases) else 1


def build_parser() -> argparse.ArgumentParser:
    """The argument parser, separate so tests can drive it."""
    parser = argparse.ArgumentParser(prog="python -m evals", description="Summary evals")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true", help="Score stored fixtures (CI mode)")
    mode.add_argument("--live", action="store_true", help="Generate via the agent adapter")
    parser.add_argument("--case", default=None, help="Restrict to one case id")
    parser.add_argument("--check", action="store_true", help="Offline: fail on a regression")
    parser.add_argument("--write-baseline", action="store_true", help="Offline: rewrite baseline")
    parser.add_argument("--model", default=None, help="Write-baseline: model id of the fixtures")
    parser.add_argument("--date", default=None, help="Write-baseline: date the fixtures were made")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--fixtures", default=str(FIXTURES_DIR), help="Fixture directory")
    parser.add_argument("--save-fixtures", action="store_true", help="Live: store as fixtures")
    parser.add_argument("--no-judge", action="store_true", help="Live: skip the model judge")
    parser.add_argument("-n", type=int, default=1, help="Live: runs per case")
    parser.add_argument("--out", default=None, help="Write the JSON report here")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the chosen mode. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.live and (args.check or args.write_baseline):
        parser.error("--check and --write-baseline are offline-only")
    if args.offline:
        return _offline(args)
    return asyncio.run(_live(args))


if __name__ == "__main__":
    sys.exit(main())

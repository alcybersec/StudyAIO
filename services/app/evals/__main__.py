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

Several runs per case (``-n/--runs N``) save ``<case>.run<k>.md``; score them with
``--offline --per-run --fixtures <dir>``. Saved text is post-footer-normaliser (what
users get), not the raw model output.
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
    format_multirun_report,
    format_offline_report,
    load_baseline,
    run_offline,
    run_offline_runs,
)
from evals.runner import format_report, load_cases


def _parse_extras(pairs: list[str]) -> dict:
    """``KEY=VALUE`` pairs for the provenance block; values parse as JSON when they can."""
    out: dict = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise SystemExit(f"--provenance expects KEY=VALUE, got {pair!r}")
        try:
            out[key] = json.loads(value)
        except ValueError:
            out[key] = value
    return out


def _offline(args: argparse.Namespace) -> int:
    cases = load_cases(args.case)
    if args.per_run:
        multi = run_offline_runs(cases, Path(args.fixtures))
        print(format_multirun_report(multi))
        return 1 if multi.bar_failures() else 0
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
            provenance.update(_parse_extras(args.provenance))
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
    report = await run(
        only=args.case,
        judge=not args.no_judge,
        n=args.n,
        save_summaries_to=save_to,
        temperature=args.temperature,
    )
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
    parser.add_argument(
        "--provenance",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Write-baseline: extra provenance (prompt, temperature, runs, chosen_run), repeatable",
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--fixtures", default=str(FIXTURES_DIR), help="Fixture directory")
    parser.add_argument("--save-fixtures", action="store_true", help="Live: store as fixtures")
    parser.add_argument("--no-judge", action="store_true", help="Live: skip the model judge")
    parser.add_argument(
        "--per-run",
        action="store_true",
        help="Offline: score <id>.run<k>.md files, report per-run and mean, judge the bar",
    )
    parser.add_argument("-n", "--runs", dest="n", type=int, default=1, help="Live: runs per case")
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Live: override the summarization temperature (default: the setting)",
    )
    parser.add_argument("--out", default=None, help="Write the JSON report here")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the chosen mode. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.live and (args.check or args.write_baseline or args.per_run):
        parser.error("--check, --write-baseline and --per-run are offline-only")
    if args.offline and args.temperature is not None:
        parser.error("--temperature is live-only")
    if args.per_run and (args.check or args.write_baseline):
        parser.error("--per-run cannot be combined with --check or --write-baseline")
    if args.offline:
        return _offline(args)
    return asyncio.run(_live(args))


if __name__ == "__main__":
    sys.exit(main())

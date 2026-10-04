# ADR 0001 — Adopt the agentic-kit orchestrator model

**Status** Accepted · **Date** 2026-10-04 · **Kit version** 1.10.3

## Context

StudyAIO is developed with Claude Code sessions. Without an explicit operating model, work
arrives without owners, tests are claimed rather than run, and invariants regress silently.

## Decision

Adopt the `agentic-kit` orchestrator model:

- A default **Orchestrator** that plans, dispatches and validates, and writes no implementation code.
- 8 roles with **exclusive file-path ownership**, listed in
  `docs/strategy.md` §2.
- **`safety` holds a veto** on gates, scoped to the floors in `docs/strategy.md` §6.
- A docs spine as the source of truth: `docs/plan/README.md` for state,
  `docs/strategy.md` for rules and the task graph.
- Handoff notes carrying pasted test evidence.
- Guard hooks from the plugin that make the atomic-commit and secret-path rules executable rather
  than advisory.

## Consequences

- The first turn of a session costs a documented read of the load order in `CLAUDE.md`.
- Ownership boundaries must partition; adding a role means redistributing globs.
- Floors cannot be weakened without a further ADR.
- `glab` is the only forge CLI, enforced by `pre-bash-guard`.

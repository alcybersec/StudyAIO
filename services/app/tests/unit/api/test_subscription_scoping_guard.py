"""Structural guard against the third leak shape, from #69.

`test_endpoint_authn_guard` asks "does this endpoint require a caller?" and
`test_endpoint_scoping_guard` asks "does this id-addressed lookup carry the
caller's identity?". `GET /api/uploads/pipeline-events` passed both and still
handed every tenant every other tenant's pipeline events, because the leak was
not a lookup at all — it subscribed to one instance-wide Redis pub/sub channel
and fanned it out to whoever was connected.

## The rule

Anywhere under `app/api/`, a `*.subscribe(...)` call must be handed something
derived from the caller's identity — resolving its arguments (positional and
keyword) through the file's assignments must reach `user.id` / `user_id`. A
literal or module-constant channel name is shared by definition, so every
subscriber to it receives every publisher's messages.

The rule is deliberately about the *name* `subscribe` rather than about Redis,
so it also covers `push_service.subscribe` in `notifications.py` and whatever
subscription is added next.

## Why the argument is resolved rather than grepped

`await pubsub.subscribe(channel)` is the natural way to write this when the
same name is needed again to unsubscribe, so a check that only looked at the
call site's own text would flag correct code and push authors to inline the
expression. Going the other way and asking "does the enclosing function mention
`user.id` anywhere?" is what `test_endpoint_scoping_guard`'s docstring rejects:
a handler can pass the identity to a logger while doing the sensitive thing
unscoped. Resolving the assignment chain is the middle: it is the *channel* that
has to carry the identity.

## Adding an entry

A genuinely instance-wide subscription (an admin-only firehose, a channel that
carries no per-user data) goes in `SHARED_CHANNEL_ALLOWED` **with a reason**.
The allowlist is asserted exact in both directions, so a site that later
becomes per-user must be removed from it.
"""

import ast
import pathlib

API_DIR = pathlib.Path(__file__).resolve().parents[3] / "app" / "api"

# Expressions that prove the channel is per-caller.
IDENTITY_MARKERS = ("user.id", "user_id")

# `{file}:{call source}` -> reason, for subscriptions that are deliberately
# instance-wide. Empty today: every subscription in app/api/ is per-user.
SHARED_CHANNEL_ALLOWED: dict[str, str] = {}

# How many assignment hops to follow (channel = prefix + suffix = ...).
_MAX_HOPS = 5


def _assignments(source: str, tree: ast.AST) -> dict[str, list[ast.expr]]:
    """Map every name assigned anywhere in the file to the values assigned to it.

    File-wide rather than per-function on purpose: a name is only consulted when
    the channel expression actually references it, and being generous here can
    only ever make the guard *stricter* to satisfy, never laxer.
    """
    assignments: dict[str, list[ast.expr]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                assignments.setdefault(target.id, []).append(value)
    return assignments


def _resolved(args: list[ast.expr], source: str, assignments: dict[str, list[ast.expr]]) -> str:
    """The source of the channel expression plus everything its names resolve to."""
    pending = list(args)
    seen_names: set[str] = set()
    chunks: list[str] = []
    for _ in range(_MAX_HOPS):
        if not pending:
            break
        names: set[str] = set()
        for expr in pending:
            chunks.append(ast.get_source_segment(source, expr) or "")
            for node in ast.walk(expr):
                if isinstance(node, ast.Name):
                    names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    # `user.id` must survive as a unit, and dump() keeps it.
                    chunks.append(ast.get_source_segment(source, node) or "")
        fresh = names - seen_names
        seen_names |= fresh
        pending = [v for name in fresh for v in assignments.get(name, [])]
    return " ".join(chunks)


def _subscribe_calls() -> list[tuple[str, int, str, str]]:
    """Every `*.subscribe(...)` under app/api/, as (file, line, source, resolved args)."""
    found = []
    for path in sorted(API_DIR.rglob("*.py")):
        source = path.read_text()
        tree = ast.parse(source)
        assignments = _assignments(source, tree)
        for node in ast.walk(tree):
            func = getattr(node, "func", None)
            if not isinstance(node, ast.Call) or not isinstance(func, ast.Attribute):
                continue
            if func.attr != "subscribe":
                continue
            found.append(
                (
                    path.name,
                    node.lineno,
                    ast.get_source_segment(source, node) or "",
                    _resolved(
                        [*node.args, *(kw.value for kw in node.keywords)], source, assignments
                    ),
                )
            )
    return sorted(found)


def test_every_api_subscription_is_scoped_to_the_caller():
    """No endpoint may subscribe to a channel that is not the caller's own."""
    calls = _subscribe_calls()
    assert calls, "guard found no subscribe() calls at all — has app/api moved?"

    unscoped = []
    for filename, lineno, src, resolved in calls:
        key = f"{filename}:{src}"
        if key in SHARED_CHANNEL_ALLOWED:
            continue
        if not any(marker in resolved for marker in IDENTITY_MARKERS):
            unscoped.append(f"{filename}:{lineno}  {src}  (resolves to: {resolved})")

    assert not unscoped, (
        "pub/sub subscription in an API module is not scoped to the caller — "
        "every subscriber to a shared channel receives every publisher's "
        "messages (#69):\n  " + "\n  ".join(unscoped)
    )


def test_allowlist_has_no_stale_entries():
    """A subscription that became per-user must leave the allowlist."""
    keys = {f"{filename}:{src}" for filename, _, src, _resolved_src in _subscribe_calls()}
    stale = sorted(set(SHARED_CHANNEL_ALLOWED) - keys)
    assert not stale, f"SHARED_CHANNEL_ALLOWED entries no longer exist: {stale}"

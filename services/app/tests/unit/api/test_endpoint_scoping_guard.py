"""Structural guard against the IDOR class in #47 and #53.

Six clusters were fixed in #53, and one in #50 before them. Both were found
by hand, and both sweeps missed things -- this check, run against the tree as
it stood before #53, flags every one of those six clusters *and* eleven more
in `courseops` that three rounds of manual review walked past.

Grep-and-fix only holds until the next endpoint is written. This test covers
the endpoints nobody has written yet.

## The rule

Inside an API endpoint, a call that

  * takes ``session`` as its first positional argument (i.e. it is a service
    or repository call, not ``HTTPException`` or a logger), **and**
  * is handed one of the endpoint's own object-identifying parameters --
    anything ending in ``_id`` / ``_code`` / ``_token``, which by definition
    came from the request and is therefore attacker-controlled

must also be handed the caller's identity, as ``user_id=``/``user.id``.

Otherwise the endpoint resolves an object from a caller-supplied id without
ever asking whose object it is.

## Why not something simpler

"Does the handler mention ``user.id`` anywhere?" is the obvious cheap check
and it does not work. Before #53, ``resolve_review_item`` passed
``user_id=user.id`` to ``resume_pipeline`` for logging while looking the
review item itself up unscoped -- a mention-based check calls that endpoint
clean. It has to be the *lookup* that carries the identity.

## Adding an entry

A new finding means one of three things. Fix the endpoint, or, if the call is
genuinely safe, add it to ``GUARDED_ELSEWHERE`` **with a reason** -- an
ownership check earlier in the same handler, or an admin-only route. The
allowlist is asserted to be exact in both directions, so a fixed endpoint
must also be removed from it.
"""

import ast
import pathlib

import pytest

# Parameters that are never an object identifier, so a call receiving one of
# these is not an id-addressed lookup.
NON_OBJECT_PARAMS = frozenset(
    {
        "user",
        "session",
        "request",
        "response",
        "body",
        "background_tasks",
        "file",
        "files",
        "limit",
        "offset",
        "days",
        "week",
        "status",
        "page",
        "q",
        "query",
        "upcoming",
    }
)

SESSION_ARG_NAMES = frozenset({"session", "db"})

# ---------------------------------------------------------------------------
# Allowlist. Key is "<module>:<endpoint>:<called>". Every entry needs a reason.
# ---------------------------------------------------------------------------

GUARDED_ELSEWHERE: dict[str, str] = {
    # An owner-scoped lookup runs earlier in the same handler and 404s first,
    # so the unscoped call below it can only ever see an already-authorised id.
    "uploads:get_upload_status:pipeline_service.get_artifact_pipeline_runs": (
        "guarded by get_artifact(..., user_id=user.id) immediately above (#53 cluster 6)"
    ),
    "uploads:retry_pipeline:pipeline_service.get_artifact_pipeline_runs": (
        "guarded by get_artifact(..., user_id=user.id) at the top of the handler"
    ),
    "courses:get_week_detail:summary_service.get_summary_for_week": (
        "guarded by get_course_by_code(..., user_id=user.id) three lines earlier"
    ),
    # Admin-only routes: authorisation is the role check, not object ownership.
    "admin:revoke_invite:invite_service.revoke_invite": (
        "admin-only route behind require_role('admin'); invites have no per-user owner"
    ),
}

# Real, currently-unfixed findings. Deliberately NOT fixed in the #53 PR to
# keep it reviewable -- the whole courseops router is unscoped, including five
# write paths, which is its own issue rather than a footnote in someone
# else's. Every line here is a live IDOR; delete entries as they are fixed.
KNOWN_UNSCOPED_PENDING_FIX: dict[str, str] = {
    "courseops:update_assessment:courseops_service.update_assessment": "WRITE",
    "courseops:list_assessment_documents:courseops_service.list_assessment_documents": "read",
    "courseops:delete_document:courseops_service.delete_course_document": "WRITE",
    "courseops:create_assessment:courseops_service.create_assessment": "WRITE",
    "courseops:list_assessments:courseops_service.list_assessments": "read",
    "courseops:create_deadline:courseops_service.create_deadline": "WRITE",
    "courseops:list_deadlines:courseops_service.list_deadlines": "read",
    "courseops:update_deadline:courseops_service.update_deadline": "WRITE",
    "courseops:delete_deadline:courseops_service.delete_deadline": "WRITE",
    "courseops:export_calendar:generate_ics": "read",
    "courseops:export_task_plan:generate_task_plan_md": "read",
}

ALLOWED = frozenset(GUARDED_ELSEWHERE) | frozenset(KNOWN_UNSCOPED_PENDING_FIX)


def _object_id_params(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> set[str]:
    """The endpoint's parameters that name a request-supplied object."""
    params = set()
    for arg in list(fn.args.args) + list(fn.args.kwonlyargs):
        if arg.arg in NON_OBJECT_PARAMS:
            continue
        if arg.arg.endswith(("_id", "_code", "_token")):
            params.add(arg.arg)
    return params


def _is_endpoint(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    """True if decorated with @router.<method>(...)."""
    for dec in fn.decorator_list:
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Attribute)
            and isinstance(dec.func.value, ast.Name)
            and dec.func.value.id == "router"
        ):
            return True
    return False


def _carries_user_identity(node: ast.expr) -> bool:
    """True for `user.id` or a bare `user_id` name."""
    if isinstance(node, ast.Attribute):
        return node.attr == "id" and isinstance(node.value, ast.Name) and node.value.id == "user"
    return isinstance(node, ast.Name) and node.id == "user_id"


def _find_unscoped_lookups() -> dict[str, str]:
    """Map "<module>:<endpoint>:<called>" -> "<file>:<line>" for violations."""
    import app.api

    api_dir = pathlib.Path(app.api.__file__).parent
    found: dict[str, str] = {}

    for path in sorted(api_dir.glob("*.py")):
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.AsyncFunctionDef | ast.FunctionDef):
                continue
            if not _is_endpoint(fn):
                continue
            id_params = _object_id_params(fn)
            if not id_params:
                continue

            for call in ast.walk(fn):
                if not isinstance(call, ast.Call) or not call.args:
                    continue
                first = call.args[0]
                if not (isinstance(first, ast.Name) and first.id in SESSION_ARG_NAMES):
                    continue

                takes_object_id = any(
                    isinstance(a, ast.Name) and a.id in id_params for a in call.args[1:]
                ) or any(
                    isinstance(k.value, ast.Name) and k.value.id in id_params for k in call.keywords
                )
                if not takes_object_id:
                    continue

                scoped = (
                    any(k.arg == "user_id" for k in call.keywords)
                    or any(_carries_user_identity(a) for a in call.args[1:])
                    or any(_carries_user_identity(k.value) for k in call.keywords)
                )
                if scoped:
                    continue

                key = f"{path.stem}:{fn.name}:{ast.unparse(call.func)}"
                found.setdefault(key, f"{path.name}:{call.lineno}")

    return found


def test_id_addressed_endpoints_scope_lookups_to_the_caller():
    """Every id-addressed service lookup in an endpoint must carry user_id."""
    found = _find_unscoped_lookups()

    unexpected = {k: v for k, v in found.items() if k not in ALLOWED}
    assert not unexpected, (
        "Endpoint(s) resolve a request-supplied id without scoping to the caller "
        "(the #47/#53 IDOR class):\n"
        + "\n".join(
            f"  {loc}  {key}" for key, loc in sorted(unexpected.items(), key=lambda x: x[1])
        )
        + "\n\nPass user_id=user.id into the lookup and return 404 (not 403) on a miss. "
        "If the call is genuinely safe, add it to GUARDED_ELSEWHERE in "
        "tests/unit/api/test_endpoint_scoping_guard.py with a reason."
    )


def test_scoping_allowlist_has_no_stale_entries():
    """A fixed endpoint must be removed from the allowlist.

    Without this the allowlist silently grows into a list of things nobody
    checks any more.
    """
    found = _find_unscoped_lookups()
    stale = sorted(ALLOWED - set(found))
    assert not stale, (
        "Allowlist entries no longer match any unscoped lookup -- the endpoint was "
        "fixed, renamed or removed. Delete them from "
        "tests/unit/api/test_endpoint_scoping_guard.py:\n" + "\n".join(f"  {k}" for k in stale)
    )


@pytest.mark.parametrize("key", sorted(KNOWN_UNSCOPED_PENDING_FIX))
def test_known_unscoped_endpoints_are_still_present(key):
    """Pin the known-vulnerable courseops calls so they cannot be quietly lost.

    These are live IDORs awaiting their own issue. If one stops being
    reported, it was either fixed (remove it from the dict) or the detection
    rule regressed (fix the rule) -- both need a human to look.
    """
    assert key in _find_unscoped_lookups(), (
        f"{key} is no longer detected as unscoped. If it was fixed, remove it from "
        "KNOWN_UNSCOPED_PENDING_FIX. If the detection rule changed, that is a "
        "regression in this guard."
    )

"""Structural guard: every AI call site decides about output language.

The rule is not "does this file import the helper" — a call site can fetch a
user's language and then build the agent without it, and every test of the
resulting summary still passes, in English, forever. It has to be the
`get_agent()` call that carries the language.

So each call site is listed here as one of two kinds, and the lists are
asserted exact in both directions:

* **content** — a human reads the output, so it must pass `output_language`.
* **parsed** — the app reads the output, so it must not. `classify` emits the
  course code and week the pipeline routes on; `extract_course_ops` emits
  dates and assessment records; `extract_concepts` emits a fixed category
  enum; `test-ai` is a connectivity probe whose reply is never shown.

A new call site fails this test until someone decides which it is. That is the
point: the default for a forgotten call site is English output, which looks
like working software rather than a missing feature.
"""

import ast
import pathlib

APP_ROOT = pathlib.Path(__file__).resolve().parents[3] / "app"

#: Call sites whose output a human reads. Each must pass `output_language`.
CONTENT_CALL_SITES = {
    ("pipeline/summarize.py", "_summarize"),
    ("pipeline/assets.py", "_generate_assets"),
    ("services/chat_service.py", "send_message"),
    ("services/chat_service.py", "stream_message"),
    ("api/qa.py", "ask_question"),
}

#: Call sites whose output the app parses, with the reason it stays English.
PARSED_CALL_SITES = {
    ("pipeline/classify.py", "_classify"): "emits the course code and week the pipeline routes on",
    ("pipeline/courseops_task.py", "_process_document"): "emits dates and assessment records",
    ("services/concept_service.py", "extract_and_save_concepts"): "emits a fixed category enum",
    ("api/settings.py", "test_ai_connection"): "a connectivity probe; the reply is never shown",
}


def _call_sites() -> dict[tuple[str, str], bool]:
    """Find every `get_agent(...)` call in the app, and whether it passes a language.

    Returns:
        {(relative path, enclosing function name): passes output_language}.
    """
    found: dict[tuple[str, str], bool] = {}

    for path in sorted(APP_ROOT.rglob("*.py")):
        if path.name == "factory.py":
            continue  # where get_agent is defined, not called
        tree = ast.parse(path.read_text())

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                func = inner.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                if name != "get_agent":
                    continue
                key = (str(path.relative_to(APP_ROOT)), node.name)
                passes = any(kw.arg == "output_language" for kw in inner.keywords)
                # A function with two call sites must be consistent; `or` would
                # let one of them silently drop the language.
                found[key] = passes if key not in found else (found[key] and passes)

    return found


class TestOutputLanguageWiring:
    def test_every_call_site_is_classified(self):
        """A new `get_agent()` call must be declared content or parsed."""
        sites = set(_call_sites())
        known = CONTENT_CALL_SITES | set(PARSED_CALL_SITES)

        assert sites - known == set(), (
            "undeclared get_agent() call site — add it to CONTENT_CALL_SITES "
            "(a human reads the output) or PARSED_CALL_SITES (the app does)"
        )
        assert known - sites == set(), "declared call site no longer exists — remove it"

    def test_content_call_sites_pass_the_language(self):
        sites = _call_sites()
        missing = sorted(site for site in CONTENT_CALL_SITES if not sites[site])

        assert missing == [], (
            f"these produce output a user reads but never pass output_language: {missing}"
        )

    def test_parsed_call_sites_do_not(self):
        sites = _call_sites()
        leaked = sorted(site for site in PARSED_CALL_SITES if sites[site])

        assert leaked == [], f"these emit records the app parses and must stay English: {leaked}"

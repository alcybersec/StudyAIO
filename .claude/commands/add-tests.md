# Add Tests

Add tests for the specified file or module. Follow these rules:

## Process

1. **Examine the target code** — understand all public functions, classes, and their edge cases.

2. **Check existing tests** — don't duplicate tests that already exist.

3. **Write tests following project conventions:**
   - Test file location mirrors source: `app/pipeline/classify.py` → `tests/unit/pipeline/test_classify.py`
   - Use descriptive test names: `test_classify_returns_review_item_when_course_unknown`
   - Use pytest fixtures for reusable setup
   - One assertion per test where practical
   - Group related tests in classes: `class TestClassifyArtifact:`

4. **Test categories to cover:**
   - **Happy path** — normal expected input produces expected output
   - **Edge cases** — empty input, None values, boundary conditions
   - **Error cases** — invalid input raises the right exception
   - **Idempotency** — calling twice produces the same result

5. **Mocking rules:**
   - Mock external dependencies (Claude Code CLI, filesystem for unit tests)
   - Mock at the boundary (mock the agent adapter, not internal functions)
   - Use `pytest-mock` / `unittest.mock`
   - Never mock the thing you're testing

6. **Run the new tests:** `pytest <test_file> -x -v`

7. **Run the full suite** to check for regressions: `pytest -x -v`

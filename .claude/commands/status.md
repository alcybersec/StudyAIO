# Project Status Check

Check the current state of the StudyAIO project and report.

## Steps

1. **Read `docs/PROGRESS.md`** — report current milestone and completed tasks.

2. **Check Docker** — run `docker compose ps` and report which services are up/down.

3. **Check Database** — if Postgres is running, check if migrations are up to date:
   ```
   alembic check
   ```

4. **Check Tests** — run the test suite and report pass/fail:
   ```
   pytest --tb=short -q
   ```

5. **Check for TODOs** — grep for TODO/FIXME/HACK in the codebase:
   ```
   grep -rn "TODO\|FIXME\|HACK" services/ --include="*.py" --include="*.tsx" --include="*.ts"
   ```

6. **Report** — summarize:
   - Current milestone and progress percentage
   - Services status (up/down)
   - Database migration status
   - Test results (X passed, Y failed)
   - Open TODOs count
   - Recommended next task

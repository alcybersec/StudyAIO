# Implement a Task

You are implementing a task for the StudyAIO project. Follow this workflow strictly:

## Workflow

### 1. Orient
- Read `docs/PROGRESS.md` to understand what's been built so far
- Read the relevant section of `docs/PRD.md` for the feature spec
- Identify which files need to be created or modified
- Check existing code for patterns to follow

### 2. Plan
- Before writing any code, explain your implementation plan
- List the files you'll create/modify
- List any new dependencies needed
- Identify edge cases and how you'll handle them
- State which tests you'll write

### 3. Implement
- Write code following the conventions in CLAUDE.md
- Create one file at a time, in dependency order (models → services → pipeline → api)
- Use type hints on everything
- Add docstrings to all public functions and classes
- Handle errors explicitly — no bare except clauses

### 4. Test
- Write tests for the new code
- Run the test suite: `pytest -x -v`
- Fix any failures before proceeding

### 5. Verify
- If Docker services are involved, verify they work: `docker compose up -d && docker compose ps`
- If database changes are involved, verify migrations: `alembic upgrade head`
- If API changes, verify endpoints respond correctly

### 6. Update Progress
- Update `docs/PROGRESS.md` with:
  - What was completed
  - Any decisions made
  - Any issues encountered
  - What should be done next

## Rules
- Do NOT skip tests to save time
- Do NOT leave TODO comments without explaining why the TODO exists
- Do NOT modify existing tests without explaining why
- Do NOT add dependencies without checking if an existing one covers the need
- If you encounter an ambiguity in the PRD, flag it — don't guess

# Debug an Issue

Investigate and fix a bug or unexpected behavior.

## Workflow

### 1. Reproduce
- Understand the expected vs actual behavior
- Find the minimum steps to reproduce
- Check logs: `docker compose logs -f api worker`

### 2. Locate
- Trace the request/data flow from entry point to failure
- For API issues: start at the route handler, follow through service → model
- For pipeline issues: check `pipeline_runs` table for the failed stage, read error_message
- For database issues: connect with `make db` and inspect relevant tables
- Check recent git changes: `git log --oneline -10` and `git diff`

### 3. Diagnose
- Identify the root cause (not just the symptom)
- Explain why the bug occurs
- Check if the same pattern exists elsewhere (similar bugs waiting to happen)

### 4. Fix
- Make the minimal change that fixes the root cause
- Do NOT add workarounds that mask the real problem
- If the fix requires a design change, explain the tradeoff

### 5. Test
- Write a test that reproduces the bug (fails before fix, passes after)
- Run the full test suite to check for regressions
- Verify the fix in the running application if applicable

### 6. Document
- If the bug revealed a gap in the PRD or CLAUDE.md, update the relevant doc
- If it's a gotcha others might hit, add a note to the Important Warnings section

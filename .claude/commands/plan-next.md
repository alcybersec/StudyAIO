# Plan Next Work

Analyze the current project state and plan the next chunk of work.

## Process

1. **Read `docs/PROGRESS.md`** to understand what's done.
2. **Read `docs/PRD.md` and `docs/PRD_v2.md`** milestones sections to understand what's next.
3. **Examine the codebase** — what exists, what's missing, what's incomplete.
4. **Identify the next 3-5 concrete tasks** in implementation order.

## Output Format

For each task, provide:

### Task N: <Title>
- **What:** One-sentence description
- **Why:** What it unblocks or enables
- **Files to create/modify:** List them
- **Dependencies:** What must exist first
- **Estimated complexity:** Small (< 1 hour) / Medium (1-3 hours) / Large (3+ hours)
- **Definition of Done:** How to verify it's complete

## Rules

- Tasks must be concrete and completable in a single session
- Tasks must be in dependency order (don't plan API routes before models exist)
- Each task should have a clear Definition of Done
- Flag any PRD ambiguities discovered during planning

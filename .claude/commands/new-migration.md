# Create a Database Migration

Create an Alembic migration for a schema change.

## Rules

1. **Always create a migration** — never modify the database schema manually.
2. **One migration per logical change** — don't combine unrelated schema changes.
3. **Write both upgrade and downgrade** — migrations must be reversible.
4. **Test the migration:**
   ```bash
   alembic upgrade head      # Apply
   alembic downgrade -1      # Rollback
   alembic upgrade head      # Re-apply (verify idempotent)
   ```

## Process

1. Modify the SQLAlchemy model in `app/models/`
2. Generate migration: `alembic revision --autogenerate -m "descriptive message"`
3. **Review the generated migration** — autogenerate often misses:
   - Index creation/deletion
   - Default values
   - Enum type changes
   - Data migrations
4. Edit the migration if needed
5. Test as described above
6. Verify with: `alembic check` (should report no pending changes)

## Naming Convention

Migration messages should be descriptive and lowercase:
- `add flashcards table`
- `add embedding column to chunks`
- `add unique constraint on course week summary`

NOT:
- `update` (too vague)
- `fix` (what fix?)
- `changes` (meaningless)

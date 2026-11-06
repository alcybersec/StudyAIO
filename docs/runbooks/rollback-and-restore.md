# Runbook: rollback and restore

Only section C is written so far. Sections A (roll back a release), B (break-glass)
and D (host lost) land with D30-10.

## C. Restore the database (and data/) from a backup

Backups are written by `scripts/backup.sh` as `backups/studyaio_<ts>_db.sql.gz`
(plus `studyaio_<ts>_data.tar.gz`), `<ts>` being `YYYYMMDD_HHMMSS`.

### Restore

```bash
bash scripts/restore.sh                    # lists timestamps, exits 1
bash scripts/restore.sh <timestamp>        # asks you to retype the timestamp
bash scripts/restore.sh <timestamp> --yes  # no prompt
```

Run it from the app directory with the stack up. It uses the compose files of the
running `api` container; if the stack is down, name them yourself:

```bash
STUDYAIO_COMPOSE_FILES="docker-compose.yml docker-compose.prod.yml" bash scripts/restore.sh <timestamp>
```

With neither a running stack nor `STUDYAIO_COMPOSE_FILES` it exits 1 and changes
nothing. To restore a copy that is not in `./backups` (for example one fetched
from the off-host repository) set `BACKUP_DIR` to its directory.

What it does, in order:

1. Validates the timestamp and checks both files with `gzip -t` / `tar t`.
2. Checks the paths (`DATA_DIR` must be an existing plain directory), refuses if a
   `prerestore_<now>.sql.gz` or `data.prerestore-<now>` from the same second already
   exists, and requires the `-- PostgreSQL database dump complete` trailer in the dump.
   Then writes a safety dump of the current database to `backups/prerestore_<now>.sql.gz`
   (always the stack's own `backups/`, even when `BACKUP_DIR` points elsewhere) and
   **aborts if that fails**; nothing has been changed at that point.
3. Extracts the data archive into a staging directory (numeric owners kept).
4. Stops every service except `db`, then loads the dump with `psql -v
   ON_ERROR_STOP=1 --single-transaction`. The old schema is dropped inside that
   same transaction, so a bad dump rolls back and the current database survives.
5. Renames the current `data/` to `data.prerestore-<now>` and puts the restored
   tree in its place. **It never deletes `data/`.** Remove the old tree by hand
   once you have checked the restore.
6. Runs `alembic upgrade head` in a one-off container, starts the stack and waits
   for `/health/ready`.

#### If the swap stops half-way

If the script dies between renaming `data/` aside and putting the restored tree in
place (for example the host lost power), `data/` may be missing while
`data.prerestore-<ts>` holds the previous tree and `data.restore-<ts>/data` the
restored one. Nothing is deleted, so recover by hand from the directory that holds
`data/`:

```bash
ls -d data data.prerestore-* data.restore-*     # see which exist
mv data.prerestore-<ts> data                    # only if data/ is missing; puts the old tree back
docker compose up -d --no-build                 # same -f files as the stack uses
```

To finish the restore instead, move `data.restore-<ts>/data` to `data` (when `data/`
is absent) and start the stack. The database is already restored at that point;
the safety dump of what it replaced is `backups/prerestore_<ts>.sql.gz`.

Pre-migration dumps (`backups/predeploy_<ts>_<sha7>.sql.gz`, database only) can be
restored by copying one to `studyaio_<ts>_db.sql.gz` first.

### Prove a backup restores (drill)

```bash
bash scripts/restore-drill.sh <backups-dir | studyaio_<ts>_db.sql.gz> [timestamp]
```

Loads the dump into a throwaway Postgres on an internal Docker network, runs
`alembic upgrade head` from the pinned api image, counts rows and lists the data
archive, then removes everything it created. It never touches the live database
or `data/`. The last line is the result:

```
restore_drill ok backup=<ts> users=<n> data_files=<n> load_s=<n> total_s=<n>
```

Pass a directory fetched from the off-host copy to prove that path. Set
`API_IMAGE` if no `api` container is running to read the pinned image from.
`total_s` excludes fetching the copy and extracting `data/`; add those to get the
restore time.

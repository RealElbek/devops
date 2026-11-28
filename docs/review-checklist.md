# Code review checklist

Use this for every PR. Leave at least **one concrete comment** (a question, a suggestion, or what
you checked and why it is fine).

## Correctness
- [ ] Does the change do what the issue asks?
- [ ] Are errors handled (wrong input → 400, missing → 404, conflict → 409)?
- [ ] Can it break double-booking protection (seat locks, unique ticket per seat)?

## Data safety
Why: in a previous project an unreviewed change deleted customer backups.
- [ ] Does the change delete or overwrite data (`DELETE`, `DROP`, `TRUNCATE`, `rm -rf`, `pg_restore --clean`, `docker volume rm`, `down -v`)? If yes:
  - [ ] it asks for confirmation (or is clearly a test-only path),
  - [ ] it takes a backup / safety copy first,
  - [ ] it was tested on a copy, and the PR says how.
- [ ] Nothing touches `backups/` or the `*-data` volumes except `scripts/backup.sh` / `scripts/restore.sh`.
- [ ] Schema changes keep existing rows working (no silent column drops).

## Tests
- [ ] New behaviour has a test in `services/<name>-service/tests/`
- [ ] CI is green (secret scan, lint, tests, smoke, resilience)

## DevOps
- [ ] `make up` still works from a fresh clone
- [ ] Healthchecks, restart policies and resource limits still in place
- [ ] Image versions pinned (no `:latest`)

## Security
- [ ] No passwords, tokens, keys or personal data (also in commit history)
- [ ] No new published ports unless needed
- [ ] Containers still run as non-root

## Docs
- [ ] README / docs updated if commands, config or API changed
- [ ] New architecture choice → new ADR in `docs/decisions.md`

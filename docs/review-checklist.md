# Code review checklist

Use this for every PR. Leave at least **one concrete comment** (a question, a suggestion, or what
you checked and why it is fine).

## Correctness
- [ ] Does the change do what the issue asks?
- [ ] Are errors handled (wrong input → 400, missing → 404, conflict → 409)?
- [ ] Can it break double-booking protection (seat locks, unique ticket per seat)?

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

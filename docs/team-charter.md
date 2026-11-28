# Team charter

**Project:** Ticket booking platform (PDP University · Unit 4 DevOps · PayFast)
**Team:** _<team name from the course sheet>_
**Repository:** https://github.com/RealElbek/devops

## Roles

| Role | Responsibility | Evidence in the repo | Member |
| ---- | -------------- | -------------------- | ------ |
| Tech Lead | Repo, collaborators, `main` protection, final merge, resolving conflicts | Branch protection, collaborators list, merged PRs | Elbek Azimjonov (@RealElbek) |
| Product Owner / Scrum Master | Issues, labels, project board, stand-ups | Issues, Project board, [meetings.md](meetings.md) | @fullcoder47 |
| QA & Code Review Lead | PR template, review checklist, tests | [.github/pull_request_template.md](../.github/pull_request_template.md), [review-checklist.md](review-checklist.md), `services/*/tests/` | Elbek Azimjonov (@RealElbek), together with Tech Lead |
| DevOps / Platform Engineer | Docker, Compose, CI/CD, "clone → one command → works" | `services/*/Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml` | Kamtarbek Shonazarov (@Kamtarbek) |
| Technical Writer & Security Champion | Docs, access list, decisions, secret checks | README, [access.md](access.md), [decisions.md](decisions.md), gitleaks job | @MahmudovMuhammadrizo24 |

> Roles assigned 2026-11-28. Nobody took QA, so the Tech Lead holds it. Reviews of the Tech
> Lead's own PRs are done by another member (a PR author never approves their own PR).
> Any change to this table is made in a PR.

## How we work

1. Every task is a GitHub **issue** on the project board (To do → In progress → Review → Done).
2. Work happens on a **branch** (`feat/...`, `fix/...`, `docs/...`), never directly on `main`.
3. Open a **pull request** using the template. CI must be green.
4. Someone **reviews** using [review-checklist.md](review-checklist.md) and leaves at least one concrete comment.
5. The Tech Lead **merges**. Branch is deleted after merge.
6. Short **stand-up** (10 min): done / next / blockers → [meetings.md](meetings.md).

## Definition of done

- Code + tests merged to `main`, CI green (secret scan, lint, tests, smoke, resilience).
- `make up` from a fresh clone works.
- Docs updated if commands or behaviour changed.

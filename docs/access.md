# Access control

Who can do what, and how changes are approved. Kept up to date by the Security Champion
(@MahmudovMuhammadrizo24) every time someone joins or leaves. Every change to this file is a PR.

## GitHub repository

Checked against **Settings → Collaborators** on 2026-11-28.

| Person | GitHub | Role in team | Repo permission | Status |
| ------ | ------ | ------------ | --------------- | ------ |
| Elbek Azimjonov | @RealElbek | Tech Lead, QA & Code Review | Admin (owner) | active |
| — | @fullcoder47 | Product Owner / Scrum Master | Write | active |
| — | @MahmudovMuhammadrizo24 | Technical Writer & Security Champion | Write | active |
| Kamtarbek Shonazarov | @Kamtarbek | DevOps / Platform Engineer | Write | active |
| Teacher | @MuhammadjonX | Reviewer / auditor | Write (see note) | **not added yet: Tech Lead to invite** |

- New team members get **Write**, never Admin. Only the Tech Lead is Admin.
- On a personal-account repository GitHub only offers one collaborator level (Write), so the auditor
  also gets Write. Branch protection still stops them, like everyone else, from changing `main`
  without a reviewed PR. A read-only auditor role needs the repo to move to a GitHub organization.
- When someone leaves: remove them in Settings → Collaborators the same day and update this table.

## How a change reaches `main` (audit question: "how are changes approved?")

1. Every change is a **pull request** from a branch. Nobody pushes to `main` directly.
2. **CI** runs on the PR: secret scan (gitleaks), image scan (Trivy, added in #15), lint + tests of all 4
   services, full-stack smoke + resilience test.
3. At least **1 approving review** from someone other than the author, using
   [review-checklist.md](review-checklist.md), with at least one concrete comment.
4. The **Tech Lead merges**. Every merge is visible in the PR list and the git history.

## `main` branch protection (Settings → Branches → rule for `main`)

| Setting | State | Evidence |
| ------- | ----- | -------- |
| Branch is protected | ✅ on | `GET /repos/RealElbek/devops/branches/main` → `protected: true` |
| Require a pull request + 1 approval | ✅ on | open PRs show "Review required" and merging is blocked until approved |
| Require review from Code Owners | to confirm (admin) | `.github/CODEOWNERS` assigns an owner to every path |
| Require status checks to pass | ❌ **none selected yet** | API shows an empty list. Tech Lead to add: `Secret scan (gitleaks)`, `Lint + tests (real Postgres)`, `Image scan (Trivy)`, `Full stack (smoke + resilience)` |
| Require conversation resolution | to confirm (admin) | |
| Do not allow bypassing / force pushes / deletion | to confirm (admin) | |

Only an admin can read the full rule, so the "to confirm" rows are checked by the Tech Lead.

## Secrets

- Real passwords live only in `.env`, which is in `.gitignore`. The repo has `.env.example` with
  local-only placeholder values (one password per database).
- CI runs **gitleaks** on the full git history for every push and PR.
- No personal data in the repo. Test data uses `@example.com` emails. Database backups
  (`backups/`) are git-ignored because they contain customer data.
- The payment API never accepts card numbers (ADR-004).
- If a secret is ever exposed (commit, issue, comment, chat): **revoke/rotate it first**, then remove
  it. Steps: [runbook.md §10](runbook.md#10-a-secret-was-leaked).

## Runtime access

| Component | Who can reach it |
| --------- | ---------------- |
| gateway (nginx) :80 | anyone who can reach the host; serves the dashboard, routes only `/api/v1/*` and `/health/*` |
| cAdvisor :8080 | anyone who can reach the host. On a real server bind to `127.0.0.1` or put behind auth. |
| the 4 services :5000 | only the gateway and each other (internal `backend` network); `/internal/*` only service-to-service |
| each Postgres :5432 | only its own service (its own internal `*-data` network), not published to the host |

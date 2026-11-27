# Access control

Who can do what, and how changes are approved. Reviewed by the Security Champion every time
someone joins or leaves.

## GitHub repository

| Person | GitHub | Role in team | Repo permission | Added |
| ------ | ------ | ------------ | --------------- | ----- |
| Elbek Azimjonov | @RealElbek | Tech Lead (all roles) | Admin (owner) | 2026-11-28 |
| Teacher | @MuhammadjonX | Reviewer / auditor | Read (or Write if required) | _to add_ |

New team members get **Write**, never Admin.

## `main` branch protection (Settings → Branches → Add rule `main`)

- [ ] Require a pull request before merging
- [ ] Require 1 approval (code owner review — see `.github/CODEOWNERS`)
- [ ] Require status checks to pass: `Secret scan (gitleaks)`, `Lint + tests (real Postgres)`, `Full stack (smoke + resilience)`
- [ ] Do not allow force pushes or deletion

## Secrets

- Real passwords live only in `.env`, which is in `.gitignore`. The repo has `.env.example` with
  local-only placeholder values.
- CI runs **gitleaks** on the full git history for every push and PR.
- No personal data in the repo. Test data uses `@example.com` emails.
- The payment API never accepts card numbers (ADR-004).
- If a secret is ever committed: rotate it immediately, then remove it from history.

## Runtime access

| Component | Who can reach it |
| --------- | ---------------- |
| nginx :80 | anyone who can reach the host |
| cAdvisor :8080 | anyone who can reach the host — on a real server bind to `127.0.0.1` or put behind auth |
| app :5000 | only nginx (internal `backend` network) |
| Postgres :5432 | only the app (internal `data` network), not published to the host |

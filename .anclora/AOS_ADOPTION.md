# AOS Adoption Declaration — Anclora CleanSheet

Repository: `anclora-clearsheet`
Status: Adopted for the governance bootstrap
Governance level: GL-1

## Local canonical sources

- Workspace policy: `../ANCLORA_WORKSPACE_AGENT_POLICY.md`
- Project routing: `.anclora/AGENT_PROJECT_CONTEXT.md`
- Runtime and environment: `.anclora/PRODUCTION_RUNTIME.md`
- Product behavior: `README.md`, `memory/PRD.md`, existing API/frontend tests
- CI delivery: `.github/workflows/`

## Decisions

1. The repository uses `development`, `staging`, `production`, and `main` as the
   promotion chain. Promotion is fast-forward-only and must never force-push.
2. CI runs the real frontend test/build commands and backend compile/test commands
   against the checked-in dependency manifests.
3. No production database, migration, seed data, or product feature is changed by
   this bootstrap.
4. Local secrets remain ignored and are never included in logs or commits.
5. A dedicated QA identity and browser QA runtime remain explicit follow-up gaps;
   they are not fabricated by this task.

## Review triggers

Review this declaration if the database provider, authentication model, branch
promotion model, QA model, or deployment platform changes.

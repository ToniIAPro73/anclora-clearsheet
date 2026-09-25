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


## Adopción de Gobernanza QA Proporcional y Economía Adaptativa

- PROPORTIONAL_QA_CONTRACT_ADOPTED=true
- BATCHED_VALIDATION_CONTRACT_ADOPTED=true
- QA_MODE_DEFAULT=AUTO
- QA_OVERRIDE_MODEL_ADOPTED=true
- FAST_MINIMUM_SUFFICIENT_TESTING_ADOPTED=true
- FAST_FULL_SUITE_PROHIBITION_ADOPTED=true
- STOP_WHEN_SUFFICIENT_EVIDENCE_ADOPTED=true

- ADAPTIVE_TOKEN_ECONOMY_CONTRACT_ADOPTED=true
- CAVEMAN_MODE_DEFAULT=AUTO
- CAVEMAN_TASK_LEVEL_REEVALUATION=true
- CAVEMAN_OVERRIDE_MODEL_ADOPTED=true

- WORKSPACE_POLICY_AUTHORITY=ANCLORA_WORKSPACE_AGENT_POLICY.md



## Historial de adopción

| Fecha | Versión | Cambio | Owner |
| --- | --- | --- | --- |
| 2026-09-16 | v0.2.0 | Declaración inicial de adopción AOS. | ToniIAPro73 |
| 2026-09-25 | v2.0 | Adopción de política canónica de QA proporcional, cadencia de puertas por lotes (BATCHED) y modelo de overrides explícitos. | ToniIAPro73 |
| 2026-09-25 | v2.1 | Adopción de economía adaptativa (CAVEMAN_MODE=AUTO) y endurecimiento FAST QA (sin suites completas por defecto, mínimo suficiente, detención ante evidencia suficiente). | ToniIAPro73 |


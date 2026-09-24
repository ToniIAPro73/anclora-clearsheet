# Anclora CleanSheet — Closed Access & Whitelist Architecture

## 1. Overview

Anclora CleanSheet implements a strictly closed access model. Public open registration is disabled, and anonymous usage of processing endpoints is prohibited. User onboarding is gated by an administrative whitelist invitation system with single-use cryptographically secure tokens.

## 2. Route Architecture

| Route | Visibility | Purpose |
|---|---|---|
| `/` | Public | Brand landing page highlighting deterministic tabular normalization, ERP/CRM/bank compatibility, and value proposition. |
| `/login` | Public | Dedicated email & password authentication surface with show/hide password toggle and link to activation. |
| `/activate` | Public (Token Required) | Account activation screen validating invitation token, showing read-only email, and accepting user display name and password (minimum 12 characters). |
| `/app` | Protected | Authenticated CleanSheet workspace. Unauthenticated visitors are routed to `/login`. |

## 3. Authentication & Security Specifications

- **Password Hashing**: Argon2id via `argon2-cffi` (`time_cost=2, memory_cost=19456, parallelism=1`).
- **Session Tokens**: JWT access tokens (1 hour TTL) and refresh tokens (7 days TTL) issued via HttpOnly cookies.
  - In production (`APP_ENV=production`): `Secure=True; SameSite=None` to support cross-subdomain API communication (`cleansheet.anclora.com` -> `api.cleansheet.anclora.com`).
  - In local development: `Secure=False; SameSite=Lax`.
- **Active State Validation**: Every authenticated request evaluates both `user.status == 'active'` and `whitelist.status == 'active'` against the database in real time. If an invitation is revoked, active sessions are immediately invalidated regardless of JWT expiration.
- **Audit Logging**: All security actions (`login_succeeded`, `login_failed`, `activation_succeeded`, `activation_rejected`, `whitelist_added`, `whitelist_revoked`, `whitelist_token_rotated`) are logged to `auth_audit_events`.
- **Zero Secret Leakage**: Raw tokens, passwords, and JWTs are never persisted in plain text or returned in listing endpoints. Tokens are stored strictly as SHA-256 hashes (`token_hash`).

## 4. Administrative Whitelist Management

### Environment Configuration
- `AUTH_ADMIN_EMAILS`: Comma-separated list of administrator emails authorized to invoke admin whitelist endpoints.
- `AUTH_WHITELIST_TOKEN_TTL_HOURS`: Invitation token time-to-live (default: 72 hours).
- `AUTH_PASSWORD_MIN_LENGTH`: Minimum password length enforced during activation (default: 12 characters).

### Admin Endpoints
- `POST /api/auth/whitelist`: Create an invitation for an email. Returns single-use raw activation token.
- `GET /api/auth/whitelist`: List whitelist entries. Never exposes token hashes or credentials.
- `POST /api/auth/whitelist/{id}/rotate-token`: Regenerate and re-issue a fresh activation token.
- `POST /api/auth/whitelist/{id}/revoke`: Immediately revoke an invitation and disable any linked user account.

### Operator CLI
An operational CLI is provided at `backend/scripts/manage_whitelist.py` that interfaces directly with backend models:
```bash
# Add new invitation
python backend/scripts/manage_whitelist.py add --email user@example.com

# List invitations
python backend/scripts/manage_whitelist.py list

# Rotate token
python backend/scripts/manage_whitelist.py rotate --target user@example.com

# Revoke access
python backend/scripts/manage_whitelist.py revoke --target user@example.com
```

## 5. Anonymous API Closure & IDOR Hardening

All product endpoints require authenticated user access (`get_current_user_required`):
- `/api/files/upload`, `/api/files/analyze`, `/api/files/preview`, `/api/files/export`, `/api/files/stream-process`, `/api/files/detect-dialect`
- `/api/batch/process`, `/api/batch/download/{storage_key}`
- `/api/samples/erp-finance`, `/api/samples/bank-extract`, `/api/samples/crm-leads`
- `/api/storage/direct-upload-url`
- `/api/connectors/test-unsaved`
- `/api/recipes/*`

### Object-Level Authorization (IDOR Mitigation)
- Files uploaded to CleanSheet are associated with the authenticated user ID (`source_files.user_id == current_user.id`).
- In-memory `FILE_CACHE` tracks user ownership alongside persisted database records.
- Batch processing and downloads verify execution ownership before granting access to generated ZIP archives.

# Antislop

An evidence-led code review marketplace: submit a repository and scope, independently verify coders, select a reviewer, and keep access handoffs and discussion together.

## Current implementation

The responsive web UI includes submitter, coder, and verification-team workspaces, email OTP/Google registration screens, a three-step review wizard, expert discovery, access checklists, and messages. Its default mode is an explicitly labeled local-data prototype, not a real authenticated service.

Tasks use one fixed primary category: Security, Frontend & UX, Backend & APIs, Performance, Testing & QA, DevOps & Cloud, Data & AI, Architecture & Refactoring, or General review. Category tags are separate from stack and workflow status; dashboard filters combine with search and status. Existing unclassified tasks remain General review. The FastAPI API validates category IDs and migrates existing SQLite reviews without discarding them.

The optional FastAPI backend implements real SMTP email OTP, Google OpenID Connect, persistent HttpOnly-cookie sessions, backend role checks, coder applications and staff decisions, private reviews, verified reviewer assignment, messages, and activity. It does not issue demo OTPs. Missing SMTP/OAuth configuration disables the corresponding sign-in option.

GitHub grants, repository scans, AI findings, file evidence uploads, payments, and coder proposals remain unconnected. Access requests record a handoff to `antislop@bee3.in` or the assigned coder; they do not send an invitation, grant permissions, or confirm access. No submitted code is cloned or executed.

## Run the UI

Requires Node.js. There is no dependency install or build step.

```sh
npm run dev
```

Open the printed URL, normally `http://127.0.0.1:4173`. Blank `apiBaseUrl` in `dist/config.js` keeps demo mode. Use sample details only; demo state is stored in browser localStorage.

Run `npm run check` for JavaScript syntax checks and `npm test` for the DOM-independent prototype workflow and mocked live-API role-control suites. Browser layout and real-provider authentication require separate end-to-end checks.

## Run FastAPI

Requires Python 3.12 or a compatible Python environment.

```sh
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` locally, generate a random `SECRET_KEY` of at least 32 characters, and configure the providers you intend to use. Never commit `.env`, tokens, or the runtime database.

```sh
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
python -m pytest backend/tests -q
```

To connect the UI locally, set `apiBaseUrl` in `dist/config.js` to `http://127.0.0.1:8000`. Use the same hostname in `FRONTEND_URL` and `CORS_ORIGINS` as the browser's UI URL (for example `http://127.0.0.1:4173`). The client sends credentials; mutations require the trusted Origin header. Do not combine localhost and 127.0.0.1 if cookies need to remain same-site.

Email sign-in requires a working SMTP account and authorized sender. Google sign-in requires an OAuth web client with the exact callback URI in `.env.example`. Configure `STAFF_EMAILS` with authorized staff addresses; users cannot choose a staff role in registration. Never use the public platform mailbox as a staff account merely because it is the access contact.

Use the same backend hostname in the public API address and Google callback URI; an OAuth state cookie issued for `127.0.0.1` cannot be returned to `localhost`. Disable URL access logging for OAuth callbacks so authorization codes are not written to logs. Provider responses are verified before account creation; third-party Google email accounts without authoritative Gmail/Workspace identity require email OTP instead.

When an API URL is configured, fixture data and role switching are removed. An invalid or unreachable API fails closed; it never silently enables demo authentication. Client configuration contains only a public API address, not credentials.

### Role-based access

FastAPI is the authorization authority; hidden buttons and route guards are additional UI controls, not security boundaries. Roles are saved on account creation and cannot be changed by choosing another role at login. Staff accounts are provisioned only through the server's `STAFF_EMAILS` allowlist.

| Role | Allowed access |
| --- | --- |
| Code submitter | Create and read their own reviews, assign approved coders, record repository handoffs, and exchange review messages. |
| Coder / doer | Submit their verification application. Only currently approved, assigned coders can read a private review and its messages. Available opportunities omit private repository links and briefs. |
| Verification staff | Review and decide coder applications. Staff access does not grant private repository or review access. |

Sessions contain no role or verification claims. The API checks current account and application state on each request, so revoked staff authorization or rejected/resubmitted coder verification removes access immediately. Unauthorized resource requests are denied without revealing private data. Auth responses include effective permissions; the live UI locks routes and mutations to these server-provided controls. The demo-only role selector never grants production access.

## Deployment and production readiness

`.openai/hosting.json` declares `dist/` as the static Sites artifact. The published Sites preview remains owner-private and uses demo mode until an externally hosted FastAPI API is configured. It does not replace the existing Hostinger site at `antislop.bee3.in`.

Host FastAPI on a Python-capable service or VPS with persistent storage. Prefer the frontend and API behind one HTTPS site to avoid cross-site cookie restrictions. Production requires HTTPS URLs, secure cookies, explicit trusted origins, encrypted SMTP, configured Google callback, backups, observability, and operational secret management. SQLite is appropriate for a local MVP only; migrate to the PostgreSQL schema and migrations described by the architecture before multi-instance scaling.

Next integrations are a scoped GitHub App with installation permission verification, an isolated code-review runner with budgets and evidence artifacts, and a payment provider. Never execute untrusted repositories inside the API process or treat email possession as a GitHub grant.

See `PLAN.md` and `ARCHITECTURE.md` for the original product plan. Authentication follows [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect); cross-origin configuration follows [FastAPI CORS guidance](https://fastapi.tiangolo.com/tutorial/cors/).

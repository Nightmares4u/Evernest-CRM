# AGENTS

## Project Purpose
- Internal Evernest CRM.
- WhatsApp-first operations workflow.
- CRM is the reporting, audit, and control layer.
- CRM is not a live chatbot or counseling bot.

## Architecture Rules
- Backend: FastAPI.
- Frontend: simple React/Next admin dashboard later.
- Database: PostgreSQL.
- WhatsApp remains the frontline channel.
- CRM is the internal control and reporting layer.
- Backend is the source of truth.

## Hard Constraints
- Do not add chatbot logic.
- Do not add auth yet.
- Do not add frontend pages unless explicitly requested.
- Do not redesign architecture.
- Do not add unnecessary abstractions.
- Keep changes minimal and stable.

## Branch Workflow
- `main` = stable.
- `dev` = integration.
- `feature/*` = active work.
- Never work directly on `main`.

## Implementation Style
- One small task at a time.
- Prefer explicit code over framework cleverness.
- Preserve append-only history where relevant.
- Backend is the source of truth.
- Favor simple, readable backend changes over new layers.

## Verification Expectations
- Run compile checks.
- Run migration checks when schema changes.
- Run a basic API smoke test when relevant.

## Review Expectations
- Identify critical issues.
- Identify medium issues.
- Identify low issues.
- Point to exact files.

## Coordination Files
- `CURRENT_STATE.md` is the live handoff file.
- `PLANS.md` is the roadmap.

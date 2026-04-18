# Evernest CRM Starter

Internal WhatsApp-first operations CRM for Evernest.

## Locked implementation plan

- **Frontend:** Next.js dashboard
- **Backend:** FastAPI
- **Database:** PostgreSQL
- **Lead channel:** WhatsApp-first
- **AI usage:** summaries, audit explanations, management debriefs only
- **Agent workflow:** stay on WhatsApp; update only a simple internal page
- **Website integration:** separate and future-safe via API/webhooks

## Core philosophy

WhatsApp is the front desk. CRM is the control tower.

## MVP modules

1. Auth (admin, manager, agent)
2. Offices
3. Agents
4. Leads
5. Agent updates
6. Audit flags
7. Reports

## Core tables

- offices
- agents
- whatsapp_numbers
- leads
- lead_events
- agent_updates
- appointments
- payments
- audit_flags
- daily_reports

## Recommended build order

1. Finalize statuses and KPI definitions
2. Set up backend + database + migrations
3. Add core models
4. Add CRUD routes for leads/offices/agents
5. Add activity logging
6. Add WhatsApp webhook raw ingest
7. Add dashboard and reports
8. Add nightly summary job

## Git workflow

- `main` = stable only
- `dev` = integration branch
- feature branches per module
- PRs into `dev`
- merge tested work from `dev` into `main`

## First feature branches

- `feat/backend-bootstrap`
- `feat/database-schema`
- `feat/leads-module`
- `feat/agents-module`
- `feat/whatsapp-webhook`
- `feat/dashboard-shell`
- `feat/reports-v1`

See `/docs` for the locked blueprint.

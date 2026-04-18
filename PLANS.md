# PLANS

## Project Goal
- Build an internal Evernest CRM that supports WhatsApp-first lead operations, internal control, auditability, and management reporting.

## Current Architecture Direction
- Backend-first implementation.
- FastAPI backend.
- PostgreSQL database.
- Simple internal admin dashboard later with React/Next.
- WhatsApp remains the frontline communication channel.
- CRM remains the internal control and reporting layer.

## Ordered Phases

### 1. Backend Core Models
- Status: Completed
- Scope: office, agent, lead core models, enums, relationships, and initial migrations.

### 2. Lead Lifecycle
- Status: Completed
- Scope: lead create/list/detail, assignment, status updates, append-only lead activity history, transition validation.

### 3. WhatsApp Raw Ingest
- Status: Completed
- Scope: raw webhook payload storage, webhook verification scaffolding, defensive inbound ingest, minimal lead creation or update from incoming message events.

### 4. Agent Update Surface
- Status: In Progress
- Scope: operational progress updates on leads, structured operational snapshot fields, append-only operational update history.

### 5. Audit Rules
- Status: Pending
- Scope: audit flags, discrepancy rules, reviewable operational exceptions, simple audit trail extensions.

### 6. Management Reporting
- Status: Pending
- Scope: management-facing reporting shell, office comparison inputs, basic KPI/reporting endpoints, internal reporting data layer.

### 7. AI Summaries
- Status: Pending
- Scope: internal summaries only, management debrief support, no live chatbot behavior, no autonomous counseling behavior.

## Do Not Build Yet
- No mobile app.
- No chatbot.
- No notifications.
- No advanced RBAC.
- No drag-and-drop CRM.
- No complex commission engine.
- No document system yet.

## Definition Of Done For A Phase
- Scope implemented only for the current phase.
- Migrations added when schema changes.
- Compile checks pass.
- Relevant migration checks pass.
- Relevant basic API smoke test passes.
- No architecture redesign introduced.

## Merge Policy
- Build on a `feature/*` branch.
- Keep changes narrowly scoped to the active phase.
- Re-review before merge.
- Merge into `dev` after verification.
- Move from `dev` to `main` only when stable and integrated.

# Locked CRM Plan

## Non-negotiables

- Keep WhatsApp as the live sales interface.
- CRM must not become a live AI counseling bot.
- CRM is an internal web app.
- Website and CRM stay separate but API-compatible.
- Backend is the source of truth.
- Raw WhatsApp webhook payloads must be stored.
- Statuses must be enums, not free text.
- Every important change must be logged.
- AI is used only for summaries and internal analysis.

## Surface implementation

### Management
- Full dashboard access
- Office comparison
- Agent performance
- Audit discrepancies
- Daily/weekly reports

### Agents
- No heavy CRM usage
- WhatsApp remains primary workspace
- Small update page only

## Deployment model

- Frontend: Vercel
- Backend: VPS / Render / Railway
- DB: PostgreSQL
- Optional worker/cron for daily summaries

## Future integration points

- WordPress forms -> API webhook -> CRM
- React/Next public site -> API -> CRM
- WhatsApp incoming events -> webhook -> CRM
- Google Sheets import -> script/API -> CRM

# CURRENT_STATE

## Branches
- Current branch: `feature/agent-update-surface`
- Stable branches:
  - `main` = stable
  - `dev` = integration

## Completed Phases
- Backend core models
- Lead lifecycle
- WhatsApp raw ingest

## Current Phase
- Agent update surface

## Current Branch Goal
- Operational progress updates on leads
- Structured snapshot fields on lead
- Append-only operational update log

## Latest Review Findings
- No critical issues
- Medium issue: operational fields can conflict with lead status semantics
- Data consistency issue: counter increments need atomic handling
- Append-only risk: milestone fields should not revert from true to false
- Low-priority cleanup: snapshot remarks overwrite behavior
- API auth/spoofing concern exists but can wait because auth is intentionally not built yet

## Exact Next Task
- Patch the agent update surface based on the latest review

## Next Prompt For Codex
- Patch the lead operations endpoint only: add simple semantic guards for status-sensitive operational fields, make counter increments atomic at the database level, prevent milestone snapshot fields from reverting from true to false, and preserve snapshot remarks when remarks is omitted.

## After Patch, Re-Review Before Merge
- Re-run review on the agent update surface after the patch lands.
- Check validation behavior, counter update safety, milestone forward-only behavior, and remarks snapshot behavior before merging.

## Next Branch After Merge
- `feature/audit-rules`

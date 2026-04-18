from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    AuditFlag,
    AuditFlagRule,
    AuditFlagSeverity,
    Lead,
    LeadStatus,
)
from app.schemas.audit import AuditFlagRead, AuditFlagRecomputeResponse

router = APIRouter(prefix="/audit-flags", tags=["audit"])
settings = get_settings()
BATCH_SIZE = 100


def _is_closed_status(status: LeadStatus) -> bool:
    return status in {LeadStatus.CLOSED_WON, LeadStatus.CLOSED_LOST}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _latest_activity_at(lead: Lead) -> datetime:
    timestamps = [_as_utc(activity.created_at) for activity in lead.activity_logs]
    timestamps.append(_as_utc(lead.created_at))
    return max(timestamps)


def _build_expected_flags_for_lead(lead: Lead, now: datetime) -> dict[AuditFlagRule, tuple[AuditFlagSeverity, str]]:
    expected_flags: dict[AuditFlagRule, tuple[AuditFlagSeverity, str]] = {}
    latest_activity_at = _latest_activity_at(lead)
    lead_age = now - _as_utc(lead.created_at)
    time_since_last_activity = now - latest_activity_at
    non_created_activity_exists = any(activity.event_type != "created" for activity in lead.activity_logs)

    if not _is_closed_status(lead.status):
        if time_since_last_activity >= timedelta(hours=settings.audit_stale_lead_hours):
            expected_flags[AuditFlagRule.STALE_LEAD] = (
                AuditFlagSeverity.WARNING,
                f"Lead has no activity for at least {settings.audit_stale_lead_hours} hours.",
            )

        if (
            lead_age >= timedelta(hours=settings.audit_no_follow_up_hours)
            and not non_created_activity_exists
        ):
            expected_flags[AuditFlagRule.NO_FOLLOW_UP] = (
                AuditFlagSeverity.WARNING,
                f"Lead has no follow-up activity after intake for at least {settings.audit_no_follow_up_hours} hours.",
            )

        if (
            lead.agent_id is None
            and lead_age >= timedelta(hours=settings.audit_unassigned_active_lead_hours)
        ):
            expected_flags[AuditFlagRule.UNASSIGNED_ACTIVE_LEAD] = (
                AuditFlagSeverity.WARNING,
                f"Lead has remained unassigned for at least {settings.audit_unassigned_active_lead_hours} hours.",
            )

    inconsistent_reasons: list[str] = []
    if getattr(lead, "payment_collected", None) is True and lead.status in {
        LeadStatus.NEW,
        LeadStatus.ASSIGNED,
    }:
        inconsistent_reasons.append("payment_collected is true while lead status is new or assigned")
    if getattr(lead, "walk_in_happened", None) is True and getattr(lead, "appointment_booked", None) is False:
        inconsistent_reasons.append("walk_in_happened is true while appointment_booked is false")
    if getattr(lead, "closed_by", None) is not None and lead.status != LeadStatus.CLOSED_WON:
        inconsistent_reasons.append("closed_by is set while lead status is not closed_won")

    if inconsistent_reasons:
        expected_flags[AuditFlagRule.INCONSISTENT_STATE] = (
            AuditFlagSeverity.ERROR,
            "; ".join(inconsistent_reasons),
        )

    return expected_flags


@router.get("", response_model=list[AuditFlagRead])
def list_audit_flags(
    lead_id: int | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[AuditFlag]:
    statement = select(AuditFlag).order_by(AuditFlag.detected_at.desc(), AuditFlag.id.desc())

    if lead_id is not None:
        statement = statement.where(AuditFlag.lead_id == lead_id)
    if active_only:
        statement = statement.where(AuditFlag.is_active.is_(True))

    return list(db.scalars(statement).all())


@router.post("/recompute", response_model=AuditFlagRecomputeResponse)
def recompute_audit_flags(
    lead_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AuditFlagRecomputeResponse:
    now = datetime.now(timezone.utc)
    created_flags = 0
    resolved_flags = 0
    total_leads_checked = 0

    def process_leads(leads: list[Lead]) -> None:
        nonlocal created_flags, resolved_flags, total_leads_checked
        total_leads_checked += len(leads)

        for lead in leads:
            expected_flags = _build_expected_flags_for_lead(lead, now)
            active_flags_by_rule = {
                flag.rule_name: flag
                for flag in lead.audit_flags
                if flag.is_active
            }

            for rule_name, (severity, detail) in expected_flags.items():
                existing_flag = active_flags_by_rule.get(rule_name)
                if existing_flag is None:
                    db.add(
                        AuditFlag(
                            lead_id=lead.id,
                            rule_name=rule_name,
                            severity=severity,
                            detail=detail,
                            is_active=True,
                        )
                    )
                    created_flags += 1
                    continue

                existing_flag.severity = severity
                existing_flag.detail = detail

            for rule_name, existing_flag in active_flags_by_rule.items():
                if rule_name not in expected_flags:
                    existing_flag.is_active = False
                    existing_flag.resolved_at = now
                    resolved_flags += 1

        db.flush()
        db.expunge_all()

    if lead_id is not None:
        process_leads(
            list(
                db.scalars(
                    select(Lead)
                    .where(Lead.id == lead_id)
                    .options(
                        selectinload(Lead.activity_logs),
                        selectinload(Lead.audit_flags),
                    )
                ).all()
            )
        )
    else:
        last_seen_id = 0

        while True:
            lead_ids = list(
                db.scalars(
                    select(Lead.id)
                    .where(Lead.id > last_seen_id)
                    .order_by(Lead.id)
                    .limit(BATCH_SIZE)
                ).all()
            )
            if not lead_ids:
                break

            process_leads(
                list(
                    db.scalars(
                        select(Lead)
                        .where(Lead.id.in_(lead_ids))
                        .order_by(Lead.id)
                        .options(
                            selectinload(Lead.activity_logs),
                            selectinload(Lead.audit_flags),
                        )
                    ).all()
                )
            )
            last_seen_id = lead_ids[-1]

    db.commit()

    active_count_statement = select(func.count(AuditFlag.id)).where(AuditFlag.is_active.is_(True))
    if lead_id is not None:
        active_count_statement = active_count_statement.where(AuditFlag.lead_id == lead_id)

    active_flags = db.scalar(active_count_statement) or 0
    return AuditFlagRecomputeResponse(
        total_leads_checked=total_leads_checked,
        active_flags=active_flags,
        created_flags=created_flags,
        resolved_flags=resolved_flags,
    )

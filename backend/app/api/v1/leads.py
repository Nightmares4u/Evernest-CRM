from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Agent, Lead, LeadActivityLog, LeadStatus, Office
from app.models.lead import can_transition_lead_status
from app.schemas.lead import (
    LeadAssign,
    LeadCreate,
    LeadDetailRead,
    LeadRead,
    LeadStatusUpdate,
)

router = APIRouter(prefix="/leads", tags=["leads"])


def _get_lead_or_404(
    db: Session,
    lead_id: int,
    *,
    include_activity_logs: bool = False,
) -> Lead:
    statement = select(Lead).where(Lead.id == lead_id)

    if include_activity_logs:
        statement = statement.options(selectinload(Lead.activity_logs))

    lead = db.scalar(statement)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    return lead


def _create_activity_log(
    db: Session,
    *,
    lead_id: int,
    event_type: str,
    agent_id: int | None = None,
    from_status: LeadStatus | None = None,
    to_status: LeadStatus | None = None,
) -> None:
    db.add(
        LeadActivityLog(
            lead_id=lead_id,
            event_type=event_type,
            agent_id=agent_id,
            from_status=from_status,
            to_status=to_status,
        )
    )


@router.post("", response_model=LeadDetailRead, status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)) -> Lead:
    office = db.get(Office, payload.office_id)
    if office is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Office not found")

    lead = Lead(
        office_id=payload.office_id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        notes=payload.notes,
        status=LeadStatus.NEW,
    )
    db.add(lead)
    db.flush()

    _create_activity_log(
        db,
        lead_id=lead.id,
        event_type="created",
        to_status=LeadStatus.NEW,
    )

    db.commit()
    return _get_lead_or_404(db, lead.id, include_activity_logs=True)


@router.get("", response_model=list[LeadRead])
def list_leads(
    office_id: int | None = Query(default=None),
    agent_id: int | None = Query(default=None),
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[Lead]:
    statement = select(Lead).order_by(Lead.created_at.desc(), Lead.id.desc())

    if office_id is not None:
        statement = statement.where(Lead.office_id == office_id)
    if agent_id is not None:
        statement = statement.where(Lead.agent_id == agent_id)
    if status_filter is not None:
        statement = statement.where(Lead.status == status_filter)

    return list(db.scalars(statement).all())


@router.get("/{lead_id}", response_model=LeadDetailRead)
def get_lead_detail(lead_id: int, db: Session = Depends(get_db)) -> Lead:
    return _get_lead_or_404(db, lead_id, include_activity_logs=True)


@router.post("/{lead_id}/assign", response_model=LeadDetailRead)
def assign_lead(
    lead_id: int,
    payload: LeadAssign,
    db: Session = Depends(get_db),
) -> Lead:
    lead = _get_lead_or_404(db, lead_id, include_activity_logs=True)
    agent = db.get(Agent, payload.agent_id)

    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if agent.office_id != lead.office_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent must belong to the same office as the lead",
        )
    if lead.status in {LeadStatus.CLOSED_WON, LeadStatus.CLOSED_LOST}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Closed leads cannot be reassigned",
        )
    if lead.agent_id == payload.agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead is already assigned to this agent",
        )

    previous_status = lead.status
    lead.agent_id = payload.agent_id

    next_status = previous_status
    if previous_status == LeadStatus.NEW:
        next_status = LeadStatus.ASSIGNED
        if not can_transition_lead_status(previous_status, next_status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lead cannot be moved to assigned from its current status",
            )
        lead.status = next_status

    _create_activity_log(
        db,
        lead_id=lead.id,
        event_type="assigned",
        agent_id=payload.agent_id,
        from_status=previous_status if previous_status != next_status else None,
        to_status=next_status if previous_status != next_status else None,
    )

    db.commit()
    return _get_lead_or_404(db, lead.id, include_activity_logs=True)


@router.patch("/{lead_id}/status", response_model=LeadDetailRead)
def update_lead_status(
    lead_id: int,
    payload: LeadStatusUpdate,
    db: Session = Depends(get_db),
) -> Lead:
    lead = _get_lead_or_404(db, lead_id, include_activity_logs=True)

    if lead.status == payload.status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead already has this status",
        )
    if not can_transition_lead_status(lead.status, payload.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from {lead.status.value} to {payload.status.value}",
        )

    previous_status = lead.status
    lead.status = payload.status

    _create_activity_log(
        db,
        lead_id=lead.id,
        event_type="status_updated",
        agent_id=lead.agent_id,
        from_status=previous_status,
        to_status=payload.status,
    )

    db.commit()
    return _get_lead_or_404(db, lead.id, include_activity_logs=True)

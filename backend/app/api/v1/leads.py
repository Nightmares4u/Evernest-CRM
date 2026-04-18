from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Agent, Lead, LeadActivityLog, LeadOperationalUpdate, LeadStatus, Office
from app.models.lead import can_transition_lead_status
from app.schemas.lead import (
    LeadAssign,
    LeadCreate,
    LeadDetailRead,
    LeadOperationsUpdate,
    LeadRead,
    LeadStatusUpdate,
)

router = APIRouter(prefix="/leads", tags=["leads"])


def _is_duplicate_phone_integrity_error(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return (
        ("unique" in message or "duplicate" in message)
        and ("leads.phone" in message or "ix_leads_phone" in message)
    )


def _get_lead_or_404(
    db: Session,
    lead_id: int,
    *,
    include_activity_logs: bool = False,
) -> Lead:
    statement = select(Lead).where(Lead.id == lead_id)

    if include_activity_logs:
        statement = statement.options(
            selectinload(Lead.activity_logs),
            selectinload(Lead.operational_updates),
        )

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
    if db.scalar(select(Lead).where(Lead.phone == payload.phone)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A lead with this phone number already exists",
        )

    lead = Lead(
        office_id=payload.office_id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        notes=payload.notes,
        status=LeadStatus.NEW,
    )
    db.add(lead)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        if _is_duplicate_phone_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A lead with this phone number already exists",
            ) from exc
        raise

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


@router.patch("/{lead_id}/operations", response_model=LeadDetailRead)
def update_lead_operations(
    lead_id: int,
    payload: LeadOperationsUpdate,
    db: Session = Depends(get_db),
) -> Lead:
    lead = _get_lead_or_404(db, lead_id, include_activity_logs=True)
    remarks_provided = "remarks" in payload.model_fields_set

    if (
        payload.calls_made_increment == 0
        and payload.follow_ups_made_increment == 0
        and payload.appointment_booked is None
        and payload.walk_in_happened is None
        and payload.closed_by is None
        and payload.payment_collected is None
        and not remarks_provided
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one operational field must be provided",
        )

    if payload.agent_id is not None:
        agent = db.get(Agent, payload.agent_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found",
            )
        if agent.office_id != lead.office_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent must belong to the same office as the lead",
            )

    if lead.status in {LeadStatus.NEW, LeadStatus.ASSIGNED} and (
        payload.closed_by is not None or payload.payment_collected is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Closed-by and payment-collected updates require a progressed lead status",
        )

    if lead.appointment_booked and payload.appointment_booked is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="appointment_booked cannot be changed from true to false",
        )
    if lead.walk_in_happened and payload.walk_in_happened is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="walk_in_happened cannot be changed from true to false",
        )
    if lead.payment_collected and payload.payment_collected is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payment_collected cannot be changed from true to false",
        )

    appointment_booked_after_update = lead.appointment_booked or payload.appointment_booked is True
    if payload.walk_in_happened is True and not appointment_booked_after_update:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="walk_in_happened requires appointment_booked first",
        )

    lead_update_values = {
        "calls_made": Lead.calls_made + payload.calls_made_increment,
        "follow_ups_made": Lead.follow_ups_made + payload.follow_ups_made_increment,
    }

    if payload.appointment_booked is not None:
        lead_update_values["appointment_booked"] = payload.appointment_booked
    if payload.walk_in_happened is not None:
        lead_update_values["walk_in_happened"] = payload.walk_in_happened
    if payload.closed_by is not None:
        lead_update_values["closed_by"] = payload.closed_by
    if payload.payment_collected is not None:
        lead_update_values["payment_collected"] = payload.payment_collected
    if remarks_provided:
        lead_update_values["remarks"] = payload.remarks

    db.execute(
        update(Lead)
        .where(Lead.id == lead.id)
        .values(**lead_update_values)
    )

    db.add(
        LeadOperationalUpdate(
            lead_id=lead.id,
            agent_id=payload.agent_id,
            calls_made_delta=payload.calls_made_increment,
            follow_ups_made_delta=payload.follow_ups_made_increment,
            appointment_booked=payload.appointment_booked,
            walk_in_happened=payload.walk_in_happened,
            closed_by=payload.closed_by,
            payment_collected=payload.payment_collected,
            remarks=payload.remarks,
        )
    )

    db.commit()
    db.expire_all()
    return _get_lead_or_404(db, lead.id, include_activity_logs=True)

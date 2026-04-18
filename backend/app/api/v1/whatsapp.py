import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.phone import normalize_phone_number, parse_phone_number
from app.db.session import get_db
from app.models import Lead, LeadActivityLog, LeadStatus, WhatsAppNumber, WhatsAppWebhookEvent

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])
settings = get_settings()


def _extract_message_text(message: dict[str, Any]) -> str | None:
    message_type = message.get("type")

    if message_type == "text":
        return message.get("text", {}).get("body")
    if message_type:
        return f"[{message_type}]"

    return None


def _extract_incoming_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    incoming_messages: list[dict[str, Any]] = []

    for entry in payload.get("entry", []):
        if not isinstance(entry, dict):
            continue

        for change in entry.get("changes", []):
            if not isinstance(change, dict) or change.get("field") != "messages":
                continue

            value = change.get("value", {})
            if not isinstance(value, dict):
                continue

            contacts_by_wa_id = {
                contact.get("wa_id"): contact
                for contact in value.get("contacts", [])
                if isinstance(contact, dict) and contact.get("wa_id")
            }
            metadata = value.get("metadata", {})

            for message in value.get("messages", []):
                if not isinstance(message, dict) or not message.get("from"):
                    continue

                incoming_messages.append(
                    {
                        "metadata": metadata if isinstance(metadata, dict) else {},
                        "contact": contacts_by_wa_id.get(message.get("from"), {}),
                        "message": message,
                    }
                )

    return incoming_messages


def _find_destination_whatsapp_number(
    db: Session,
    metadata: dict[str, Any],
) -> WhatsAppNumber | None:
    phone_number_id = metadata.get("phone_number_id")
    if phone_number_id:
        whatsapp_number = db.scalar(
            select(WhatsAppNumber).where(WhatsAppNumber.phone_number_id == phone_number_id)
        )
        if whatsapp_number is not None:
            return whatsapp_number

    display_phone_number = _normalize_phone_number(metadata.get("display_phone_number"))
    if display_phone_number is None:
        return None

    whatsapp_numbers = list(
        db.scalars(
            select(WhatsAppNumber).where(WhatsAppNumber.display_phone_number.is_not(None))
        ).all()
    )
    for whatsapp_number in whatsapp_numbers:
        if (
            _normalize_phone_number(whatsapp_number.display_phone_number)
            == display_phone_number
        ):
            return whatsapp_number

    return None


def _verify_whatsapp_signature(raw_body: bytes, signature_header: str | None) -> None:
    if not settings.whatsapp_app_secret:
        # MVP fallback: signature verification is skipped only when the app secret is not configured.
        return

    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid WhatsApp webhook signature",
        )

    expected_signature = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature_header, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid WhatsApp webhook signature",
        )


def _is_duplicate_phone_integrity_error(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return (
        ("unique" in message or "duplicate" in message)
        and ("leads.phone" in message or "ix_leads_phone" in message)
    )


def _create_activity_log(
    db: Session,
    *,
    lead_id: int,
    event_type: str,
    from_status: LeadStatus | None = None,
    to_status: LeadStatus | None = None,
) -> None:
    db.add(
        LeadActivityLog(
            lead_id=lead_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
        )
    )


@router.get("")
def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    if hub_mode != "subscribe":
        return PlainTextResponse("Unsupported verification mode", status_code=status.HTTP_400_BAD_REQUEST)

    if not settings.whatsapp_verify_token:
        return PlainTextResponse(
            "WhatsApp verification token is not configured",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if hub_verify_token != settings.whatsapp_verify_token:
        return PlainTextResponse("Verification failed", status_code=status.HTTP_403_FORBIDDEN)

    return PlainTextResponse(hub_challenge or "")


@router.post("")
async def ingest_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    raw_body_bytes = await request.body()
    _verify_whatsapp_signature(
        raw_body_bytes,
        request.headers.get("x-hub-signature-256"),
    )
    raw_body = raw_body_bytes.decode("utf-8", errors="replace")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        payload = None

    webhook_event = WhatsAppWebhookEvent(
        object_type=payload.get("object") if isinstance(payload, dict) else None,
        raw_body=raw_body,
        payload=payload,
        processing_status="received",
    )
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)

    if not isinstance(payload, dict):
        webhook_event.processing_status = "ignored"
        webhook_event.processing_error = "Invalid JSON payload"
        webhook_event.processed_at = datetime.now(timezone.utc)
        db.commit()
        return JSONResponse(
            {
                "status": "stored",
                "event_id": webhook_event.id,
                "processing_status": webhook_event.processing_status,
            }
        )

    incoming_messages = _extract_incoming_messages(payload)
    mapped_leads = 0

    failed_messages = 0

    for incoming_message in incoming_messages:
        try:
            message = incoming_message["message"]
            contact = incoming_message["contact"]
            metadata = incoming_message["metadata"]

            sender_phone = parse_phone_number(message.get("from"))
            if sender_phone is None:
                continue

            destination_whatsapp_number = _find_destination_whatsapp_number(db, metadata)
            lead = db.scalar(select(Lead).where(Lead.phone == sender_phone))

            if lead is None:
                if destination_whatsapp_number is None:
                    continue

                profile = contact.get("profile") if isinstance(contact, dict) else None
                contact_name = (
                    profile.get("name")
                    if isinstance(profile, dict)
                    else None
                )
                lead = Lead(
                    office_id=destination_whatsapp_number.office_id,
                    whatsapp_number_id=destination_whatsapp_number.id,
                    full_name=contact_name or sender_phone,
                    phone=sender_phone,
                    notes=_extract_message_text(message),
                    status=LeadStatus.NEW,
                )
                db.add(lead)
                try:
                    db.flush()
                except IntegrityError as exc:
                    db.rollback()
                    if not _is_duplicate_phone_integrity_error(exc):
                        raise

                    lead = db.scalar(select(Lead).where(Lead.phone == sender_phone))
                    if lead is None:
                        raise
                else:
                    _create_activity_log(
                        db,
                        lead_id=lead.id,
                        event_type="created",
                        to_status=LeadStatus.NEW,
                    )

            if (
                destination_whatsapp_number is not None
                and lead is not None
                and destination_whatsapp_number.office_id == lead.office_id
            ):
                lead.whatsapp_number_id = destination_whatsapp_number.id

            _create_activity_log(
                db,
                lead_id=lead.id,
                event_type="incoming_whatsapp_message",
            )
            db.commit()
            mapped_leads += 1
        except IntegrityError:
            db.rollback()
            failed_messages += 1
        except Exception:
            db.rollback()
            failed_messages += 1

    webhook_event = db.get(WhatsAppWebhookEvent, webhook_event.id)
    if webhook_event is not None:
        if failed_messages > 0 and mapped_leads == 0:
            webhook_event.processing_status = "failed"
            webhook_event.processing_error = f"{failed_messages} messages failed"
        elif failed_messages > 0:
            webhook_event.processing_status = "partial_success"
            webhook_event.processing_error = f"{failed_messages} messages failed"
        else:
            webhook_event.processing_status = "processed"
            webhook_event.processing_error = None
        webhook_event.processed_at = datetime.now(timezone.utc)
        db.commit()

    if webhook_event and webhook_event.processing_status == "failed":
        return JSONResponse(
            {
                "status": "stored",
                "event_id": webhook_event.id,
                "processing_status": "failed",
            }
        )

    return JSONResponse(
        {
            "status": "stored",
            "event_id": webhook_event.id,
            "processing_status": webhook_event.processing_status,
            "message_events": len(incoming_messages),
            "mapped_leads": mapped_leads,
        }
    )

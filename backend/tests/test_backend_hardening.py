import hashlib
import hmac
import json
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import whatsapp as whatsapp_module
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Lead, Office, WhatsAppNumber, WhatsAppWebhookEvent


class BackendHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_local = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        whatsapp_module.settings.whatsapp_app_secret = ""
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()
        whatsapp_module.settings.whatsapp_app_secret = ""

    def _seed_office(self) -> int:
        with Session(self.engine) as db:
            office = Office(name="Main Office")
            db.add(office)
            db.commit()
            return office.id

    def _seed_whatsapp_number(self, office_id: int) -> None:
        with Session(self.engine) as db:
            whatsapp_number = WhatsAppNumber(
                office_id=office_id,
                phone_number_id="1234567890",
                display_phone_number="+92 300 1111111",
            )
            db.add(whatsapp_number)
            db.commit()

    def test_duplicate_manual_lead_creation_returns_controlled_response(self) -> None:
        office_id = self._seed_office()

        first_response = self.client.post(
            "/api/v1/leads",
            json={
                "office_id": office_id,
                "full_name": "Lead One",
                "phone": "+92 300 1234567",
            },
        )
        self.assertEqual(first_response.status_code, 201)

        duplicate_response = self.client.post(
            "/api/v1/leads",
            json={
                "office_id": office_id,
                "full_name": "Lead Two",
                "phone": "923001234567",
            },
        )
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertEqual(
            duplicate_response.json()["detail"],
            "A lead with this phone number already exists",
        )

    def test_webhook_signature_verification_rejects_invalid_signature(self) -> None:
        office_id = self._seed_office()
        self._seed_whatsapp_number(office_id)
        whatsapp_module.settings.whatsapp_app_secret = "topsecret"

        payload = {
            "object": "whatsapp_business_account",
            "entry": [],
        }
        raw_body = json.dumps(payload).encode("utf-8")

        response = self.client.post(
            "/api/v1/webhooks/whatsapp",
            data=raw_body,
            headers={
                "content-type": "application/json",
                "x-hub-signature-256": "sha256=invalid",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"],
            "Invalid WhatsApp webhook signature",
        )

    def test_webhook_signature_verification_accepts_valid_signature_and_stores_payload(self) -> None:
        office_id = self._seed_office()
        self._seed_whatsapp_number(office_id)
        whatsapp_module.settings.whatsapp_app_secret = "topsecret"

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {
                                    "display_phone_number": "+92 300 1111111",
                                    "phone_number_id": "1234567890",
                                },
                                "contacts": [
                                    {
                                        "wa_id": "923001234567",
                                        "profile": {"name": "Sara Ahmed"},
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": "923001234567",
                                        "id": "wamid-1",
                                        "type": "text",
                                        "text": {"body": "Need details."},
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }
        raw_body = json.dumps(payload).encode("utf-8")
        signature = "sha256=" + hmac.new(
            b"topsecret",
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        response = self.client.post(
            "/api/v1/webhooks/whatsapp",
            data=raw_body,
            headers={
                "content-type": "application/json",
                "x-hub-signature-256": signature,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["processing_status"], "processed")

        with Session(self.engine) as db:
            lead = db.scalar(select(Lead).where(Lead.phone == "923001234567"))
            webhook_event = db.scalar(
                select(WhatsAppWebhookEvent).order_by(WhatsAppWebhookEvent.id.desc())
            )

            self.assertIsNotNone(lead)
            self.assertEqual(lead.full_name, "Sara Ahmed")
            self.assertIsNotNone(webhook_event)
            self.assertEqual(webhook_event.processing_status, "processed")


if __name__ == "__main__":
    unittest.main()

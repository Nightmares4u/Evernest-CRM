import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Agent, Lead, LeadStatus, Office


class LeadOperationsTests(unittest.TestCase):
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
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed_office_and_agent(self) -> tuple[int, int]:
        with Session(self.engine) as db:
            office = Office(name="Operations Office")
            db.add(office)
            db.flush()

            agent = Agent(
                office_id=office.id,
                full_name="Areeba Khan",
                email="areeba.khan@example.com",
            )
            db.add(agent)
            db.commit()
            return office.id, agent.id

    def _seed_lead(
        self,
        *,
        office_id: int,
        agent_id: int,
        phone: str,
        status: LeadStatus,
        appointment_booked: bool = False,
        walk_in_happened: bool = False,
        payment_collected: bool = False,
        calls_made: int = 0,
        follow_ups_made: int = 0,
        remarks: str | None = None,
    ) -> int:
        with Session(self.engine) as db:
            lead = Lead(
                office_id=office_id,
                agent_id=agent_id,
                full_name=f"Lead {phone}",
                phone=phone,
                status=status,
                appointment_booked=appointment_booked,
                walk_in_happened=walk_in_happened,
                payment_collected=payment_collected,
                calls_made=calls_made,
                follow_ups_made=follow_ups_made,
                remarks=remarks,
            )
            db.add(lead)
            db.commit()
            return lead.id

    def test_forward_only_milestones_reject_reverting_true_to_false(self) -> None:
        office_id, agent_id = self._seed_office_and_agent()

        test_cases = [
            ("appointment_booked", {"appointment_booked": False}, {"appointment_booked": True}),
            ("walk_in_happened", {"walk_in_happened": False}, {"walk_in_happened": True}),
            ("payment_collected", {"payment_collected": False}, {"payment_collected": True}),
        ]

        for index, (field_name, payload, lead_kwargs) in enumerate(test_cases, start=1):
            lead_id = self._seed_lead(
                office_id=office_id,
                agent_id=agent_id,
                phone=f"92300111000{index}",
                status=LeadStatus.CONTACTED,
                **lead_kwargs,
            )

            with self.subTest(field_name=field_name):
                response = self.client.patch(f"/api/v1/leads/{lead_id}/operations", json=payload)
                self.assertEqual(response.status_code, 400)

                with Session(self.engine) as db:
                    lead = db.get(Lead, lead_id)
                    self.assertTrue(getattr(lead, field_name))

    def test_semantic_guards_reject_closed_by_and_payment_for_new_or_assigned(self) -> None:
        office_id, agent_id = self._seed_office_and_agent()

        for status_value in (LeadStatus.NEW, LeadStatus.ASSIGNED):
            for index, (field_name, payload) in enumerate(
                (
                    ("closed_by", {"closed_by": "self_closed"}),
                    ("payment_collected", {"payment_collected": True}),
                ),
                start=1,
            ):
                lead_id = self._seed_lead(
                    office_id=office_id,
                    agent_id=agent_id,
                    phone=f"92300222{1 if status_value == LeadStatus.NEW else 2:01d}{index:02d}000",
                    status=status_value,
                )

                with self.subTest(status=status_value.value, field_name=field_name):
                    response = self.client.patch(f"/api/v1/leads/{lead_id}/operations", json=payload)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(
                        response.json()["detail"],
                        "Closed-by and payment-collected updates require a progressed lead status",
                    )

    def test_walk_in_requires_existing_or_same_payload_appointment(self) -> None:
        office_id, agent_id = self._seed_office_and_agent()

        lead_without_appointment = self._seed_lead(
            office_id=office_id,
            agent_id=agent_id,
            phone="923003330001",
            status=LeadStatus.CONTACTED,
        )
        reject_response = self.client.patch(
            f"/api/v1/leads/{lead_without_appointment}/operations",
            json={"walk_in_happened": True},
        )
        self.assertEqual(reject_response.status_code, 400)
        self.assertEqual(
            reject_response.json()["detail"],
            "walk_in_happened requires appointment_booked first",
        )

        lead_same_payload = self._seed_lead(
            office_id=office_id,
            agent_id=agent_id,
            phone="923003330002",
            status=LeadStatus.CONTACTED,
        )
        allow_response = self.client.patch(
            f"/api/v1/leads/{lead_same_payload}/operations",
            json={"appointment_booked": True, "walk_in_happened": True},
        )
        self.assertEqual(allow_response.status_code, 200)
        self.assertTrue(allow_response.json()["appointment_booked"])
        self.assertTrue(allow_response.json()["walk_in_happened"])

    def test_counter_increments_and_remarks_behavior(self) -> None:
        office_id, agent_id = self._seed_office_and_agent()
        lead_id = self._seed_lead(
            office_id=office_id,
            agent_id=agent_id,
            phone="923004440001",
            status=LeadStatus.CONTACTED,
            calls_made=2,
            follow_ups_made=1,
            remarks="existing snapshot",
        )

        first_response = self.client.patch(
            f"/api/v1/leads/{lead_id}/operations",
            json={
                "agent_id": agent_id,
                "calls_made_increment": 3,
                "follow_ups_made_increment": 2,
            },
        )
        self.assertEqual(first_response.status_code, 200)
        first_body = first_response.json()
        self.assertEqual(first_body["calls_made"], 5)
        self.assertEqual(first_body["follow_ups_made"], 3)
        self.assertEqual(first_body["remarks"], "existing snapshot")

        second_response = self.client.patch(
            f"/api/v1/leads/{lead_id}/operations",
            json={"remarks": "latest snapshot"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_body = second_response.json()
        self.assertEqual(second_body["remarks"], "latest snapshot")

        with Session(self.engine) as db:
            lead = db.scalar(select(Lead).where(Lead.id == lead_id))
            self.assertEqual(lead.calls_made, 5)
            self.assertEqual(lead.follow_ups_made, 3)
            self.assertEqual(lead.remarks, "latest snapshot")


if __name__ == "__main__":
    unittest.main()

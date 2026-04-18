import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import audit as audit_module
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import AuditFlag, AuditFlagRule, Lead, LeadActivityLog, LeadStatus, Office


class AuditFlagsTests(unittest.TestCase):
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
        audit_module.settings.audit_stale_lead_hours = 72
        audit_module.settings.audit_no_follow_up_hours = 24
        audit_module.settings.audit_unassigned_active_lead_hours = 24
        audit_module.BATCH_SIZE = 100
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed_office(self) -> int:
        with Session(self.engine) as db:
            office = Office(name="Audit Office")
            db.add(office)
            db.commit()
            return office.id

    def _seed_lead(
        self,
        *,
        office_id: int,
        phone: str,
        status: LeadStatus,
        created_at: datetime,
        agent_id: int | None = None,
    ) -> int:
        with Session(self.engine) as db:
            lead = Lead(
                office_id=office_id,
                agent_id=agent_id,
                full_name=f"Lead {phone}",
                phone=phone,
                status=status,
                created_at=created_at,
                updated_at=created_at,
            )
            db.add(lead)
            db.commit()
            return lead.id

    def _add_activity(self, *, lead_id: int, event_type: str, created_at: datetime) -> None:
        with Session(self.engine) as db:
            db.add(
                LeadActivityLog(
                    lead_id=lead_id,
                    event_type=event_type,
                    created_at=created_at,
                )
            )
            db.commit()

    def test_recompute_creates_expected_flags(self) -> None:
        office_id = self._seed_office()
        now = datetime.now(timezone.utc)

        stale_lead_id = self._seed_lead(
            office_id=office_id,
            phone="923100000001",
            status=LeadStatus.CONTACTED,
            created_at=now - timedelta(hours=100),
            agent_id=1,
        )
        self._add_activity(
            lead_id=stale_lead_id,
            event_type="created",
            created_at=now - timedelta(hours=100),
        )

        no_follow_up_id = self._seed_lead(
            office_id=office_id,
            phone="923100000002",
            status=LeadStatus.NEW,
            created_at=now - timedelta(hours=30),
            agent_id=1,
        )
        self._add_activity(
            lead_id=no_follow_up_id,
            event_type="created",
            created_at=now - timedelta(hours=30),
        )

        unassigned_lead_id = self._seed_lead(
            office_id=office_id,
            phone="923100000003",
            status=LeadStatus.CONTACTED,
            created_at=now - timedelta(hours=30),
            agent_id=None,
        )
        self._add_activity(
            lead_id=unassigned_lead_id,
            event_type="created",
            created_at=now - timedelta(hours=10),
        )

        response = self.client.post("/api/v1/audit-flags/recompute")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_leads_checked"], 3)
        self.assertEqual(body["created_flags"], 5)
        self.assertEqual(body["active_flags"], 5)

        with Session(self.engine) as db:
            active_flags = list(db.scalars(select(AuditFlag).where(AuditFlag.is_active.is_(True))).all())
            by_lead_rule = {(flag.lead_id, flag.rule_name.value) for flag in active_flags}
            self.assertIn((stale_lead_id, AuditFlagRule.STALE_LEAD.value), by_lead_rule)
            self.assertIn((stale_lead_id, AuditFlagRule.NO_FOLLOW_UP.value), by_lead_rule)
            self.assertIn((no_follow_up_id, AuditFlagRule.NO_FOLLOW_UP.value), by_lead_rule)
            self.assertIn((unassigned_lead_id, AuditFlagRule.UNASSIGNED_ACTIVE_LEAD.value), by_lead_rule)
            self.assertIn((unassigned_lead_id, AuditFlagRule.NO_FOLLOW_UP.value), by_lead_rule)

    def test_recompute_resolves_flags_when_issue_is_fixed(self) -> None:
        office_id = self._seed_office()
        now = datetime.now(timezone.utc)
        lead_id = self._seed_lead(
            office_id=office_id,
            phone="923100000010",
            status=LeadStatus.NEW,
            created_at=now - timedelta(hours=30),
            agent_id=1,
        )
        self._add_activity(
            lead_id=lead_id,
            event_type="created",
            created_at=now - timedelta(hours=30),
        )

        first_response = self.client.post("/api/v1/audit-flags/recompute")
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json()["active_flags"], 1)

        self._add_activity(
            lead_id=lead_id,
            event_type="status_updated",
            created_at=now,
        )

        second_response = self.client.post("/api/v1/audit-flags/recompute", params={"lead_id": lead_id})
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["resolved_flags"], 1)

        with Session(self.engine) as db:
            active_flags = list(
                db.scalars(
                    select(AuditFlag).where(
                        AuditFlag.lead_id == lead_id,
                        AuditFlag.is_active.is_(True),
                    )
                ).all()
            )
            resolved_flags = list(
                db.scalars(
                    select(AuditFlag).where(
                        AuditFlag.lead_id == lead_id,
                        AuditFlag.is_active.is_(False),
                    )
                ).all()
            )
            self.assertEqual(len(active_flags), 0)
            self.assertEqual(len(resolved_flags), 1)

    def test_list_audit_flags_filters_active_and_by_lead(self) -> None:
        office_id = self._seed_office()
        now = datetime.now(timezone.utc)
        lead_one = self._seed_lead(
            office_id=office_id,
            phone="923100000020",
            status=LeadStatus.NEW,
            created_at=now - timedelta(hours=30),
            agent_id=1,
        )
        lead_two = self._seed_lead(
            office_id=office_id,
            phone="923100000021",
            status=LeadStatus.CONTACTED,
            created_at=now - timedelta(hours=30),
            agent_id=None,
        )
        self._add_activity(lead_id=lead_one, event_type="created", created_at=now - timedelta(hours=30))
        self._add_activity(lead_id=lead_two, event_type="created", created_at=now - timedelta(hours=30))

        recompute_response = self.client.post("/api/v1/audit-flags/recompute")
        self.assertEqual(recompute_response.status_code, 200)

        filtered_response = self.client.get("/api/v1/audit-flags", params={"lead_id": lead_two})
        self.assertEqual(filtered_response.status_code, 200)
        flags = filtered_response.json()
        self.assertTrue(flags)
        self.assertTrue(all(flag["lead_id"] == lead_two for flag in flags))

    def test_recompute_processes_leads_in_batches(self) -> None:
        office_id = self._seed_office()
        now = datetime.now(timezone.utc)
        audit_module.BATCH_SIZE = 2

        for index in range(5):
            lead_id = self._seed_lead(
                office_id=office_id,
                phone=f"92310000010{index}",
                status=LeadStatus.CONTACTED,
                created_at=now - timedelta(hours=30),
                agent_id=1,
            )
            self._add_activity(
                lead_id=lead_id,
                event_type="created",
                created_at=now - timedelta(hours=30),
            )

        response = self.client.post("/api/v1/audit-flags/recompute")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_leads_checked"], 5)
        self.assertEqual(body["created_flags"], 5)
        self.assertEqual(body["active_flags"], 5)

    def test_inconsistent_state_rule_flags_relevant_conflicts(self) -> None:
        now = datetime.now(timezone.utc)
        lead = Lead(
            office_id=1,
            full_name="Inconsistent Lead",
            phone="923100009999",
            status=LeadStatus.NEW,
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
        )
        lead.activity_logs = []
        lead.payment_collected = True
        lead.walk_in_happened = True
        lead.appointment_booked = False
        lead.closed_by = "self_closed"

        expected_flags = audit_module._build_expected_flags_for_lead(lead, now)

        self.assertIn(AuditFlagRule.INCONSISTENT_STATE, expected_flags)
        severity, detail = expected_flags[AuditFlagRule.INCONSISTENT_STATE]
        self.assertEqual(severity.value, "error")
        self.assertIn("payment_collected is true while lead status is new or assigned", detail)
        self.assertIn("walk_in_happened is true while appointment_booked is false", detail)
        self.assertIn("closed_by is set while lead status is not closed_won", detail)


if __name__ == "__main__":
    unittest.main()

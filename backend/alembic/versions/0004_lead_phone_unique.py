"""lead phone unique

Revision ID: 0004_lead_phone_unique
Revises: 0003_whatsapp_raw_ingest
Create Date: 2026-04-18 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_lead_phone_unique"
down_revision = "0003_whatsapp_raw_ingest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_index("ix_leads_phone")
        batch_op.create_index("ix_leads_phone", ["phone"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_index("ix_leads_phone")
        batch_op.create_index("ix_leads_phone", ["phone"], unique=False)

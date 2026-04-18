"""whatsapp raw ingest

Revision ID: 0003_whatsapp_raw_ingest
Revises: 0002_lead_lifecycle
Create Date: 2026-04-18 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_whatsapp_raw_ingest"
down_revision = "0002_lead_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_numbers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("office_id", sa.Integer(), nullable=False),
        sa.Column("phone_number_id", sa.String(length=100), nullable=True),
        sa.Column("display_phone_number", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["office_id"], ["offices.id"]),
        sa.UniqueConstraint("phone_number_id"),
        sa.UniqueConstraint("display_phone_number"),
    )

    op.create_table(
        "whatsapp_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("object_type", sa.String(length=100), nullable=True),
        sa.Column("raw_body", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "processing_status",
            sa.String(length=30),
            server_default="received",
            nullable=False,
        ),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(sa.Column("whatsapp_number_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_leads_whatsapp_number_id_whatsapp_numbers",
            "whatsapp_numbers",
            ["whatsapp_number_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_leads_whatsapp_number_id",
            ["whatsapp_number_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_index("ix_leads_whatsapp_number_id")
        batch_op.drop_constraint(
            "fk_leads_whatsapp_number_id_whatsapp_numbers",
            type_="foreignkey",
        )
        batch_op.drop_column("whatsapp_number_id")

    op.drop_table("whatsapp_webhook_events")
    op.drop_table("whatsapp_numbers")

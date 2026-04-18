"""lead lifecycle

Revision ID: 0002_lead_lifecycle
Revises: 0001_initial_core_tables
Create Date: 2026-04-18 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_lead_lifecycle"
down_revision = "0001_initial_core_tables"
branch_labels = None
depends_on = None


old_lead_status = sa.Enum(
    "new",
    "assigned",
    "contacted",
    "qualified",
    "closed_won",
    "closed_lost",
    name="lead_status",
    native_enum=False,
)

new_lead_status = sa.Enum(
    "new",
    "assigned",
    "contacted",
    "follow_up",
    "appointment_booked",
    "walk_in_done",
    "qualified",
    "closed_won",
    "closed_lost",
    "no_response",
    name="lead_status",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=old_lead_status,
            type_=new_lead_status,
            existing_nullable=False,
            existing_server_default=sa.text("'new'"),
            server_default="new",
        )

    op.create_table(
        "lead_activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("from_status", new_lead_status, nullable=True),
        sa.Column("to_status", new_lead_status, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
    )
    op.create_index(
        op.f("ix_lead_activity_logs_lead_id"),
        "lead_activity_logs",
        ["lead_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_lead_activity_logs_lead_id"), table_name="lead_activity_logs")
    op.drop_table("lead_activity_logs")

    with op.batch_alter_table("leads") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=new_lead_status,
            type_=old_lead_status,
            existing_nullable=False,
            existing_server_default=sa.text("'new'"),
            server_default="new",
        )

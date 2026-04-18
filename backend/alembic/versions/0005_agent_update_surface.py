"""agent update surface

Revision ID: 0005_agent_update_surface
Revises: 0004_lead_phone_unique
Create Date: 2026-04-18 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_agent_update_surface"
down_revision = "0004_lead_phone_unique"
branch_labels = None
depends_on = None


lead_closure_source = sa.Enum(
    "self_closed",
    "senior_closed",
    name="lead_closure_source",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(
            sa.Column("calls_made", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("follow_ups_made", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "appointment_booked",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "walk_in_happened",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("closed_by", lead_closure_source, nullable=True))
        batch_op.add_column(
            sa.Column(
                "payment_collected",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("remarks", sa.Text(), nullable=True))

    op.create_table(
        "lead_operational_updates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column(
            "calls_made_delta",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "follow_ups_made_delta",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("appointment_booked", sa.Boolean(), nullable=True),
        sa.Column("walk_in_happened", sa.Boolean(), nullable=True),
        sa.Column("closed_by", lead_closure_source, nullable=True),
        sa.Column("payment_collected", sa.Boolean(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
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
        op.f("ix_lead_operational_updates_lead_id"),
        "lead_operational_updates",
        ["lead_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_lead_operational_updates_lead_id"),
        table_name="lead_operational_updates",
    )
    op.drop_table("lead_operational_updates")

    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_column("remarks")
        batch_op.drop_column("payment_collected")
        batch_op.drop_column("closed_by")
        batch_op.drop_column("walk_in_happened")
        batch_op.drop_column("appointment_booked")
        batch_op.drop_column("follow_ups_made")
        batch_op.drop_column("calls_made")

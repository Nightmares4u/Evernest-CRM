"""audit rules

Revision ID: 0005_audit_rules
Revises: 0004_lead_phone_unique
Create Date: 2026-04-18 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_audit_rules"
down_revision = "0004_lead_phone_unique"
branch_labels = None
depends_on = None


audit_flag_rule = sa.Enum(
    "stale_lead",
    "no_follow_up",
    "inconsistent_state",
    "unassigned_active_lead",
    name="audit_flag_rule",
    native_enum=False,
)

audit_flag_severity = sa.Enum(
    "warning",
    "error",
    name="audit_flag_severity",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "audit_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("rule_name", audit_flag_rule, nullable=False),
        sa.Column("severity", audit_flag_severity, nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
    )
    op.create_index(op.f("ix_audit_flags_lead_id"), "audit_flags", ["lead_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_flags_lead_id"), table_name="audit_flags")
    op.drop_table("audit_flags")

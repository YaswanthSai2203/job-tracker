"""add user email_verified

Revision ID: b2c8e1a4f9d0
Revises: 422e3c47bfe0
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

revision = "b2c8e1a4f9d0"
down_revision = "422e3c47bfe0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("email_verified")

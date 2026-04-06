"""add history_id to integrations

Revision ID: d4f501c82e91
Revises: c2e038558140
Create Date: 2026-04-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4f501c82e91"
down_revision: Union[str, None] = "c2e038558140"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "integrations",
        sa.Column("history_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("integrations", "history_id")

"""add archived_at to exams

Revision ID: a9d2c4e6b1f3
Revises: f2a6d8b3c1e9
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9d2c4e6b1f3'
down_revision: Union[str, None] = 'f2a6d8b3c1e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('exams', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('exams', 'archived_at')

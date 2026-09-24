"""add parse_confidence to questions

Revision ID: c7e4a2f91b3d
Revises: a1c9f3e7b2d4
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e4a2f91b3d'
down_revision: Union[str, None] = 'a1c9f3e7b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('questions', sa.Column('parse_confidence', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('questions', 'parse_confidence')

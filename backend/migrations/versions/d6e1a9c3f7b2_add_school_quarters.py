"""add school_quarters (the four chorak date ranges, editable by the admin)

Revision ID: d6e1a9c3f7b2
Revises: b4c8e1f7a3d5
Create Date: 2026-11-17 00:00:00.000000

No rows are inserted: an empty table means "use the defaults in code"
(quarter_service.DEFAULTS), so the app works the moment this is applied and
the admin only saves a row set if the calendar ever changes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6e1a9c3f7b2'
down_revision: Union[str, None] = 'b4c8e1f7a3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'school_quarters',
        sa.Column('number', sa.Integer(), primary_key=True),
        sa.Column('start_month', sa.Integer(), nullable=False),
        sa.Column('start_day', sa.Integer(), nullable=False),
        sa.Column('end_month', sa.Integer(), nullable=False),
        sa.Column('end_day', sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('school_quarters')

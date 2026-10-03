"""add expected_question_count to exams

Revision ID: f2a6d8b3c1e9
Revises: e4b7c9a2f1d6
Create Date: 2026-10-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a6d8b3c1e9'
down_revision: Union[str, None] = 'e4b7c9a2f1d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('exams', sa.Column('expected_question_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('exams', 'expected_question_count')

"""add ai grading columns for short-answer questions

Revision ID: e4b7c9a2f1d6
Revises: d8f3a1c5e9b2
Create Date: 2026-09-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b7c9a2f1d6'
down_revision: Union[str, None] = 'd8f3a1c5e9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('questions', sa.Column('reference_answer', sa.Text(), nullable=True))
    op.add_column('student_answers', sa.Column('ai_feedback', sa.Text(), nullable=True))
    op.add_column('student_answers', sa.Column('graded_by', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('student_answers', 'graded_by')
    op.drop_column('student_answers', 'ai_feedback')
    op.drop_column('questions', 'reference_answer')

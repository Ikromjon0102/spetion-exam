"""add option_image_key to question_options

Revision ID: d8f3a1c5e9b2
Revises: c7e4a2f91b3d
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f3a1c5e9b2'
down_revision: Union[str, None] = 'c7e4a2f91b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('question_options', sa.Column('option_image_key', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('question_options', 'option_image_key')

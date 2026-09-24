"""add homeroom_teacher_id to classes

Revision ID: a1c9f3e7b2d4
Revises: bd3dd8992686
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c9f3e7b2d4'
down_revision: Union[str, None] = 'bd3dd8992686'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('classes', sa.Column('homeroom_teacher_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_classes_homeroom_teacher_id_teachers', 'classes', 'teachers', ['homeroom_teacher_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_classes_homeroom_teacher_id_teachers', 'classes', type_='foreignkey')
    op.drop_column('classes', 'homeroom_teacher_id')

"""add chorak exams: sections, templates, per-section scores

Revision ID: b4c8e1f7a3d5
Revises: a9d2c4e6b1f3
Create Date: 2026-11-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4c8e1f7a3d5'
down_revision: Union[str, None] = 'a9d2c4e6b1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('exams', sa.Column('exam_type', sa.String(length=20), nullable=False, server_default='nazorat'))
    op.add_column('exams', sa.Column('quarter', sa.Integer(), nullable=True))
    op.add_column('exam_uploads', sa.Column('target_exam_id', sa.Integer(), nullable=True))
    op.add_column('exam_uploads', sa.Column('target_section_id', sa.Integer(), nullable=True))

    op.create_table(
        'exam_sections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('exam_id', sa.Integer(), sa.ForeignKey('exams.id'), nullable=False),
        sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('kind', sa.String(length=20), nullable=False, server_default='asosiy'),
        sa.Column('question_count', sa.Integer(), nullable=False),
        sa.Column('points_per_question', sa.Numeric(), nullable=False),
        sa.Column('ready_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_exam_sections_exam_id', 'exam_sections', ['exam_id'])

    with op.batch_alter_table('questions') as batch:
        batch.add_column(sa.Column('section_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_questions_section_id', 'exam_sections', ['section_id'], ['id'])

    op.create_table(
        'exam_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False, unique=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='180'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'exam_template_sections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('exam_templates.id'), nullable=False),
        sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('kind', sa.String(length=20), nullable=False, server_default='asosiy'),
        sa.Column('question_count', sa.Integer(), nullable=False),
        sa.Column('points_per_question', sa.Numeric(), nullable=False),
    )
    op.create_table(
        'attempt_section_scores',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('attempt_id', sa.Integer(), sa.ForeignKey('exam_attempts.id'), nullable=False),
        sa.Column('section_id', sa.Integer(), sa.ForeignKey('exam_sections.id'), nullable=False),
        sa.Column('exam_id', sa.Integer(), sa.ForeignKey('exams.id'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('score', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('max_score', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('correct_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('question_count', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('attempt_id', 'section_id', name='uq_section_score_attempt_section'),
    )
    op.create_index('ix_attempt_section_scores_student_subject', 'attempt_section_scores', ['student_id', 'subject_id'])


def downgrade() -> None:
    op.drop_index('ix_attempt_section_scores_student_subject', table_name='attempt_section_scores')
    op.drop_table('attempt_section_scores')
    op.drop_table('exam_template_sections')
    op.drop_table('exam_templates')
    with op.batch_alter_table('questions') as batch:
        batch.drop_constraint('fk_questions_section_id', type_='foreignkey')
        batch.drop_column('section_id')
    op.drop_index('ix_exam_sections_exam_id', table_name='exam_sections')
    op.drop_table('exam_sections')
    op.drop_column('exam_uploads', 'target_section_id')
    op.drop_column('exam_uploads', 'target_exam_id')
    op.drop_column('exams', 'quarter')
    op.drop_column('exams', 'exam_type')

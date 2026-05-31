"""finance tables

Revision ID: f7a3d21bc849
Revises: b298fe56f3f7
Create Date: 2026-05-31 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7a3d21bc849'
down_revision: Union[str, None] = 'b298fe56f3f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'categories',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('emoji', sa.String(10), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('color', sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'transactions',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_uuid', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_uuid'], ['bank_user.user_uuid']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_transactions_user_uuid', 'transactions', ['user_uuid'])

    op.create_table(
        'user_profiles',
        sa.Column('user_uuid', sa.Uuid(), nullable=False),
        sa.Column('xp', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('xp_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('gems', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('streak_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_activity_date', sa.String(20), nullable=True),
        sa.Column('growth_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('financial_score', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('monthly_limit', sa.Float(), nullable=False, server_default='0'),
        sa.Column('tree_leaves', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leaves_to_next', sa.Integer(), nullable=False, server_default='10'),
        sa.ForeignKeyConstraint(['user_uuid'], ['bank_user.user_uuid']),
        sa.PrimaryKeyConstraint('user_uuid'),
    )

    op.create_table(
        'xp_history',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_uuid', sa.Uuid(), nullable=False),
        sa.Column('month', sa.String(20), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['user_uuid'], ['bank_user.user_uuid']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_xp_history_user_uuid', 'xp_history', ['user_uuid'])

    op.create_table(
        'user_skills',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_uuid', sa.Uuid(), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('color', sa.String(20), nullable=False, server_default='primary'),
        sa.ForeignKeyConstraint(['user_uuid'], ['bank_user.user_uuid']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_skills_user_uuid', 'user_skills', ['user_uuid'])

    op.create_table(
        'goals',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_uuid', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('current', sa.Float(), nullable=False, server_default='0'),
        sa.Column('target', sa.Float(), nullable=False),
        sa.Column('deadline', sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(['user_uuid'], ['bank_user.user_uuid']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_goals_user_uuid', 'goals', ['user_uuid'])

    op.create_table(
        'milestones',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('goal_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('date', sa.String(30), nullable=False),
        sa.Column('xp', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='locked'),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_milestones_goal_id', 'milestones', ['goal_id'])

    op.create_table(
        'milestone_subtasks',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('milestone_id', sa.Uuid(), nullable=False),
        sa.Column('text', sa.String(500), nullable=False),
        sa.Column('done', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['milestone_id'], ['milestones.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_milestone_subtasks_milestone_id', 'milestone_subtasks', ['milestone_id'])

    op.create_table(
        'lessons',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('subtitle', sa.String(255), nullable=False, server_default=''),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('xp', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('duration', sa.Integer(), nullable=False, server_default='10'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'user_lessons',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_uuid', sa.Uuid(), nullable=False),
        sa.Column('lesson_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='locked'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['user_uuid'], ['bank_user.user_uuid']),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_lessons_user_uuid', 'user_lessons', ['user_uuid'])

    op.create_table(
        'challenges',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('total', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('reward', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('type', sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'user_challenges',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_uuid', sa.Uuid(), nullable=False),
        sa.Column('challenge_id', sa.Uuid(), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.ForeignKeyConstraint(['user_uuid'], ['bank_user.user_uuid']),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_challenges_user_uuid', 'user_challenges', ['user_uuid'])

    op.create_table(
        'achievements',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'user_achievements',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_uuid', sa.Uuid(), nullable=False),
        sa.Column('achievement_id', sa.Uuid(), nullable=False),
        sa.Column('unlocked', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['user_uuid'], ['bank_user.user_uuid']),
        sa.ForeignKeyConstraint(['achievement_id'], ['achievements.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_achievements_user_uuid', 'user_achievements', ['user_uuid'])

    op.create_table(
        'market_items',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('cost', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('color', sa.String(30), nullable=False, server_default='#4CAF50'),
        sa.Column('emoji', sa.String(10), nullable=False, server_default='🌳'),
        sa.Column('category', sa.String(30), nullable=False),
        sa.Column('is_new', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('stages_json', sa.Text(), nullable=False, server_default='[]'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'user_market_items',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_uuid', sa.Uuid(), nullable=False),
        sa.Column('item_id', sa.Uuid(), nullable=False),
        sa.Column('owned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['user_uuid'], ['bank_user.user_uuid']),
        sa.ForeignKeyConstraint(['item_id'], ['market_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_market_items_user_uuid', 'user_market_items', ['user_uuid'])

    op.create_table(
        'savings_goals',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_uuid', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.String(500), nullable=False, server_default=''),
        sa.Column('icon', sa.String(10), nullable=False, server_default='💰'),
        sa.Column('current', sa.Float(), nullable=False, server_default='0'),
        sa.Column('target', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['user_uuid'], ['bank_user.user_uuid']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_savings_goals_user_uuid', 'savings_goals', ['user_uuid'])


def downgrade() -> None:
    op.drop_index('ix_savings_goals_user_uuid', table_name='savings_goals')
    op.drop_table('savings_goals')
    op.drop_index('ix_user_market_items_user_uuid', table_name='user_market_items')
    op.drop_table('user_market_items')
    op.drop_table('market_items')
    op.drop_index('ix_user_achievements_user_uuid', table_name='user_achievements')
    op.drop_table('user_achievements')
    op.drop_table('achievements')
    op.drop_index('ix_user_challenges_user_uuid', table_name='user_challenges')
    op.drop_table('user_challenges')
    op.drop_table('challenges')
    op.drop_index('ix_user_lessons_user_uuid', table_name='user_lessons')
    op.drop_table('user_lessons')
    op.drop_table('lessons')
    op.drop_index('ix_milestone_subtasks_milestone_id', table_name='milestone_subtasks')
    op.drop_table('milestone_subtasks')
    op.drop_index('ix_milestones_goal_id', table_name='milestones')
    op.drop_table('milestones')
    op.drop_index('ix_goals_user_uuid', table_name='goals')
    op.drop_table('goals')
    op.drop_index('ix_user_skills_user_uuid', table_name='user_skills')
    op.drop_table('user_skills')
    op.drop_index('ix_xp_history_user_uuid', table_name='xp_history')
    op.drop_table('xp_history')
    op.drop_table('user_profiles')
    op.drop_index('ix_transactions_user_uuid', table_name='transactions')
    op.drop_table('transactions')
    op.drop_table('categories')

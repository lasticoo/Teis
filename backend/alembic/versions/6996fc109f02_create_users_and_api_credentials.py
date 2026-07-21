"""create_users_and_api_credentials

Revision ID: 6996fc109f02
Revises: 002_add_v1_3_tables
Create Date: 2026-07-20 21:36:33.219585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6996fc109f02'
down_revision: Union[str, None] = '002_add_v1_3_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create api_credentials table
    op.create_table('api_credentials',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('service_name', sa.String(length=50), nullable=False),
        sa.Column('encrypted_api_key', sa.String(length=500), nullable=False),
        sa.Column('encrypted_api_secret', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_name')
    )
    
    # 2. Create users table
    op.create_table('users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('totp_secret', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )


def downgrade() -> None:
    op.drop_table('users')
    op.drop_table('api_credentials')

"""Add mfe_price and mae_price columns to trades table

Revision ID: 005_add_mfe_mae_columns
Revises: 004_backup_history
Create Date: 2026-07-28 17:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '005_add_mfe_mae_columns'
down_revision: Union[str, None] = '004_backup_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('trades')]
    
    statements = []
    if 'mfe_price' not in cols:
        statements.append("ADD COLUMN mfe_price DECIMAL(20,8) NULL")
    if 'mae_price' not in cols:
        statements.append("ADD COLUMN mae_price DECIMAL(20,8) NULL")
        
    if statements:
        sql = f"ALTER TABLE trades {', '.join(statements)};"
        op.execute(sql)

def downgrade() -> None:
    op.execute("ALTER TABLE trades DROP COLUMN mae_price, DROP COLUMN mfe_price;")

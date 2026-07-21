"""Add V1.3 tables and enum updates

Revision ID: 002_add_v1_3_tables
Revises: 001_initial_migration
Create Date: 2026-07-20 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_add_v1_3_tables'
down_revision: Union[str, None] = '001_initial_migration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Update data_source ENUM in trades table
    op.execute("""
        ALTER TABLE trades MODIFY COLUMN data_source ENUM('manual', 'binance_sync', 'historical_import') NOT NULL;
    """)

    # 2. Create system_notifications table
    op.execute("""
    CREATE TABLE system_notifications (
        id CHAR(36) PRIMARY KEY,
        type ENUM('trade_pending_tag','edge_status_change','sync_failure') NOT NULL,
        reference_id CHAR(36) NULL,
        channel ENUM('in_app','web_push','email') NOT NULL,
        message TEXT NOT NULL,
        sent_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
        acknowledged_at DATETIME(3) NULL,
        INDEX idx_notif_type_sent (type, sent_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 3. Create equity_snapshots table
    op.execute("""
    CREATE TABLE equity_snapshots (
        id CHAR(36) PRIMARY KEY,
        balance DECIMAL(20,8) NOT NULL,
        unrealized_pnl DECIMAL(20,8) NOT NULL,
        captured_at DATETIME(3) NOT NULL,
        INDEX idx_equity_time (captured_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 4. Create account_transfers table
    op.execute("""
    CREATE TABLE account_transfers (
        id CHAR(36) PRIMARY KEY,
        amount DECIMAL(20,8) NOT NULL,
        asset VARCHAR(10) NOT NULL,
        occurred_at DATETIME(3) NOT NULL,
        binance_transfer_ref VARCHAR(100) NULL,
        INDEX idx_transfer_time (occurred_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

def downgrade() -> None:
    # Drop tables
    op.drop_table('account_transfers')
    op.drop_table('equity_snapshots')
    op.drop_table('system_notifications')

    # Revert data_source ENUM in trades table
    op.execute("""
        ALTER TABLE trades MODIFY COLUMN data_source ENUM('manual', 'binance_sync') NOT NULL;
    """)

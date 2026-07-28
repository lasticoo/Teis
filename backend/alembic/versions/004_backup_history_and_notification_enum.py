"""Add backup_history table and update system_notifications.type enum

Revision ID: 004_backup_history_and_notification_enum
Revises: 003_edge_validation_criteria
Create Date: 2026-07-28 17:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_backup_history'
down_revision: Union[str, None] = '003_edge_validation_criteria'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Modify system_notifications.type enum
    op.execute("""
    ALTER TABLE system_notifications
      MODIFY COLUMN type ENUM('trade_pending_tag','edge_status_change','sync_failure',
                               'backup_success','backup_failure','restore_drill_reminder') NOT NULL;
    """)

    # 2. Create backup_history table
    op.execute("""
    CREATE TABLE IF NOT EXISTS backup_history (
      id CHAR(36) PRIMARY KEY,
      backup_type ENUM('daily_sql', 'weekly_export') NOT NULL,
      status ENUM('success', 'failed') NOT NULL,
      file_path_local VARCHAR(500) NULL,
      file_path_remote VARCHAR(500) NULL,
      file_size_bytes BIGINT NULL,
      error_message TEXT NULL,
      created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS backup_history;")
    op.execute("""
    ALTER TABLE system_notifications
      MODIFY COLUMN type ENUM('trade_pending_tag','edge_status_change','sync_failure') NOT NULL;
    """)

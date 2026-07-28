"""Add Fitur 16 Edge Validation Criteria columns to edge_blueprints

Revision ID: 003_edge_validation_criteria
Revises: 002_add_v1_3_tables
Create Date: 2026-07-28 16:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_edge_validation_criteria'
down_revision: Union[str, None] = '002_add_v1_3_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
    ALTER TABLE edge_blueprints
      ADD COLUMN is_stable BOOLEAN NULL,
      ADD COLUMN is_repeatable BOOLEAN NULL,
      ADD COLUMN is_robust BOOLEAN NULL,
      ADD COLUMN stability_detail JSON NULL,
      ADD COLUMN repeatability_detail JSON NULL,
      ADD COLUMN robustness_detail JSON NULL,
      ADD COLUMN criteria_evaluated_at DATETIME(3) NULL;
    """)

def downgrade() -> None:
    op.execute("""
    ALTER TABLE edge_blueprints
      DROP COLUMN criteria_evaluated_at,
      DROP COLUMN robustness_detail,
      DROP COLUMN repeatability_detail,
      DROP COLUMN stability_detail,
      DROP COLUMN is_robust,
      DROP COLUMN is_repeatable,
      DROP COLUMN is_stable;
    """)

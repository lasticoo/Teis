"""Add Fitur 16 Edge Validation Criteria columns to edge_blueprints

Revision ID: 003_edge_validation_criteria
Revises: 002_add_v1_3_tables
Create Date: 2026-07-28 16:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_edge_validation_criteria'
down_revision: Union[str, None] = '6996fc109f02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('edge_blueprints')]
    
    statements = []
    if 'is_stable' not in cols:
        statements.append("ADD COLUMN is_stable BOOLEAN NULL")
    if 'is_repeatable' not in cols:
        statements.append("ADD COLUMN is_repeatable BOOLEAN NULL")
    if 'is_robust' not in cols:
        statements.append("ADD COLUMN is_robust BOOLEAN NULL")
    if 'stability_detail' not in cols:
        statements.append("ADD COLUMN stability_detail JSON NULL")
    if 'repeatability_detail' not in cols:
        statements.append("ADD COLUMN repeatability_detail JSON NULL")
    if 'robustness_detail' not in cols:
        statements.append("ADD COLUMN robustness_detail JSON NULL")
    if 'criteria_evaluated_at' not in cols:
        statements.append("ADD COLUMN criteria_evaluated_at DATETIME(3) NULL")
        
    if statements:
        sql = f"ALTER TABLE edge_blueprints {', '.join(statements)};"
        op.execute(sql)

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

"""Initial migration

Revision ID: 001_initial_migration
Revises: 
Create Date: 2026-07-17 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_migration'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. trades table
    op.execute("""
    CREATE TABLE trades (
        id CHAR(36) PRIMARY KEY,
        pair VARCHAR(20) NOT NULL,
        direction ENUM('long','short') NOT NULL,
        entry_price DECIMAL(20,8) NOT NULL,
        exit_price DECIMAL(20,8) NULL,
        stop_loss DECIMAL(20,8) NULL,
        take_profit DECIMAL(20,8) NULL,
        margin DECIMAL(20,8) NULL,
        leverage DECIMAL(6,2) NULL,
        risk_amount DECIMAL(20,8) NULL,
        rr_planned DECIMAL(6,2) NULL,
        rr_realized DECIMAL(6,2) NULL,
        pnl DECIMAL(20,8) NULL,
        fee DECIMAL(20,8) NULL,
        entry_time DATETIME(3) NOT NULL,
        exit_time DATETIME(3) NULL,
        holding_time_sec INT GENERATED ALWAYS AS (TIMESTAMPDIFF(SECOND, entry_time, exit_time)) STORED,
        data_source ENUM('manual','binance_sync') NOT NULL,
        locked_at DATETIME(3) NULL,
        created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
        INDEX idx_trades_pair_time (pair, entry_time),
        INDEX idx_trades_locked (locked_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 2. exchange_fills table
    op.execute("""
    CREATE TABLE exchange_fills (
        id CHAR(36) PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        binance_trade_id BIGINT NOT NULL,
        binance_order_id BIGINT NOT NULL,
        price DECIMAL(20,8) NOT NULL,
        qty DECIMAL(20,8) NOT NULL,
        fee DECIMAL(20,8) NOT NULL,
        funding_fee DECIMAL(20,8) NULL,
        side VARCHAR(10) NOT NULL,
        executed_at DATETIME(3) NOT NULL,
        raw_payload JSON NULL,
        UNIQUE KEY uq_fill (symbol, binance_trade_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 3. trade_fills table
    op.execute("""
    CREATE TABLE trade_fills (
        id CHAR(36) PRIMARY KEY,
        trade_id CHAR(36) NOT NULL,
        exchange_fill_id CHAR(36) NOT NULL,
        role ENUM('entry','exit') NOT NULL,
        CONSTRAINT fk_tf_trade FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
        CONSTRAINT fk_tf_fill FOREIGN KEY (exchange_fill_id) REFERENCES exchange_fills(id) ON DELETE CASCADE,
        UNIQUE KEY uq_trade_fill (trade_id, exchange_fill_id),
        INDEX idx_tf_trade_role (trade_id, role)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 4. trade_execution table
    op.execute("""
    CREATE TABLE trade_execution (
        id CHAR(36) PRIMARY KEY,
        trade_id CHAR(36) NOT NULL UNIQUE,
        order_type ENUM('limit','market') NOT NULL,
        moved_to_breakeven BOOLEAN NOT NULL DEFAULT FALSE,
        trailing_stop_used BOOLEAN NOT NULL DEFAULT FALSE,
        exit_reason ENUM('take_profit','stop_loss','manual_close','breakeven') NULL,
        CONSTRAINT fk_exec_trade FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 5. market_context table
    op.execute("""
    CREATE TABLE market_context (
        id CHAR(36) PRIMARY KEY,
        trade_id CHAR(36) NOT NULL,
        trend_htf VARCHAR(20) NULL,
        trend_ltf VARCHAR(20) NULL,
        bias_arah_manual ENUM('bull_trend','bear_trend','range') NULL,
        atr DECIMAL(20,8) NULL,
        volume_24h DECIMAL(24,4) NULL,
        session ENUM('asia','london','new_york') NOT NULL,
        btc_dominance DECIMAL(6,2) NULL,
        fear_greed_index TINYINT UNSIGNED NULL,
        funding_rate DECIMAL(10,6) NULL,
        open_interest DECIMAL(24,4) NULL,
        captured_at DATETIME(3) NOT NULL,
        CONSTRAINT fk_mc_trade FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 6. setup_taxonomy_versions table
    op.execute("""
    CREATE TABLE setup_taxonomy_versions (
        id CHAR(36) PRIMARY KEY,
        version_number INT NOT NULL,
        tag_name VARCHAR(50) NOT NULL,
        tag_definition TEXT NOT NULL,
        effective_from DATETIME(3) NOT NULL,
        effective_until DATETIME(3) NULL,
        UNIQUE KEY uq_version_tag (version_number, tag_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 7. trade_setup_tags table
    op.execute("""
    CREATE TABLE trade_setup_tags (
        trade_id CHAR(36) NOT NULL,
        taxonomy_version_id CHAR(36) NOT NULL,
        PRIMARY KEY (trade_id, taxonomy_version_id),
        CONSTRAINT fk_tst_trade FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
        CONSTRAINT fk_tst_tax FOREIGN KEY (taxonomy_version_id) REFERENCES setup_taxonomy_versions(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 8. psychology table
    op.execute("""
    CREATE TABLE psychology (
        id CHAR(36) PRIMARY KEY,
        trade_id CHAR(36) NOT NULL UNIQUE,
        confidence_level TINYINT NOT NULL,
        psychological_tags JSON NOT NULL,
        plan_adherence BOOLEAN NOT NULL,
        free_notes TEXT NULL,
        CONSTRAINT fk_psy_trade FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
        CONSTRAINT chk_confidence CHECK (confidence_level BETWEEN 1 AND 10)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 9. screenshots table
    op.execute("""
    CREATE TABLE screenshots (
        id CHAR(36) PRIMARY KEY,
        trade_id CHAR(36) NOT NULL,
        stage ENUM('before_entry','during_trade','exit') NOT NULL,
        file_path VARCHAR(500) NOT NULL,
        uploaded_at DATETIME(3) NOT NULL,
        CONSTRAINT fk_ss_trade FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 10. trade_corrections table
    op.execute("""
    CREATE TABLE trade_corrections (
        id CHAR(36) PRIMARY KEY,
        original_trade_id CHAR(36) NOT NULL,
        field_name VARCHAR(50) NOT NULL,
        old_value VARCHAR(255) NULL,
        new_value VARCHAR(255) NULL,
        reason TEXT NOT NULL,
        corrected_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
        CONSTRAINT fk_corr_trade FOREIGN KEY (original_trade_id) REFERENCES trades(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 11. edge_blueprints table
    op.execute("""
    CREATE TABLE edge_blueprints (
        id CHAR(36) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        setup_combination JSON NOT NULL,
        sample_size INT NOT NULL,
        expectancy_r DECIMAL(8,4) NOT NULL,
        ci_lower DECIMAL(8,4) NOT NULL,
        ci_upper DECIMAL(8,4) NOT NULL,
        status ENUM('learning','research','validation','production','monitoring') NOT NULL DEFAULT 'learning',
        created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
        updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 12. TRIGGERS for Immutability

    # Trigger on trades
    op.execute("""
    CREATE TRIGGER before_update_trades
    BEFORE UPDATE ON trades
    FOR EACH ROW
    BEGIN
        IF OLD.locked_at IS NOT NULL THEN
            IF NEW.pair != OLD.pair OR
               NEW.direction != OLD.direction OR
               NEW.entry_price != OLD.entry_price OR
               NEW.stop_loss != OLD.stop_loss OR
               NEW.take_profit != OLD.take_profit OR
               NEW.margin != OLD.margin OR
               NEW.leverage != OLD.leverage OR
               NEW.risk_amount != OLD.risk_amount OR
               NEW.rr_planned != OLD.rr_planned OR
               NEW.fee != OLD.fee OR
               NEW.entry_time != OLD.entry_time OR
               NEW.data_source != OLD.data_source OR
               NEW.created_at != OLD.created_at THEN
                SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Trade sudah terkunci, gunakan trade_corrections';
            END IF;
        END IF;
    END;
    """)

    # Trigger on psychology
    op.execute("""
    CREATE TRIGGER before_update_psychology
    BEFORE UPDATE ON psychology
    FOR EACH ROW
    BEGIN
        DECLARE is_locked DATETIME(3);
        SELECT locked_at INTO is_locked FROM trades WHERE id = NEW.trade_id;
        IF is_locked IS NOT NULL THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Trade sudah terkunci, gunakan trade_corrections';
        END IF;
    END;
    """)

    op.execute("""
    CREATE TRIGGER before_delete_psychology
    BEFORE DELETE ON psychology
    FOR EACH ROW
    BEGIN
        DECLARE is_locked DATETIME(3);
        SELECT locked_at INTO is_locked FROM trades WHERE id = OLD.trade_id;
        IF is_locked IS NOT NULL THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Trade sudah terkunci, gunakan trade_corrections';
        END IF;
    END;
    """)

    # Trigger on trade_setup_tags
    op.execute("""
    CREATE TRIGGER before_update_trade_setup_tags
    BEFORE UPDATE ON trade_setup_tags
    FOR EACH ROW
    BEGIN
        DECLARE is_locked DATETIME(3);
        SELECT locked_at INTO is_locked FROM trades WHERE id = NEW.trade_id;
        IF is_locked IS NOT NULL THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Trade sudah terkunci, gunakan trade_corrections';
        END IF;
    END;
    """)

    op.execute("""
    CREATE TRIGGER before_delete_trade_setup_tags
    BEFORE DELETE ON trade_setup_tags
    FOR EACH ROW
    BEGIN
        DECLARE is_locked DATETIME(3);
        SELECT locked_at INTO is_locked FROM trades WHERE id = OLD.trade_id;
        IF is_locked IS NOT NULL THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Trade sudah terkunci, gunakan trade_corrections';
        END IF;
    END;
    """)

def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS before_update_trades;")
    op.execute("DROP TRIGGER IF EXISTS before_update_psychology;")
    op.execute("DROP TRIGGER IF EXISTS before_delete_psychology;")
    op.execute("DROP TRIGGER IF EXISTS before_update_trade_setup_tags;")
    op.execute("DROP TRIGGER IF EXISTS before_delete_trade_setup_tags;")

    # Drop tables
    op.drop_table('edge_blueprints')
    op.drop_table('trade_corrections')
    op.drop_table('screenshots')
    op.drop_table('psychology')
    op.drop_table('trade_setup_tags')
    op.drop_table('setup_taxonomy_versions')
    op.drop_table('market_context')
    op.drop_table('trade_execution')
    op.drop_table('trade_fills')
    op.drop_table('exchange_fills')
    op.drop_table('trades')

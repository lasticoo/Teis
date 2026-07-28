import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from fastapi import APIRouter, Depends, Response, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

from app.database import get_db, engine
from app.models.models import Base
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["Database Backup"])


def serialize_sql_value(val: Any) -> str:
    """
    Escapes and serializes Python/SQLAlchemy data types into valid MySQL literals.
    """
    if val is None:
        return "NULL"
    elif isinstance(val, bool):
        return "1" if val else "0"
    elif isinstance(val, (int, float, Decimal)):
        return str(val)
    elif isinstance(val, datetime):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S.%f')[:23]}'"
    else:
        # String or JSON - escape single quotes and backslashes
        escaped = str(val).replace("\\", "\\\\").replace("'", "''").replace("\0", "")
        return f"'{escaped}'"


@router.get("/download")
def download_database_backup(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    """
    Generates a full MySQL .sql dump file of all TEIS tables and data for manual user backup.
    """
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        sql_lines = [
            "-- ========================================================",
            "-- TRADING EDGE INTELLIGENCE SYSTEM (TEIS) DATABASE BACKUP",
            f"-- Generated At: {now_str}",
            "-- Format: MySQL 8.0 SQL Dump",
            "-- ========================================================",
            "",
            "SET FOREIGN_KEY_CHECKS = 0;",
            "SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';",
            "SET NAMES utf8mb4;",
            ""
        ]

        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        for table in table_names:
            sql_lines.append(f"-- --------------------------------------------------------")
            sql_lines.append(f"-- Table structure & data for `{table}`")
            sql_lines.append(f"-- --------------------------------------------------------")

            # Get CREATE TABLE DDL
            ddl_row = db.execute(text(f"SHOW CREATE TABLE `{table}`")).fetchone()
            if ddl_row and len(ddl_row) >= 2:
                create_sql = ddl_row[1]
                sql_lines.append(f"DROP TABLE IF EXISTS `{table}`;")
                sql_lines.append(f"{create_sql};")
                sql_lines.append("")

            # Get table data
            data_rows = db.execute(text(f"SELECT * FROM `{table}`")).fetchall()
            if data_rows:
                # Fetch column names
                columns_result = db.execute(text(f"SHOW COLUMNS FROM `{table}`")).fetchall()
                col_names = [col[0] for col in columns_result]
                col_str = ", ".join([f"`{c}`" for c in col_names])

                sql_lines.append(f"-- Dumping data for table `{table}` ({len(data_rows)} rows)")
                for row in data_rows:
                    val_strs = [serialize_sql_value(v) for v in row]
                    vals_joined = ", ".join(val_strs)
                    sql_lines.append(f"INSERT INTO `{table}` ({col_str}) VALUES ({vals_joined});")
                sql_lines.append("")

        sql_lines.append("SET FOREIGN_KEY_CHECKS = 1;")
        sql_lines.append("-- Dump completed successfully.")

        sql_content = "\n".join(sql_lines)
        filename = f"teis_backup_{filename_stamp}.sql"

        return Response(
            content=sql_content,
            media_type="application/sql",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

    except Exception as e:
        logger.error(f"❌ Failed to generate database backup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menggenerasi backup database: {str(e)}"
        )

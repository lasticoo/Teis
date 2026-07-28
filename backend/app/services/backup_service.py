import os
import io
import csv
import zipfile
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Tuple, Optional
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

from app.config import settings
from app.models.models import BackupHistory, SystemNotification

logger = logging.getLogger(__name__)


def serialize_sql_value(val: Any) -> str:
    """Escapes and serializes Python/SQLAlchemy data types into valid MySQL literals."""
    if val is None:
        return "NULL"
    elif isinstance(val, bool):
        return "1" if val else "0"
    elif isinstance(val, (int, float, Decimal)):
        return str(val)
    elif isinstance(val, datetime):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S.%f')[:23]}'"
    else:
        escaped = str(val).replace("\\", "\\\\").replace("'", "''").replace("\0", "")
        return f"'{escaped}'"


def generate_full_sql_dump(db: Session) -> str:
    """Generates a full MySQL .sql dump string containing DDL and data for all tables."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    inspector = inspect(db.get_bind())
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

    return "\n".join(sql_lines)


def get_backup_minio_client():
    """Initializes S3 client for MinIO and ensures the backup bucket exists."""
    endpoint_url = f"http://{settings.MINIO_ENDPOINT}"
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    bucket = settings.BACKUP_MINIO_BUCKET
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        try:
            s3.create_bucket(Bucket=bucket)
            logger.info(f"✅ MinIO bucket '{bucket}' created successfully.")
        except Exception as e:
            logger.warning(f"Could not create MinIO bucket '{bucket}': {e}")
    return s3


class BackupService:
    """Core Service managing automated daily backups, weekly exports, MinIO sync, and retention cleanup."""

    @staticmethod
    def run_daily_backup(db: Session) -> BackupHistory:
        """Runs daily SQL backup: saves to local volume, uploads to MinIO, records history & sends alert."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"teis_backup_{timestamp}.sql"
        
        local_dir = os.path.join(settings.BACKUP_LOCAL_PATH, "daily")
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, filename)
        remote_key = f"daily/{filename}"

        file_size = 0
        error_msg = None
        local_success = False
        remote_success = False

        # 1. Generate SQL dump
        try:
            sql_dump = generate_full_sql_dump(db)
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(sql_dump)
            file_size = os.path.getsize(local_path)
            local_success = True
        except Exception as e:
            logger.error(f"❌ Failed to write local backup file: {e}")
            error_msg = f"Failed local backup: {str(e)}"

        # 2. Upload to MinIO
        if local_success:
            try:
                s3 = get_backup_minio_client()
                s3.upload_file(local_path, settings.BACKUP_MINIO_BUCKET, remote_key)
                remote_success = True
            except Exception as e:
                logger.warning(f"⚠️ Failed to upload backup to MinIO bucket '{settings.BACKUP_MINIO_BUCKET}': {e}")
                if not error_msg:
                    error_msg = f"MinIO upload failed: {str(e)}"

        # Determine overall status (Success if local or remote succeeded)
        overall_status = "success" if (local_success or remote_success) else "failed"

        # Record in backup_history
        history_rec = BackupHistory(
            backup_type="daily_sql",
            status=overall_status,
            file_path_local=local_path if local_success else None,
            file_path_remote=f"{settings.BACKUP_MINIO_BUCKET}/{remote_key}" if remote_success else None,
            file_size_bytes=file_size,
            error_message=error_msg
        )
        db.add(history_rec)
        db.commit()
        db.refresh(history_rec)

        # Multi-channel notification
        from app.services.notification_service import NotificationService
        if overall_status == "success":
            mb_size = file_size / (1024 * 1024)
            msg = f"✅ Backup database harian berhasil! Berkas: {filename} ({mb_size:.2f} MB)."
            if not remote_success:
                msg += " (Peringatan: Upload MinIO gagal, backup tersimpan di lokasi lokal)."
            try:
                NotificationService.send_multi_channel_notification(
                    db=db,
                    notification_type="backup_success",
                    message=msg,
                    reference_id=history_rec.id
                )
            except Exception as e:
                logger.error(f"Failed to dispatch backup_success notification: {e}")
        else:
            msg = f"🚨 KRITIS: Backup database harian GAGAL! Detail: {error_msg}"
            try:
                NotificationService.send_multi_channel_notification(
                    db=db,
                    notification_type="backup_failure",
                    message=msg,
                    reference_id=history_rec.id
                )
            except Exception as e:
                logger.error(f"Failed to dispatch backup_failure notification: {e}")

        return history_rec

    @staticmethod
    def cleanup_old_backups(db: Session, days: int = 30) -> int:
        """Removes local and MinIO daily backup files older than specified retention period (default 30 days)."""
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0

        # 1. Clean local files
        local_dir = os.path.join(settings.BACKUP_LOCAL_PATH, "daily")
        if os.path.exists(local_dir):
            for fname in os.listdir(local_dir):
                fpath = os.path.join(local_dir, fname)
                if os.path.isfile(fpath):
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if mtime < cutoff_date:
                        try:
                            os.remove(fpath)
                            deleted_count += 1
                            logger.info(f"🗑️ Cleaned up old local backup file: {fname}")
                        except Exception as e:
                            logger.warning(f"Could not remove local backup file {fname}: {e}")

        # 2. Clean MinIO objects under daily/
        try:
            s3 = get_backup_minio_client()
            bucket = settings.BACKUP_MINIO_BUCKET
            res = s3.list_objects_v2(Bucket=bucket, Prefix="daily/")
            if "Contents" in res:
                for obj in res["Contents"]:
                    last_mod = obj["LastModified"].replace(tzinfo=None)
                    if last_mod < cutoff_date:
                        try:
                            s3.delete_object(Bucket=bucket, Key=obj["Key"])
                            logger.info(f"🗑️ Cleaned up old MinIO backup object: {obj['Key']}")
                        except Exception as e:
                            logger.warning(f"Could not delete MinIO backup object {obj['Key']}: {e}")
        except Exception as e:
            logger.warning(f"Failed MinIO retention cleanup: {e}")

        return deleted_count

    @staticmethod
    def run_weekly_export(db: Session) -> BackupHistory:
        """Exports all tables into separate CSV files compressed into a ZIP archive for permanent retention."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"teis_export_{timestamp}.zip"
        
        local_dir = os.path.join(settings.BACKUP_LOCAL_PATH, "weekly")
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, filename)
        remote_key = f"weekly/{filename}"

        file_size = 0
        error_msg = None
        local_success = False
        remote_success = False

        try:
            inspector = inspect(db.get_bind())
            table_names = inspector.get_table_names()

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for table in table_names:
                    cols_result = db.execute(text(f"SHOW COLUMNS FROM `{table}`")).fetchall()
                    col_names = [c[0] for c in cols_result]
                    data_rows = db.execute(text(f"SELECT * FROM `{table}`")).fetchall()

                    csv_buffer = io.StringIO()
                    writer = csv.writer(csv_buffer)
                    writer.writerow(col_names)
                    for r in data_rows:
                        writer.writerow([str(val) if val is not None else "" for val in r])

                    zf.writestr(f"{table}.csv", csv_buffer.getvalue())

            with open(local_path, "wb") as f:
                f.write(zip_buffer.getvalue())

            file_size = os.path.getsize(local_path)
            local_success = True
        except Exception as e:
            logger.error(f"❌ Failed weekly CSV ZIP export: {e}")
            error_msg = str(e)

        if local_success:
            try:
                s3 = get_backup_minio_client()
                s3.upload_file(local_path, settings.BACKUP_MINIO_BUCKET, remote_key)
                remote_success = True
            except Exception as e:
                logger.warning(f"Failed MinIO upload for weekly export: {e}")
                if not error_msg:
                    error_msg = f"MinIO upload failed: {str(e)}"

        overall_status = "success" if (local_success or remote_success) else "failed"

        history_rec = BackupHistory(
            backup_type="weekly_export",
            status=overall_status,
            file_path_local=local_path if local_success else None,
            file_path_remote=f"{settings.BACKUP_MINIO_BUCKET}/{remote_key}" if remote_success else None,
            file_size_bytes=file_size,
            error_message=error_msg
        )
        db.add(history_rec)
        db.commit()
        db.refresh(history_rec)

        return history_rec

    @staticmethod
    def remind_restore_drill(db: Session) -> Optional[SystemNotification]:
        """Dispatches monthly restore drill notification reminding trader to verify restore procedure."""
        from app.services.notification_service import NotificationService
        latest = db.query(BackupHistory).order_by(BackupHistory.created_at.desc()).first()
        
        last_date = latest.created_at.strftime("%Y-%m-%d %H:%M") if latest else "Belum Ada"
        last_size_mb = f"{latest.file_size_bytes / (1024*1024):.2f} MB" if (latest and latest.file_size_bytes) else "0 MB"

        msg = (
            f"📅 PENGINGAT UJI RESTORE BULANAN: Sudah waktunya menguji restore backup database TEIS Anda. "
            f"Backup terakhir: {last_date} ({last_size_mb}). "
            f"Ikuti langkah restore di dokumentasi sebelum menganggap backup ini valid."
        )

        try:
            res = NotificationService.send_multi_channel_notification(
                db=db,
                notification_type="restore_drill_reminder",
                message=msg,
                reference_id=latest.id if latest else None
            )
            return res
        except Exception as e:
            logger.error(f"Failed restore drill reminder dispatch: {e}")
            return None

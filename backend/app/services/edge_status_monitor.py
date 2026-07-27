import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.models import EdgeBlueprint, Trade, SystemNotification

logger = logging.getLogger(__name__)


class EdgeStatusMonitor:
    """
    FITUR 13 - Mesin Validasi & Pemantau Status Edge (Edge Validation & Status Monitor)
    
    Manages automated edge maturity status transitions (Learning -> Research -> Validation -> Production -> Monitoring)
    and monitors 30-trade run-rate performance degradation against historical Confidence Intervals (ci_lower).
    """

    RUN_RATE_SAMPLE_SIZE = 30  # Last 30 trades run-rate window

    @classmethod
    def evaluate_all_edge_statuses(cls, db: Session) -> Dict[str, Any]:
        """
        Evaluates all edge blueprints, checks 30-trade run-rate degradation, updates statuses,
        and triggers multi-channel notifications on status changes.
        """
        logger.info("🔍 Running Edge Validation & Status Monitor process...")

        blueprints = db.query(EdgeBlueprint).all()
        if not blueprints:
            return {
                "status": "completed",
                "total_blueprints_evaluated": 0,
                "status_changes": [],
                "summary": {"production": 0, "validation": 0, "research": 0, "learning": 0, "monitoring": 0}
            }

        status_changes = []
        summary_counts = {"production": 0, "validation": 0, "research": 0, "learning": 0, "monitoring": 0}

        for bp in blueprints:
            tags = bp.setup_combination or []
            if not tags:
                continue

            old_status = bp.status
            n_tot = bp.sample_size
            ci_low = float(bp.ci_lower) if bp.ci_lower is not None else -99.0
            is_sig = bp.is_fdr_significant
            oos_exp = float(bp.out_of_sample_expectancy_r) if bp.out_of_sample_expectancy_r is not None else 0.0

            # 1. Fetch last 30 recent trades for run-rate monitoring
            placeholders = ", ".join([f"'{t}'" for t in tags])
            tag_count = len(tags)

            sql_recent = f"""
                SELECT t.id, t.rr_realized, t.pnl, t.entry_time
                FROM trades t
                JOIN trade_setup_tags st ON t.id = st.trade_id
                JOIN setup_taxonomy_versions stv ON st.taxonomy_version_id = stv.id
                WHERE stv.tag_name IN ({placeholders})
                  AND t.locked_at IS NOT NULL
                  AND t.exit_time IS NOT NULL
                  AND t.data_source != 'historical_import'
                GROUP BY t.id
                HAVING COUNT(DISTINCT stv.tag_name) >= {tag_count}
                ORDER BY t.entry_time DESC
                LIMIT {cls.RUN_RATE_SAMPLE_SIZE}
            """
            recent_rows = db.execute(text(sql_recent)).fetchall()
            recent_trades_count = len(recent_rows)

            recent_r_list = [
                float(r.rr_realized) if r.rr_realized is not None else (1.0 if float(r.pnl or 0) > 0 else -1.0)
                for r in recent_rows
            ]
            
            run_rate_mean_r = float(np.mean(recent_r_list)) if recent_r_list else float(bp.expectancy_r)

            # 2. Determine target status based on rules
            new_status = old_status

            if n_tot < 20:
                new_status = "learning"
            elif 20 <= n_tot < 30:
                new_status = "research"
            elif 30 <= n_tot < 50:
                new_status = "validation"
            else:
                # n >= 50
                if is_sig and ci_low > 0 and oos_exp > 0:
                    new_status = "production"
                else:
                    new_status = "validation"

            # 3. Check Run-Rate Performance Degradation for Production & Monitoring
            if old_status == "production" or new_status == "production":
                # Check if recent 30-trade run-rate dropped below historical ci_lower
                if recent_trades_count >= 1 and run_rate_mean_r < ci_low:
                    new_status = "monitoring"
                    logger.warning(
                        f"🚨 Edge '{bp.name}' run-rate ({run_rate_mean_r:.2f}R) dropped below ci_lower ({ci_low:.2f}R)!"
                    )
            elif old_status == "monitoring":
                # Check if recent 30-trade run-rate recovered above historical ci_lower
                if recent_trades_count >= 1 and run_rate_mean_r >= ci_low and oos_exp > 0:
                    new_status = "production" if n_tot >= 50 else "validation"
                    logger.info(
                        f"✅ Edge '{bp.name}' run-rate recovered ({run_rate_mean_r:.2f}R >= {ci_low:.2f}R)!"
                    )

            # 4. Handle Status Transitions & Trigger Alerts
            if old_status != new_status:
                bp.status = new_status
                bp.updated_at = datetime.now()

                msg = ""
                if new_status == "monitoring":
                    msg = (
                        f"🚨 ALERT: Edge '{bp.name}' mengalami penurunan status dari {old_status.upper()} ke MONITORING! "
                        f"Rata-rata 30 trade terakhir ({run_rate_mean_r:.2f}R) telah jatuh di bawah batas CI historis ({ci_low:.2f}R)."
                    )
                elif new_status == "production":
                    msg = (
                        f"🎉 PROMOSI: Edge '{bp.name}' berhasil pulih dan naik ke status PRODUCTION! "
                        f"Run-rate 30 trade terakhir ({run_rate_mean_r:.2f}R) telah melampaui batas CI historis ({ci_low:.2f}R)."
                    )
                else:
                    msg = f"ℹ️ Status Edge '{bp.name}' telah diperbarui dari {old_status.upper()} ke {new_status.upper()}."

                # Create SystemNotification record
                notif = SystemNotification(
                    type="edge_status_change",
                    reference_id=bp.id,
                    channel="in_app",
                    message=msg
                )
                db.add(notif)

                # Send multi-channel notification via NotificationService
                try:
                    from app.services.notification_service import NotificationService
                    NotificationService.send_notification(
                        db=db,
                        notification_type="edge_status_change",
                        message=msg,
                        reference_id=bp.id
                    )
                except Exception as notif_err:
                    logger.error(f"Gagal mengirim multi-channel notifikasi: {notif_err}")

                status_changes.append({
                    "edge_id": bp.id,
                    "name": bp.name,
                    "old_status": old_status,
                    "new_status": new_status,
                    "run_rate_mean_r": round(run_rate_mean_r, 4),
                    "ci_lower": round(ci_low, 4),
                    "message": msg
                })

            summary_counts[new_status] = summary_counts.get(new_status, 0) + 1

        db.commit()

        logger.info(f"✅ Edge Status Monitor complete. {len(status_changes)} status changes executed.")
        return {
            "status": "completed",
            "total_blueprints_evaluated": len(blueprints),
            "status_changes_count": len(status_changes),
            "status_changes": status_changes,
            "summary": summary_counts
        }

    @classmethod
    def get_status_overview(cls, db: Session) -> Dict[str, Any]:
        """
        Returns full status overview of all edges for API & Dashboard consumption.
        """
        blueprints = db.query(EdgeBlueprint).order_by(EdgeBlueprint.expectancy_r.desc()).all()
        
        summary = {"production": 0, "validation": 0, "research": 0, "learning": 0, "monitoring": 0}
        edge_details = []

        for bp in blueprints:
            st = bp.status
            summary[st] = summary.get(st, 0) + 1

            edge_details.append({
                "id": bp.id,
                "name": bp.name,
                "status": bp.status,
                "sample_size": bp.sample_size,
                "expectancy_r": float(bp.expectancy_r) if bp.expectancy_r is not None else 0.0,
                "ci_lower": float(bp.ci_lower) if bp.ci_lower is not None else 0.0,
                "ci_upper": float(bp.ci_upper) if bp.ci_upper is not None else 0.0,
                "win_rate_pct": float(bp.win_rate_pct) if bp.win_rate_pct is not None else 0.0,
                "is_fdr_significant": bp.is_fdr_significant,
                "out_of_sample_expectancy_r": float(bp.out_of_sample_expectancy_r) if bp.out_of_sample_expectancy_r is not None else 0.0,
                "updated_at": bp.updated_at.isoformat() if bp.updated_at else None
            })

        return {
            "total_edges": len(blueprints),
            "summary": summary,
            "edges": edge_details
        }

import logging
import math
from itertools import combinations
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.models import Trade, TradeSetupTag, EdgeBlueprint, SystemNotification

logger = logging.getLogger(__name__)


class EdgeDiscoveryEngine:
    """
    FITUR 12 - Mesin Penemu Edge (Edge Discovery Engine)
    
    Scientific statistical edge finder powered by vectorized NumPy Bootstrap resampling (10,000 iterations),
    Wilson Score Interval for win rate bounds, and Benjamini-Hochberg FDR (False Discovery Rate) correction.
    """

    BOOTSTRAP_ITERATIONS = 10000
    FDR_ALPHA = 0.05  # Target 5% FDR
    MIN_SAMPLE_SIZE = 20

    @classmethod
    def run_discovery(cls, db: Session) -> Dict[str, Any]:
        """
        Executes full Edge Discovery Engine workflow.
        Returns summary of discovered edges and execution status.
        Strict Rule (Bab 07.5 & Bab 08): ONLY locked non-imported trades (data_source != 'historical_import') are evaluated.
        """
        logger.info("⚡ Starting Edge Discovery Engine batch process...")

        trades_query = db.query(
            Trade.id,
            Trade.pair,
            Trade.entry_time,
            Trade.exit_time,
            Trade.rr_realized,
            Trade.pnl,
            Trade.data_source,
            Trade.locked_at
        ).filter(
            Trade.locked_at.isnot(None),
            Trade.exit_time.isnot(None),
            Trade.data_source != "historical_import"
        ).order_by(Trade.entry_time.asc()).all()

        if len(trades_query) < cls.MIN_SAMPLE_SIZE:
            msg = f"Data sampel live tidak mencukupi untuk discovery (Eksklusi Impor Historis). Syarat n >= {cls.MIN_SAMPLE_SIZE}, ditemukan {len(trades_query)} trade bertag locked."
            logger.info(msg)
            return {
                "status": "skipped",
                "reason": msg,
                "total_trades_analyzed": len(trades_query),
                "edges_discovered": 0
            }

        # 2. Map trade tags (from trade_setup_tags and setup_taxonomy_versions tables)
        tag_rows = db.execute(text("""
            SELECT st.trade_id, stv.tag_name 
            FROM trade_setup_tags st
            JOIN setup_taxonomy_versions stv ON st.taxonomy_version_id = stv.id
        """)).fetchall()

        trade_tags_map: Dict[str, List[str]] = {}
        for t_id, tag_name in tag_rows:
            if t_id not in trade_tags_map:
                trade_tags_map[t_id] = []
            trade_tags_map[t_id].append(tag_name)

        # Build trade objects list with R-multiples
        trade_data_list = []
        for t in trades_query:
            tags = sorted(list(set(trade_tags_map.get(t.id, []))))
            if not tags:
                continue
            r_val = float(t.rr_realized) if t.rr_realized is not None else (1.0 if float(t.pnl or 0) > 0 else -1.0)
            trade_data_list.append({
                "id": t.id,
                "entry_time": t.entry_time,
                "r_realized": r_val,
                "tags": tags
            })

        if not trade_data_list:
            return {
                "status": "skipped",
                "reason": "Tidak ada trade bertag yang dapat dievaluasi.",
                "total_trades_analyzed": 0,
                "edges_discovered": 0
            }

        # 3. Mine unique tag combinations (up to 4 tags per combination)
        combo_trades_map: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}

        for item in trade_data_list:
            tags = item["tags"]
            # Generate all subsets of length 1 to min(4, len(tags))
            max_k = min(4, len(tags))
            for k in range(1, max_k + 1):
                for combo in combinations(tags, k):
                    if combo not in combo_trades_map:
                        combo_trades_map[combo] = []
                    combo_trades_map[combo].append(item)

        # Filter combinations with sample size >= MIN_SAMPLE_SIZE
        valid_combos = {
            combo: trades
            for combo, trades in combo_trades_map.items()
            if len(trades) >= cls.MIN_SAMPLE_SIZE
        }

        if not valid_combos:
            msg = f"Tidak ada kombinasi tag unik yang memenuhi sampel n >= {cls.MIN_SAMPLE_SIZE}."
            logger.info(msg)
            return {
                "status": "completed",
                "reason": msg,
                "total_trades_analyzed": len(trade_data_list),
                "edges_discovered": 0
            }

        logger.info(f"Ditemukan {len(valid_combos)} kombinasi tag dengan sampel n >= {cls.MIN_SAMPLE_SIZE}.")

        # 4. Statistical Evaluation per combination (Discovery 70% / Validation 30% + 10,000 Vectorized Bootstrap)
        evaluation_results = []

        for combo, combo_trades in valid_combos.items():
            # Sort trades chronologically
            combo_trades_sorted = sorted(combo_trades, key=lambda x: x["entry_time"])
            n_total = len(combo_trades_sorted)

            # 70/30 Chronological Split
            n_disc = max(14, int(n_total * 0.70))
            disc_trades = combo_trades_sorted[:n_disc]
            val_trades = combo_trades_sorted[n_disc:]

            r_disc = np.array([t["r_realized"] for t in disc_trades], dtype=np.float64)
            r_val = np.array([t["r_realized"] for t in val_trades], dtype=np.float64) if val_trades else np.array([], dtype=np.float64)

            # Mean Expectancy (R) on Discovery
            expectancy_r = float(np.mean(r_disc))
            out_of_sample_expectancy_r = float(np.mean(r_val)) if len(r_val) > 0 else expectancy_r

            # Vectorized 10,000 Iteration Bootstrap Resampling
            matrix = np.random.choice(r_disc, size=(cls.BOOTSTRAP_ITERATIONS, len(r_disc)), replace=True)
            boot_means = matrix.mean(axis=1)

            # 95% Confidence Interval (2.5th and 97.5th percentiles)
            ci_lower = float(np.percentile(boot_means, 2.5))
            ci_upper = float(np.percentile(boot_means, 97.5))

            # Non-parametric P-value test (H0: mean <= 0)
            p_val = float(np.mean(boot_means <= 0.0))
            if p_val == 0.0:
                p_val = 1.0 / cls.BOOTSTRAP_ITERATIONS  # Minimum resolution limit

            # Wilson Score Interval for Win Rate
            wins_count = int(np.sum(r_disc > 0))
            win_rate_pct, wr_ci_low, wr_ci_high = cls._compute_wilson_score(wins_count, n_disc)

            evaluation_results.append({
                "combo": combo,
                "name": " + ".join(combo),
                "sample_size": n_total,
                "discovery_sample_size": n_disc,
                "validation_sample_size": len(val_trades),
                "expectancy_r": expectancy_r,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "p_value": p_val,
                "win_rate_pct": win_rate_pct,
                "win_rate_ci_lower": wr_ci_low,
                "win_rate_ci_upper": wr_ci_high,
                "out_of_sample_expectancy_r": out_of_sample_expectancy_r,
            })

        # 5. Benjamini-Hochberg FDR (False Discovery Rate) Correction
        evaluation_results.sort(key=lambda x: x["p_value"])
        m = len(evaluation_results)

        # Compute adjusted p-values (p_adj = p * m / rank)
        for rank_idx, res in enumerate(evaluation_results, start=1):
            p_adj = min(1.0, res["p_value"] * (m / rank_idx))
            res["fdr_adjusted_p_value"] = p_adj

        # Enforce right-to-left monotonic property for BH adjustment
        for i in range(m - 2, -1, -1):
            evaluation_results[i]["fdr_adjusted_p_value"] = min(
                evaluation_results[i]["fdr_adjusted_p_value"],
                evaluation_results[i + 1]["fdr_adjusted_p_value"]
            )

        for res in evaluation_results:
            res["is_fdr_significant"] = res["fdr_adjusted_p_value"] <= cls.FDR_ALPHA

        # 6. Status Assignment & Storage into `edge_blueprints` MySQL table
        stored_count = 0
        for res in evaluation_results:
            n_tot = res["sample_size"]
            is_sig = res["is_fdr_significant"]
            ci_low = res["ci_lower"]
            oos_exp = res["out_of_sample_expectancy_r"]

            # Status Rules (Dokumen Teknis Bab 08.5)
            if n_tot < 20:
                status = "learning"
            elif 20 <= n_tot < 30:
                status = "research"
            else:
                if is_sig and ci_low > 0 and oos_exp > 0:
                    status = "production" if n_tot >= 50 else "validation"
                elif oos_exp < 0 or ci_low < 0:
                    status = "monitoring"
                else:
                    status = "validation"

            combo_json = list(res["combo"])
            combo_name = res["name"]

            # Upsert into MySQL `edge_blueprints`
            existing = db.query(EdgeBlueprint).filter(
                EdgeBlueprint.name == combo_name
            ).first()

            if existing:
                old_status = existing.status
                existing.setup_combination = combo_json
                existing.sample_size = n_tot
                existing.expectancy_r = round(Decimal(str(res["expectancy_r"])), 4)
                existing.ci_lower = round(Decimal(str(res["ci_lower"])), 4)
                existing.ci_upper = round(Decimal(str(res["ci_upper"])), 4)
                existing.win_rate_pct = round(Decimal(str(res["win_rate_pct"])), 2)
                existing.win_rate_ci_lower = round(Decimal(str(res["win_rate_ci_lower"])), 2)
                existing.win_rate_ci_upper = round(Decimal(str(res["win_rate_ci_upper"])), 2)
                existing.p_value = round(Decimal(str(res["p_value"])), 6)
                existing.fdr_adjusted_p_value = round(Decimal(str(res["fdr_adjusted_p_value"])), 6)
                existing.is_fdr_significant = is_sig
                existing.out_of_sample_expectancy_r = round(Decimal(str(oos_exp)), 4)
                existing.status = status

                # Notify if status degraded to monitoring
                if old_status == "production" and status == "monitoring":
                    notif = SystemNotification(
                        type="edge_status_change",
                        reference_id=existing.id,
                        channel="in_app",
                        message=f"🚨 Edge '{combo_name}' mengalami penurunan status dari Production ke Monitoring (Expectancy: {res['expectancy_r']:.2f}R)."
                    )
                    db.add(notif)
            else:
                blueprint = EdgeBlueprint(
                    name=combo_name,
                    setup_combination=combo_json,
                    sample_size=n_tot,
                    expectancy_r=round(Decimal(str(res["expectancy_r"])), 4),
                    ci_lower=round(Decimal(str(res["ci_lower"])), 4),
                    ci_upper=round(Decimal(str(res["ci_upper"])), 4),
                    win_rate_pct=round(Decimal(str(res["win_rate_pct"])), 2),
                    win_rate_ci_lower=round(Decimal(str(res["win_rate_ci_lower"])), 2),
                    win_rate_ci_upper=round(Decimal(str(res["win_rate_ci_upper"])), 2),
                    p_value=round(Decimal(str(res["p_value"])), 6),
                    fdr_adjusted_p_value=round(Decimal(str(res["fdr_adjusted_p_value"])), 6),
                    is_fdr_significant=is_sig,
                    out_of_sample_expectancy_r=round(Decimal(str(oos_exp)), 4),
                    status=status
                )
                db.add(blueprint)
            
            stored_count += 1

        db.commit()

        logger.info(f"✅ Edge Discovery Engine completed! {stored_count} blueprints updated.")
        return {
            "status": "completed",
            "total_trades_analyzed": len(trade_data_list),
            "combinations_evaluated": len(valid_combos),
            "edges_discovered": stored_count,
            "results_summary": [
                {
                    "name": r["name"],
                    "sample_size": r["sample_size"],
                    "expectancy_r": r["expectancy_r"],
                    "ci": f"[{r['ci_lower']:.2f}R, {r['ci_upper']:.2f}R]",
                    "win_rate_pct": r["win_rate_pct"],
                    "is_fdr_significant": r["is_fdr_significant"]
                }
                for r in evaluation_results[:5]
            ]
        }

    @staticmethod
    def _compute_wilson_score(wins: int, n: int, confidence: float = 0.95) -> Tuple[float, float, float]:
        """
        Computes 95% Wilson Score Interval for Bernoulli win rate.
        Returns (win_rate_pct, ci_lower_pct, ci_upper_pct)
        """
        if n == 0:
            return 0.0, 0.0, 0.0

        p = wins / n
        z = 1.9599643984540054  # 95% confidence standard normal quantile

        center = (p + (z**2) / (2 * n)) / (1 + (z**2) / n)
        margin = (z / (1 + (z**2) / n)) * math.sqrt((p * (1 - p) / n) + ((z**2) / (4 * (n**2))))

        ci_lower = max(0.0, center - margin) * 100.0
        ci_upper = min(1.0, center + margin) * 100.0
        win_rate = p * 100.0

        return round(win_rate, 2), round(ci_lower, 2), round(ci_upper, 2)

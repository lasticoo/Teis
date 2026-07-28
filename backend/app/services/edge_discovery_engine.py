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
    FITUR 12 & FITUR 16 - Mesin Penemu Edge & Uji Validasi (Edge Discovery & Validation Criteria Engine)
    
    Scientific statistical edge finder powered by vectorized NumPy Bootstrap resampling (10,000 iterations),
    Wilson Score Interval for win rate bounds, Benjamini-Hochberg FDR (False Discovery Rate) correction,
    and 3 qualitative validation criteria (Stability, Repeatability, Robustness).
    """

    BOOTSTRAP_ITERATIONS = 10000
    FDR_ALPHA = 0.05  # Target 5% FDR
    MIN_SAMPLE_SIZE = 20
    STABILITY_MAX_CV = 0.75
    REPEATABILITY_MIN_SUBGROUP_N = 5
    ROBUSTNESS_MAX_DROP_PCT = 0.50

    @classmethod
    def _evaluate_stability(cls, trades_sorted: List[Dict[str, Any]]) -> Tuple[Optional[bool], Optional[Dict[str, Any]]]:
        """
        Sub-Test A: Uji Stabilitas
        Splits chronologically sorted trades into 3 equal periods.
        Checks if mean expectancy > 0 in all 3 periods and Coefficient of Variation (std / |mean|) <= STABILITY_MAX_CV.
        """
        N = len(trades_sorted)
        if N < 3:
            return None, None

        n_p = N // 3
        p1 = trades_sorted[:n_p]
        p2 = trades_sorted[n_p:2*n_p]
        p3 = trades_sorted[2*n_p:]

        periods_detail = []
        period_means = []

        for idx, p in enumerate([p1, p2, p3], start=1):
            if not p:
                continue
            r_list = [t["r_realized"] for t in p]
            exp_r = float(np.mean(r_list))
            period_means.append(exp_r)
            s_date = p[0]["entry_time"].strftime("%Y-%m-%d") if p[0].get("entry_time") else "N/A"
            e_date = p[-1]["entry_time"].strftime("%Y-%m-%d") if p[-1].get("entry_time") else "N/A"
            periods_detail.append({
                "period": idx,
                "range": f"{s_date} to {e_date}",
                "n": len(p),
                "expectancy_r": round(exp_r, 4)
            })

        if len(period_means) < 3:
            return None, None

        overall_mean = float(np.mean(period_means))
        overall_std = float(np.std(period_means, ddof=0))
        abs_mean = abs(overall_mean)
        cv = round(overall_std / abs_mean, 4) if abs_mean > 0 else 999.0

        all_positive = all(m > 0 for m in period_means)
        is_stable = all_positive and (cv <= cls.STABILITY_MAX_CV)

        stability_detail = {
            "periods": periods_detail,
            "overall_mean_expectancy_r": round(overall_mean, 4),
            "std_deviation": round(overall_std, 4),
            "coefficient_of_variation": cv,
            "threshold": cls.STABILITY_MAX_CV,
            "all_periods_positive": all_positive,
            "passed": is_stable
        }

        return is_stable, stability_detail

    @classmethod
    def _evaluate_repeatability(
        cls,
        trades_sorted: List[Dict[str, Any]],
        db: Session
    ) -> Tuple[Optional[bool], Optional[Dict[str, Any]]]:
        """
        Sub-Test B: Uji Keberulangan (Repeatable)
        Groups trades across 3 separate dimensions: pair, month (YYYY-MM), and session.
        Checks if majority (>50%) of valid subgroups (n >= REPEATABILITY_MIN_SUBGROUP_N) have positive expectancy R.
        """
        if not trades_sorted:
            return None, None

        trade_ids = [t["id"] for t in trades_sorted]
        if not trade_ids:
            return None, None

        placeholders = ", ".join([f"'{tid}'" for tid in trade_ids])
        sql = f"""
            SELECT t.id, t.pair, t.entry_time, mc.session
            FROM trades t
            LEFT JOIN market_context mc ON t.id = mc.trade_id
            WHERE t.id IN ({placeholders})
        """
        rows = db.execute(text(sql)).fetchall()
        meta_map = {r.id: {"pair": r.pair, "entry_time": r.entry_time, "session": r.session} for r in rows}

        trade_records = []
        for t in trades_sorted:
            m = meta_map.get(t["id"], {})
            e_time = m.get("entry_time") or t.get("entry_time")
            month_str = e_time.strftime("%Y-%m") if e_time else "N/A"
            trade_records.append({
                "id": t["id"],
                "r_realized": t["r_realized"],
                "pair": m.get("pair") or "N/A",
                "month": month_str,
                "session": m.get("session") or "N/A"
            })

        dimensions_res = {}
        evaluable_dims_passed = []

        for dim_key in ["pair", "month", "session"]:
            from collections import defaultdict
            grp = defaultdict(list)
            for tr in trade_records:
                grp[tr[dim_key]].append(tr["r_realized"])

            subgroups_info = []
            valid_subgroups_count = 0
            positive_subgroups_count = 0

            for group_val, r_vals in grp.items():
                if group_val == "N/A":
                    continue
                n_grp = len(r_vals)
                exp_grp = float(np.mean(r_vals)) if r_vals else 0.0
                is_val = n_grp >= cls.REPEATABILITY_MIN_SUBGROUP_N
                is_pos = exp_grp > 0

                if is_val:
                    valid_subgroups_count += 1
                    if is_pos:
                        positive_subgroups_count += 1

                subgroups_info.append({
                    "name": str(group_val),
                    "n": n_grp,
                    "expectancy_r": round(exp_grp, 4),
                    "is_valid_sample": is_val,
                    "is_positive": is_pos
                })

            if valid_subgroups_count >= 2:
                dim_passed = (positive_subgroups_count / valid_subgroups_count) > 0.50
                evaluable_dims_passed.append(dim_passed)
                status_desc = "passed" if dim_passed else "failed"
            else:
                dim_passed = True
                status_desc = "skipped_insufficient_coverage"

            dimensions_res[dim_key] = {
                "total_subgroups": len(grp),
                "valid_subgroups": valid_subgroups_count,
                "positive_subgroups": positive_subgroups_count,
                "passed": dim_passed,
                "status": status_desc,
                "subgroups": subgroups_info
            }

        is_repeatable = all(evaluable_dims_passed) if evaluable_dims_passed else True

        repeatability_detail = {
            "dimensions": dimensions_res,
            "evaluable_dimensions_count": len(evaluable_dims_passed),
            "passed": is_repeatable
        }

        return is_repeatable, repeatability_detail

    @classmethod
    def _evaluate_robustness(
        cls,
        trades_sorted: List[Dict[str, Any]],
        db: Session
    ) -> Tuple[Optional[bool], Optional[Dict[str, Any]]]:
        """
        Sub-Test C: Uji Robustness (Simple Mode)
        Simulates 8 TP/SL shift scenarios (+/- 5% and +/- 10%).
        Checks if expectancy R remains > 0 in all 8 scenarios and maximum expectancy drop <= ROBUSTNESS_MAX_DROP_PCT.
        """
        if not trades_sorted:
            return None, None

        trade_ids = [t["id"] for t in trades_sorted]
        if not trade_ids:
            return None, None

        placeholders = ", ".join([f"'{tid}'" for tid in trade_ids])
        sql = f"""
            SELECT t.id, t.entry_price, t.stop_loss, t.take_profit, t.margin, t.direction, tex.exit_reason
            FROM trades t
            LEFT JOIN trade_execution tex ON t.id = tex.trade_id
            WHERE t.id IN ({placeholders})
        """
        rows = db.execute(text(sql)).fetchall()
        exec_map = {
            r.id: {
                "entry_price": float(r.entry_price) if r.entry_price is not None else None,
                "stop_loss": float(r.stop_loss) if r.stop_loss is not None else None,
                "take_profit": float(r.take_profit) if r.take_profit is not None else None,
                "exit_reason": r.exit_reason,
                "direction": r.direction
            }
            for r in rows
        }

        shift_scenarios = [
            ("TP -5%", "TP", -0.05),
            ("TP +5%", "TP", 0.05),
            ("SL -5%", "SL", -0.05),
            ("SL +5%", "SL", 0.05),
            ("TP -10%", "TP", -0.10),
            ("TP +10%", "TP", 0.10),
            ("SL -10%", "SL", -0.10),
            ("SL +10%", "SL", 0.10),
        ]

        orig_r_list = [t["r_realized"] for t in trades_sorted]
        orig_expectancy = float(np.mean(orig_r_list)) if orig_r_list else 0.0

        excluded_count = 0
        manual_or_be_count = 0
        scenarios_results = []
        all_scenarios_positive = True
        max_drop_pct = 0.0

        for sc_name, target_param, pct in shift_scenarios:
            shifted_r_list = []
            for t in trades_sorted:
                m = exec_map.get(t["id"], {})
                r_orig = t["r_realized"]
                exit_reason = m.get("exit_reason")
                entry_p = m.get("entry_price")
                sl_p = m.get("stop_loss")
                tp_p = m.get("take_profit")

                if exit_reason in ("manual_close", "breakeven"):
                    shifted_r_list.append(r_orig)
                    if sc_name == "TP -5%":
                        manual_or_be_count += 1
                    continue

                if not entry_p or not sl_p or abs(entry_p - sl_p) == 0:
                    shifted_r_list.append(r_orig)
                    if sc_name == "TP -5%":
                        excluded_count += 1
                    continue

                risk_dist = abs(entry_p - sl_p)

                if exit_reason == "take_profit":
                    if target_param == "TP" and tp_p:
                        orig_tp_dist = abs(tp_p - entry_p)
                        new_tp_dist = orig_tp_dist * (1.0 + pct)
                        r_shifted = new_tp_dist / risk_dist
                    else:
                        r_shifted = r_orig
                elif exit_reason == "stop_loss":
                    if target_param == "SL":
                        new_sl_dist = risk_dist * (1.0 + pct)
                        r_shifted = -(new_sl_dist / risk_dist)
                    else:
                        r_shifted = r_orig
                else:
                    r_shifted = r_orig

                shifted_r_list.append(r_shifted)

            exp_shifted = float(np.mean(shifted_r_list)) if shifted_r_list else 0.0
            if exp_shifted <= 0:
                all_scenarios_positive = False

            if orig_expectancy > 0:
                drop_pct = (orig_expectancy - exp_shifted) / orig_expectancy
            else:
                drop_pct = 0.0

            if drop_pct > max_drop_pct:
                max_drop_pct = drop_pct

            scenarios_results.append({
                "scenario": sc_name,
                "expectancy_r": round(exp_shifted, 4),
                "drop_pct": round(max(0.0, drop_pct), 4),
                "positive": exp_shifted > 0
            })

        is_robust = all_scenarios_positive and (max_drop_pct <= cls.ROBUSTNESS_MAX_DROP_PCT)
        low_confidence = (manual_or_be_count / len(trades_sorted)) > 0.70 if trades_sorted else False

        robustness_detail = {
            "original_expectancy_r": round(orig_expectancy, 4),
            "excluded_count": excluded_count,
            "low_confidence": low_confidence,
            "scenarios": scenarios_results,
            "max_drop_pct": round(max_drop_pct, 4),
            "threshold": cls.ROBUSTNESS_MAX_DROP_PCT,
            "passed": is_robust
        }

        return is_robust, robustness_detail

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

            # Evaluate Fitur 16 Criteria: Stability, Repeatability, Robustness
            is_stable, stability_detail = None, None
            is_repeatable, repeatability_detail = None, None
            is_robust, robustness_detail = None, None

            if n_total >= 30:
                try:
                    is_stable, stability_detail = cls._evaluate_stability(combo_trades_sorted)
                    is_repeatable, repeatability_detail = cls._evaluate_repeatability(combo_trades_sorted, db)
                    is_robust, robustness_detail = cls._evaluate_robustness(combo_trades_sorted, db)
                except Exception as eval_err:
                    logger.error(f"❌ Error evaluating validation criteria for combination {combo}: {eval_err}", exc_info=True)
                    is_stable, is_repeatable, is_robust = None, None, None

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
                "is_stable": is_stable,
                "stability_detail": stability_detail,
                "is_repeatable": is_repeatable,
                "repeatability_detail": repeatability_detail,
                "is_robust": is_robust,
                "robustness_detail": robustness_detail,
                "combo_trades_sorted": combo_trades_sorted
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
        eval_now = datetime.now()

        for res in evaluation_results:
            n_tot = res["sample_size"]
            is_sig = res["is_fdr_significant"]
            ci_low = res["ci_lower"]
            oos_exp = res["out_of_sample_expectancy_r"]
            is_st = res["is_stable"]
            is_rep = res["is_repeatable"]
            is_rob = res["is_robust"]

            # Status Rules (Dokumen Teknis Bab 08.5 & Adendum Fitur 16)
            if n_tot < 20:
                status = "learning"
            elif 20 <= n_tot < 30:
                status = "research"
            else:
                # n_tot >= 30
                if is_sig and ci_low > 0 and oos_exp > 0:
                    if n_tot >= 50 and (is_st is True) and (is_rep is True) and (is_rob is True):
                        status = "production"
                    else:
                        status = "validation"
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
                existing.is_stable = is_st
                existing.is_repeatable = is_rep
                existing.is_robust = is_rob
                existing.stability_detail = res["stability_detail"]
                existing.repeatability_detail = res["repeatability_detail"]
                existing.robustness_detail = res["robustness_detail"]
                existing.criteria_evaluated_at = eval_now
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
                    is_stable=is_st,
                    is_repeatable=is_rep,
                    is_robust=is_rob,
                    stability_detail=res["stability_detail"],
                    repeatability_detail=res["repeatability_detail"],
                    robustness_detail=res["robustness_detail"],
                    criteria_evaluated_at=eval_now,
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
                    "is_fdr_significant": r["is_fdr_significant"],
                    "is_stable": r["is_stable"],
                    "is_repeatable": r["is_repeatable"],
                    "is_robust": r["is_robust"]
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

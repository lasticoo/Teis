from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models.models import EdgeBlueprint, Trade, TradeSetupTag
from app.services.edge_discovery_engine import EdgeDiscoveryEngine
from app.services.edge_status_monitor import EdgeStatusMonitor

router = APIRouter(prefix="/edges", tags=["Edge Discovery Engine"])


@router.get("/criteria-report")
def get_criteria_report(db: Session = Depends(get_db)):
    """
    Returns raw stability (CV), repeatability (subgroups), and robustness (max_drop_pct)
    metrics for edge blueprints with sample size >= 30, sorted by closeness to threshold bounds.
    """
    blueprints = db.query(EdgeBlueprint).filter(EdgeBlueprint.sample_size >= 30).all()
    
    report_list = []
    for bp in blueprints:
        stab_detail = bp.stability_detail or {}
        rep_detail = bp.repeatability_detail or {}
        rob_detail = bp.robustness_detail or {}

        cv_val = stab_detail.get("cv") or stab_detail.get("coefficient_of_variation") or 0.0
        pct_subgroups = rep_detail.get("pct_positive_subgroups", 0.0)
        max_drop = rob_detail.get("max_drop_pct", 0.0)

        borderline_score = abs(0.75 - float(cv_val)) + abs(50.0 - float(max_drop))

        report_list.append({
            "id": bp.id,
            "name": bp.name,
            "setup_combination": bp.setup_combination,
            "sample_size": bp.sample_size,
            "status": bp.status,
            "expectancy_r": float(bp.expectancy_r) if bp.expectancy_r else 0.0,
            "is_stable": bp.is_stable,
            "is_repeatable": bp.is_repeatable,
            "is_robust": bp.is_robust,
            "stability_cv": round(float(cv_val), 4),
            "stability_threshold": 0.75,
            "repeatability_valid_subgroups": rep_detail.get("valid_subgroups", 0),
            "repeatability_pct_positive": pct_subgroups,
            "robustness_max_drop_pct": round(float(max_drop), 2),
            "robustness_threshold_max_drop": 50.0,
            "borderline_score": round(borderline_score, 4),
            "evaluated_at": bp.criteria_evaluated_at.isoformat() if bp.criteria_evaluated_at else None
        })

    report_list.sort(key=lambda x: x["borderline_score"])
    
    return {
        "total_evaluated_edges": len(report_list),
        "thresholds": {
            "STABILITY_MAX_CV": 0.75,
            "REPEATABILITY_MIN_SUBGROUP_N": 5,
            "ROBUSTNESS_MAX_DROP_PCT": 50.0
        },
        "edges": report_list
    }


@router.get("/blueprints")
def get_edge_blueprints(
    status_filter: Optional[str] = Query(None, alias="status"),
    sort_by: Optional[str] = Query("expectancy", alias="sort_by"),
    db: Session = Depends(get_db)
):
    """
    Returns list of discovered edge blueprints from MySQL `edge_blueprints` table.
    """
    query = db.query(EdgeBlueprint)

    if status_filter and status_filter != "all":
        query = query.filter(EdgeBlueprint.status == status_filter)

    if sort_by == "sample_size":
        query = query.order_by(EdgeBlueprint.sample_size.desc())
    elif sort_by == "status":
        query = query.order_by(EdgeBlueprint.status.asc())
    else:
        query = query.order_by(EdgeBlueprint.expectancy_r.desc())

    blueprints = query.all()

    return [
        {
            "id": bp.id,
            "name": bp.name,
            "setup_combination": bp.setup_combination,
            "sample_size": bp.sample_size,
            "expectancy_r": float(bp.expectancy_r) if bp.expectancy_r is not None else 0.0,
            "ci_lower": float(bp.ci_lower) if bp.ci_lower is not None else 0.0,
            "ci_upper": float(bp.ci_upper) if bp.ci_upper is not None else 0.0,
            "win_rate_pct": float(bp.win_rate_pct) if bp.win_rate_pct is not None else 0.0,
            "win_rate_ci_lower": float(bp.win_rate_ci_lower) if bp.win_rate_ci_lower is not None else 0.0,
            "win_rate_ci_upper": float(bp.win_rate_ci_upper) if bp.win_rate_ci_upper is not None else 0.0,
            "p_value": float(bp.p_value) if bp.p_value is not None else 1.0,
            "fdr_adjusted_p_value": float(bp.fdr_adjusted_p_value) if bp.fdr_adjusted_p_value is not None else 1.0,
            "is_fdr_significant": bp.is_fdr_significant,
            "out_of_sample_expectancy_r": float(bp.out_of_sample_expectancy_r) if bp.out_of_sample_expectancy_r is not None else 0.0,
            "is_stable": bp.is_stable,
            "is_repeatable": bp.is_repeatable,
            "is_robust": bp.is_robust,
            "stability_detail": bp.stability_detail,
            "repeatability_detail": bp.repeatability_detail,
            "robustness_detail": bp.robustness_detail,
            "criteria_evaluated_at": bp.criteria_evaluated_at.isoformat() if bp.criteria_evaluated_at else None,
            "status": bp.status,
            "created_at": bp.created_at.isoformat() if bp.created_at else None,
            "updated_at": bp.updated_at.isoformat() if bp.updated_at else None,
        }
        for bp in blueprints
    ]


@router.get("/blueprints/{edge_id}")
def get_edge_blueprint_detail(
    edge_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns detailed statistics for a single edge blueprint, including contributing trades.
    """
    blueprint = db.query(EdgeBlueprint).filter(EdgeBlueprint.id == edge_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Edge blueprint tidak ditemukan.")

    tags = blueprint.setup_combination or []
    
    # Find contributing trades that match ALL tags in the setup combination
    contributing_trades = []
    if tags:
        # Build dynamic query to find trades containing all setup tags
        placeholders = ", ".join([f"'{tag}'" for tag in tags])
        tag_count = len(tags)

        sql = f"""
            SELECT t.id, t.pair, t.direction, t.entry_time, t.exit_time, t.pnl, t.rr_realized, t.data_source
            FROM trades t
            JOIN trade_setup_tags st ON t.id = st.trade_id
            JOIN setup_taxonomy_versions stv ON st.taxonomy_version_id = stv.id
            WHERE stv.tag_name IN ({placeholders})
              AND t.locked_at IS NOT NULL
            GROUP BY t.id
            HAVING COUNT(DISTINCT stv.tag_name) >= {tag_count}
            ORDER BY t.entry_time DESC
        """
        rows = db.execute(text(sql)).fetchall()

        for r in rows:
            contributing_trades.append({
                "id": r.id,
                "pair": r.pair,
                "direction": r.direction,
                "entry_time": r.entry_time.isoformat() if r.entry_time else None,
                "exit_time": r.exit_time.isoformat() if r.exit_time else None,
                "pnl": float(r.pnl) if r.pnl is not None else 0.0,
                "rr_realized": float(r.rr_realized) if r.rr_realized is not None else 0.0,
                "data_source": r.data_source
            })

    return {
        "id": blueprint.id,
        "name": blueprint.name,
        "setup_combination": blueprint.setup_combination,
        "sample_size": blueprint.sample_size,
        "expectancy_r": float(blueprint.expectancy_r) if blueprint.expectancy_r is not None else 0.0,
        "ci_lower": float(blueprint.ci_lower) if blueprint.ci_lower is not None else 0.0,
        "ci_upper": float(blueprint.ci_upper) if blueprint.ci_upper is not None else 0.0,
        "win_rate_pct": float(blueprint.win_rate_pct) if blueprint.win_rate_pct is not None else 0.0,
        "win_rate_ci_lower": float(blueprint.win_rate_ci_lower) if blueprint.win_rate_ci_lower is not None else 0.0,
        "win_rate_ci_upper": float(blueprint.win_rate_ci_upper) if blueprint.win_rate_ci_upper is not None else 0.0,
        "p_value": float(blueprint.p_value) if blueprint.p_value is not None else 1.0,
        "fdr_adjusted_p_value": float(blueprint.fdr_adjusted_p_value) if blueprint.fdr_adjusted_p_value is not None else 1.0,
        "is_fdr_significant": blueprint.is_fdr_significant,
        "out_of_sample_expectancy_r": float(blueprint.out_of_sample_expectancy_r) if blueprint.out_of_sample_expectancy_r is not None else 0.0,
        "is_stable": blueprint.is_stable,
        "is_repeatable": blueprint.is_repeatable,
        "is_robust": blueprint.is_robust,
        "stability_detail": blueprint.stability_detail,
        "repeatability_detail": blueprint.repeatability_detail,
        "robustness_detail": blueprint.robustness_detail,
        "criteria_evaluated_at": blueprint.criteria_evaluated_at.isoformat() if blueprint.criteria_evaluated_at else None,
        "status": blueprint.status,
        "created_at": blueprint.created_at.isoformat() if blueprint.created_at else None,
        "updated_at": blueprint.updated_at.isoformat() if blueprint.updated_at else None,
        "contributing_trades": contributing_trades
    }


@router.post("/discover")
def trigger_edge_discovery(db: Session = Depends(get_db)):
    """
    Triggers on-demand Edge Discovery process.
    Strict rule: ONLY evaluates live/manual locked trades (data_source != 'historical_import').
    """
    result = EdgeDiscoveryEngine.run_discovery(db)
    return result


@router.get("/status")
def get_edge_status_overview(db: Session = Depends(get_db)):
    """
    FITUR 13 - Returns current edge status overview, maturity breakdown, and health summary.
    """
    return EdgeStatusMonitor.get_status_overview(db)


@router.post("/monitor")
def trigger_edge_status_monitor(db: Session = Depends(get_db)):
    """
    FITUR 13 - Triggers on-demand Edge Validation & Status Monitor process.
    Evaluates 30-trade run-rate degradation and handles status transitions.
    """
    return EdgeStatusMonitor.evaluate_all_edge_statuses(db)

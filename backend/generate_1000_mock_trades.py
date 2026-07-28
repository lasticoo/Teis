import random
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import text
from app.database import SessionLocal
from app.models.models import Trade, TradeExecution, MarketContext, SetupTaxonomyVersion, TradeSetupTag, EdgeBlueprint
from app.services.edge_discovery_engine import EdgeDiscoveryEngine
from app.services.edge_status_monitor import EdgeStatusMonitor

db = SessionLocal()
print("🚀 Step 1: Generating 1,000 Realistic Multi-Tag Mock Trades...")

# Taxonomy setup
tags_def = [
    ("Order Block (H4)", "Setup"),
    ("FVG (H1)", "Setup"),
    ("Liquidity Sweep", "Trigger"),
    ("BOS (H1)", "Trigger"),
    ("CHOCH (M15)", "Trigger"),
    ("Fibonacci 0.618", "Confirmation"),
    ("Supply / Demand (H4)", "Setup"),
    ("Mitigation Block (H1)", "Setup"),
    ("Asia Liquidity Sweep", "Trigger"),
    ("Bull Trend (4H)", "Filter")
]

tax_map = {}
for tag_name, cat in tags_def:
    tax = db.query(SetupTaxonomyVersion).filter(SetupTaxonomyVersion.tag_name == tag_name).first()
    if not tax:
        tax = SetupTaxonomyVersion(tag_name=tag_name, tag_definition=f"Taxonomy tag {tag_name}", version_number=1, effective_from=datetime.now())
        db.add(tax)
        db.commit()
        db.refresh(tax)
    tax_map[tag_name] = tax.id

pairs_list = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "XRPUSDT", "RENDERUSDT", "SUIUSDT", "NEARUSDT", "TIAUSDT", "ENAUSDT"]
sessions_list = ["asia", "london", "new_york"]

start_base_date = datetime.now() - timedelta(days=365)

trades_to_create = []

# Cluster 1: 180 Trades [Order Block (H4), FVG (H1), Liquidity Sweep] -> 72% Win Rate (+2.5R win, -1.0R loss)
for i in range(180):
    t_time = start_base_date + timedelta(hours=i * 48) + timedelta(minutes=random.randint(0, 120))
    is_win = (i % 5 != 0 and i % 7 != 0)  # ~72% win
    r_val = 2.5 if is_win else -1.0
    pair_name = pairs_list[i % len(pairs_list)]
    sess_name = sessions_list[i % len(sessions_list)]
    trades_to_create.append({
        "pair": pair_name, "direction": "LONG" if i % 2 == 0 else "SHORT",
        "entry_price": 50000.0 if "BTC" in pair_name else 3000.0,
        "stop_loss": 49500.0, "take_profit": 51250.0,
        "rr_realized": r_val, "entry_time": t_time, "session": sess_name,
        "tags": ["Order Block (H4)", "FVG (H1)", "Liquidity Sweep"],
        "is_win": is_win
    })

# Cluster 2: 120 Trades [Supply / Demand (H4), CHOCH (M15), Asia Liquidity Sweep] -> 68% Win Rate (+2.0R win, -1.0R loss)
for i in range(120):
    t_time = start_base_date + timedelta(hours=i * 70) + timedelta(minutes=random.randint(0, 120))
    is_win = (i % 3 != 0)  # 66-68% win
    r_val = 2.0 if is_win else -1.0
    pair_name = pairs_list[(i + 3) % len(pairs_list)]
    sess_name = sessions_list[(i + 1) % len(sessions_list)]
    trades_to_create.append({
        "pair": pair_name, "direction": "SHORT" if i % 2 == 0 else "LONG",
        "entry_price": 3000.0, "stop_loss": 3050.0, "take_profit": 2900.0,
        "rr_realized": r_val, "entry_time": t_time, "session": sess_name,
        "tags": ["Supply / Demand (H4)", "CHOCH (M15)", "Asia Liquidity Sweep"],
        "is_win": is_win
    })

# Cluster 3: 45 Trades [BOS (H1), Bull Trend (4H)] -> 65% Win Rate (+2.0R win, -1.0R loss) -> (n=45 < 50 -> Validation)
for i in range(45):
    t_time = start_base_date + timedelta(hours=i * 180) + timedelta(minutes=random.randint(0, 120))
    is_win = (i % 3 != 0)  # 66% win
    r_val = 2.0 if is_win else -1.0
    pair_name = pairs_list[(i + 5) % len(pairs_list)]
    sess_name = sessions_list[i % len(sessions_list)]
    trades_to_create.append({
        "pair": pair_name, "direction": "LONG",
        "entry_price": 100.0, "stop_loss": 98.0, "take_profit": 104.0,
        "rr_realized": r_val, "entry_time": t_time, "session": sess_name,
        "tags": ["BOS (H1)", "Bull Trend (4H)"],
        "is_win": is_win
    })

# Cluster 4: 80 Trades [Mitigation Block (H1), Fibonacci 0.618] -> 40% Win Rate (+1.0R win, -1.2R loss) -> Research
for i in range(80):
    t_time = start_base_date + timedelta(hours=i * 100) + timedelta(minutes=random.randint(0, 120))
    is_win = (i % 5 == 0 or i % 7 == 0)  # ~40% win
    r_val = 1.0 if is_win else -1.2
    pair_name = pairs_list[(i + 2) % len(pairs_list)]
    sess_name = sessions_list[i % len(sessions_list)]
    trades_to_create.append({
        "pair": pair_name, "direction": "LONG",
        "entry_price": 50.0, "stop_loss": 48.0, "take_profit": 52.0,
        "rr_realized": r_val, "entry_time": t_time, "session": sess_name,
        "tags": ["Mitigation Block (H1)", "Fibonacci 0.618"],
        "is_win": is_win
    })

# Remaining 575 Trades: Random combinations across taxonomy tags with 50% win rate
tag_pool = ["Order Block (H4)", "FVG (H1)", "Liquidity Sweep", "BOS (H1)", "CHOCH (M15)", "Fibonacci 0.618", "Supply / Demand (H4)", "Asia Liquidity Sweep", "Bull Trend (4H)"]

for i in range(575):
    t_time = start_base_date + timedelta(hours=i * 15) + timedelta(minutes=random.randint(0, 180))
    is_win = (i % 2 == 0)
    r_val = 1.8 if is_win else -1.0
    pair_name = pairs_list[i % len(pairs_list)]
    sess_name = sessions_list[i % len(sessions_list)]
    # Pick 2-4 random tags
    k = random.randint(2, 4)
    selected_tags = random.sample(tag_pool, k)
    trades_to_create.append({
        "pair": pair_name, "direction": "LONG" if i % 2 == 0 else "SHORT",
        "entry_price": 100.0, "stop_loss": 95.0, "take_profit": 109.0,
        "rr_realized": r_val, "entry_time": t_time, "session": sess_name,
        "tags": selected_tags,
        "is_win": is_win
    })

# Batch insert into DB
print(f"📦 Total synthetic trades generated: {len(trades_to_create)}. Writing to database...")

inserted_count = 0
for data in trades_to_create:
    exit_t = data["entry_time"] + timedelta(hours=random.randint(1, 6))
    r_val = data["rr_realized"]
    pnl_val = r_val * 15.0
    
    tr = Trade(
        pair=data["pair"],
        direction=data["direction"],
        entry_price=Decimal(str(data["entry_price"])),
        stop_loss=Decimal(str(data["stop_loss"])),
        take_profit=Decimal(str(data["take_profit"])),
        margin=Decimal("50.0"),
        leverage=10,
        pnl=Decimal(str(pnl_val)),
        rr_realized=Decimal(str(r_val)),
        fee=Decimal("0.05"),
        entry_time=data["entry_time"],
        exit_time=exit_t,
        data_source="manual",
        locked_at=exit_t
    )
    db.add(tr)
    db.flush()
    
    # Attach Tags
    for tag_name in data["tags"]:
        db.add(TradeSetupTag(trade_id=tr.id, taxonomy_version_id=tax_map[tag_name]))
        
    # Execution
    exit_r = "take_profit" if data["is_win"] else "stop_loss"
    db.add(TradeExecution(trade_id=tr.id, order_type="limit", exit_reason=exit_r))
    
    # Market Context
    db.add(MarketContext(trade_id=tr.id, session=data["session"], captured_at=data["entry_time"]))
    
    inserted_count += 1
    if inserted_count % 200 == 0:
        db.commit()
        print(f"  • Inserted {inserted_count} / {len(trades_to_create)} trades...")

db.commit()
print("✅ 1,000 Mock Trades successfully inserted into database!")

# Step 2: Execute Edge Discovery Engine
print("\n⚡ Step 2: Running Edge Discovery Engine on 1,000 Mock Trades...")
disc_res = EdgeDiscoveryEngine.run_discovery(db)
print(f"Discovery Result Status: {disc_res.get('status')}, Edges Discovered: {disc_res.get('edges_discovered')}")

# Step 3: Run Edge Status Monitor
print("\n🔍 Step 3: Evaluating Edge Status Monitor...")
mon_res = EdgeStatusMonitor.evaluate_all_edge_statuses(db)

blueprints = db.query(EdgeBlueprint).order_by(EdgeBlueprint.sample_size.desc()).all()
print(f"\n📊 === DITEMUKAN {len(blueprints)} CETAK BIRU EDGE DISCOVERY DARI 1,000 MOCK TRADES ===")

summary_status = {}
for bp in blueprints:
    summary_status[bp.status] = summary_status.get(bp.status, 0) + 1

print("Distribution Status Edge Blueprints:")
for st, count in summary_status.items():
    print(f"  • {st.upper()}: {count} Edges")

print("\n--- TOP 10 EDGE BLUEPRINTS TERATAS ---")
for idx, bp in enumerate(blueprints[:10], start=1):
    print(f"\n#{idx} Edge Name: {bp.name}")
    print(f"   Combo Tags: {bp.setup_combination}")
    print(f"   Sample (n): {bp.sample_size} | Expectancy: {float(bp.expectancy_r):.2f}R | Win Rate: {float(bp.win_rate_pct):.1f}%")
    print(f"   Fitur 16 Criteria -> Stable: {bp.is_stable}, Repeatable: {bp.is_repeatable}, Robust: {bp.is_robust}")
    print(f"   🏆 STATUS AKHIR: {bp.status.upper()}")

db.close()
print("\n📌 SANGAT SESUAI! Seluruh 1,000 data mock trade dan Edge Blueprint TETAP DIPERTAHANKAN di Database agar dapat Anda jelajahi di UI (http://localhost:5173/edges).")

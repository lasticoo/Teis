import json
import logging
import uuid
import boto3
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from botocore.client import Config
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, IntegrityError

from app.database import get_db
from app.api.deps import get_current_user
from app.config import settings
from app.models.models import (
    Trade, 
    Psychology, 
    TradeSetupTag, 
    TradeExecution, 
    TradeCorrection,
    Screenshot, 
    SetupTaxonomyVersion,
    MarketContext
)
from app.tasks.worker import lock_trade, collect_market_context

logger = logging.getLogger(__name__)
router = APIRouter(tags=["journal"])


@router.get("/journal/trade/{trade_id}/context")
def get_trade_market_context(
    trade_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Mengambil data market context untuk satu trade."""
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade tidak ditemukan.")

    ctx_list = trade.market_context
    ctx = ctx_list[0] if ctx_list else None

    if not ctx:
        return {}

    return {
        "trade_id": trade_id,
        "trend_htf":        ctx.trend_htf,
        "trend_ltf":        ctx.trend_ltf,
        "atr":              str(ctx.atr) if ctx.atr else None,
        "volume_24h":       str(ctx.volume_24h) if ctx.volume_24h else None,
        "open_interest":    str(ctx.open_interest) if ctx.open_interest else None,
        "funding_rate":     str(ctx.funding_rate) if ctx.funding_rate else None,
        "btc_dominance":    str(ctx.btc_dominance) if ctx.btc_dominance else None,
        "fear_greed_index": ctx.fear_greed_index,
        "session":          ctx.session,
        "captured_at":      ctx.captured_at.isoformat() if ctx.captured_at else None,
    }

def get_minio_client():
    endpoint_url = f"http://{settings.MINIO_ENDPOINT}"
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    return s3

def seed_taxonomy_if_empty(db: Session):
    setups = [
        # H4 Timeframe Context & Setups
        ("H4 Bullish", "Struktur/Tren Timeframe 4 Jam cenderung Naik."),
        ("H4 Bearish", "Struktur/Tren Timeframe 4 Jam cenderung Turun."),
        ("OB BULLISH (H4)", "Order Block Bullish pada timeframe H4 (4 Jam)."),
        ("OB BEARISH (H4)", "Order Block Bearish pada timeframe H4 (4 Jam)."),
        ("POI (H4)", "Point of Interest (Liquidity Sweep + Order Block) pada timeframe H4."),
        ("Liquidity Sweep (H4)", "Penyapuan likuiditas pada timeframe H4."),
        ("Order Block (H4)", "Order Block pada timeframe H4."),
        ("FVG (H4)", "Fair Value Gap / Imbalance pada timeframe H4."),
        ("CHOCH (H4)", "Change of Character pada timeframe H4."),
        ("BOS (H4)", "Break of Structure pada timeframe H4."),
        ("Equal High / Low (H4)", "Equal High / Equal Low pada timeframe H4."),
        ("Supply / Demand (H4)", "Zona Supply / Demand pada timeframe H4."),
        ("Breaker Block (H4)", "Breaker Block pada timeframe H4."),
        ("Mitigation Block (H4)", "Mitigation Block pada timeframe H4."),

        # H1 Timeframe Context & Setups
        ("H1 Bullish", "Struktur/Tren Timeframe 1 Jam cenderung Naik."),
        ("H1 Bearish", "Struktur/Tren Timeframe 1 Jam cenderung Turun."),
        ("OB BULLISH (H1)", "Order Block Bullish pada timeframe H1 (1 Jam)."),
        ("OB BEARISH (H1)", "Order Block Bearish pada timeframe H1 (1 Jam)."),
        ("POI (H1)", "Point of Interest (Liquidity Sweep + Order Block) pada timeframe H1."),
        ("Liquidity Sweep (H1)", "Penyapuan likuiditas pada timeframe H1."),
        ("Order Block (H1)", "Order Block pada timeframe H1."),
        ("FVG (H1)", "Fair Value Gap / Imbalance pada timeframe H1."),
        ("CHOCH (H1)", "Change of Character pada timeframe H1."),
        ("BOS (H1)", "Break of Structure pada timeframe H1."),
        ("Equal High / Low (H1)", "Equal High / Equal Low pada timeframe H1."),
        ("Supply / Demand (H1)", "Zona Supply / Demand pada timeframe H1."),
        ("Breaker Block (H1)", "Breaker Block pada timeframe H1."),
        ("Mitigation Block (H1)", "Mitigation Block pada timeframe H1."),

        # Fibonacci Confirmations
        ("FIBONACCI 0.382", "Retracement Fibonacci level 38.2%."),
        ("FIBONACCI 0.618", "Golden Ratio Retracement Fibonacci level 61.8%."),
        ("FIBONACCI 0.786", "Deep Retracement Fibonacci level 78.6%."),

        # Macro & Session Context
        ("Premium / Discount Array", "Penetapan harga di area mahal (premium) atau murah (discount)."),
        ("SMT Divergence", "Divergensi korelasi antar instrumen terkait (misal BTC vs ETH)."),
        ("Session High / Low Sweep", "Penyapuan harga tertinggi/terendah dari sesi Asia, London, atau New York."),

        # Legacy / Generic Setups
        ("Liquidity Sweep", "Mengambil likuiditas di atas/bawah key level sebelum pembalikan arah."),
        ("Order Block", "Area konsolidasi sebelum ekspansi harga yang kuat."),
        ("FVG (Fair Value Gap)", "Ketidakseimbangan harga / Imbalance antara candle 1 dan candle 3."),
        ("CHOCH (Change of Character)", "Indikasi awal perubahan karakter / struktur trend."),
        ("BOS (Break of Structure)", "Konfirmasi kelanjutan trend setelah menembus swing high/low sebelumnya."),
        ("Equal High / Low (EQH/EQL)", "Level high/low rata yang berpotensi menarik likuiditas."),
        ("Supply / Demand Zone", "Zona penawaran/permintaan kuat yang memicu dorongan harga signifikan."),
        ("Breaker Block", "Order block yang tertembus dan berganti fungsi menjadi support/resistance baru."),
        ("Mitigation Block", "Area retracement untuk mengurangi posisi sebelum pergerakan berlanjut."),
        ("OB BULLISH", "Order Block Bullish."),
        ("OB BEARISH", "Order Block Bearish."),
        ("POI (Liquidity Sweep + Order Block)", "Point of Interest gabungan.")
    ]
    existing = {t.tag_name for t in db.query(SetupTaxonomyVersion).all()}
    added = False
    for name, desc in setups:
        if name not in existing:
            tax = SetupTaxonomyVersion(
                version_number=1,
                tag_name=name,
                tag_definition=desc,
                effective_from=datetime.now()
            )
            db.add(tax)
            added = True
    if added:
        db.commit()

@router.get("/journal/pending")
def get_pending_trades(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    # Seed setup options if empty
    seed_taxonomy_if_empty(db)
    
    # Retrieve ALL active trades (tidak ada exit_time) — termasuk yang sudah terkunci (locked)
    # agar trader tetap bisa melihat kartu Market Context dari trade yang sedang berjalan
    trades = db.query(Trade).filter(Trade.exit_time == None).order_by(Trade.entry_time.desc()).all()
    taxonomy = db.query(SetupTaxonomyVersion).all()
    
    results = []
    for t in trades:
        # Hitung sisa waktu koreksi jika sudah pernah di-tag
        seconds_left = None
        is_locked = t.locked_at is not None
        
        if t.psychology and not is_locked:
            elapsed = (datetime.now() - t.created_at).total_seconds()
            seconds_left = max(0.0, 120.0 - elapsed)
        elif is_locked:
            seconds_left = 0  # Terkunci permanen

        results.append({
            "id": t.id,
            "pair": t.pair,
            "direction": t.direction,
            "entry_price": float(t.entry_price),
            "leverage": float(t.leverage) if t.leverage is not None else None,
            "entry_time": t.entry_time.isoformat(),
            "is_tagged": t.psychology is not None,
            "is_locked": is_locked,
            "seconds_left": seconds_left,
            "psychology": {
                "confidence_level": t.psychology.confidence_level,
                "psychological_tags": t.psychology.psychological_tags,
                "plan_adherence": t.psychology.plan_adherence,
                "free_notes": t.psychology.free_notes,
            } if t.psychology else None,
            "order_type": t.execution.order_type if t.execution else None,
            "setups": [tag.taxonomy_version_id for tag in t.setup_tags] if t.setup_tags else [],
            "screenshot_url": (t.screenshots[0].file_path.replace("minio:9000", "localhost:9000") if t.screenshots and t.screenshots[0].file_path else None)
        })
        
    return {
        "trades": results,
        "taxonomy": [
            {
                "id": tax.id,
                "tag_name": tax.tag_name,
                "tag_definition": tax.tag_definition
            } for tax in taxonomy
        ]
    }


@router.get("/journal/list")
def get_journal_list(
    data_source: Optional[str] = "all",
    pair: Optional[str] = None,
    status_filter: Optional[str] = "all",
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Returns the complete list of journaled trades with filters for source (Live/Import/Manual),
    pair, and open/closed status. Includes linked fills, PnL, RR, and market context.
    """
    query = db.query(Trade)

    if data_source and data_source != "all":
        query = query.filter(Trade.data_source == data_source)

    if pair:
        query = query.filter(Trade.pair == pair.upper())

    if status_filter == "open":
        query = query.filter(Trade.exit_time == None)
    elif status_filter == "closed":
        query = query.filter(Trade.exit_time != None)

    trades = query.order_by(Trade.entry_time.desc()).all()

    badge_map = {
        "binance_sync": "Live",
        "historical_import": "Import",
        "manual": "Manual"
    }

    results = []
    for t in trades:
        # Format linked fills
        linked_fills = []
        for tf in t.fills:
            ef = tf.exchange_fill
            if ef:
                linked_fills.append({
                    "id": ef.id,
                    "binance_trade_id": ef.binance_trade_id,
                    "role": tf.role,
                    "side": ef.side,
                    "price": float(ef.price),
                    "qty": float(ef.qty),
                    "fee": float(ef.fee),
                    "executed_at": ef.executed_at.isoformat() if ef.executed_at else None
                })

        # Format setups
        setup_names = [tag.taxonomy_version.tag_name for tag in t.setup_tags if tag.taxonomy_version]

        # Format context
        ctx = t.market_context[0] if t.market_context else None
        ctx_data = {
            "trend_htf": ctx.trend_htf,
            "trend_ltf": ctx.trend_ltf,
            "atr": str(ctx.atr) if ctx and ctx.atr else None,
            "volume_24h": str(ctx.volume_24h) if ctx and ctx.volume_24h else None,
            "open_interest": str(ctx.open_interest) if ctx and ctx.open_interest else None,
            "funding_rate": str(ctx.funding_rate) if ctx and ctx.funding_rate else None,
            "btc_dominance": str(ctx.btc_dominance) if ctx and ctx.btc_dominance else None,
            "fear_greed_index": ctx.fear_greed_index if ctx else None,
            "session": ctx.session if ctx else None
        } if ctx else None

        results.append({
            "id": t.id,
            "pair": t.pair,
            "direction": t.direction,
            "entry_price": float(t.entry_price),
            "exit_price": float(t.exit_price) if t.exit_price is not None else None,
            "stop_loss": float(t.stop_loss) if t.stop_loss is not None else None,
            "take_profit": float(t.take_profit) if t.take_profit is not None else None,
            "margin": float(t.margin) if t.margin is not None else None,
            "leverage": float(t.leverage) if t.leverage is not None else None,
            "risk_amount": float(t.risk_amount) if t.risk_amount is not None else None,
            "rr_planned": float(t.rr_planned) if t.rr_planned is not None else None,
            "rr_realized": float(t.rr_realized) if t.rr_realized is not None else None,
            "pnl": float(t.pnl) if t.pnl is not None else None,
            "fee": float(t.fee) if t.fee is not None else None,
            "entry_time": t.entry_time.isoformat(),
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "holding_time_sec": t.holding_time_sec,
            "data_source": t.data_source,
            "source_badge": badge_map.get(t.data_source, "Live"),
            "status": "Closed" if t.exit_time else "Open",
            "is_locked": t.locked_at is not None,
            "is_tagged": t.psychology is not None,
            "setups": setup_names,
            "psychology": {
                "confidence_level": t.psychology.confidence_level,
                "psychological_tags": t.psychology.psychological_tags,
                "plan_adherence": t.psychology.plan_adherence,
                "free_notes": t.psychology.free_notes,
            } if t.psychology else None,
            "screenshot_url": (t.screenshots[0].file_path.replace("minio:9000", "localhost:9000") if t.screenshots and t.screenshots[0].file_path else None),
            "fills": linked_fills,
            "market_context": ctx_data
        })

    return {"trades": results, "total": len(results)}


@router.post("/journal/tag")
async def tag_trade(
    trade_id: str = Form(...),
    setup: str = Form(...),  # JSON string of list of UUIDs (setup taxonomy ids)
    bias_arah_manual: str = Form(...), # bull_trend, bear_trend, range
    session: str = Form(...), # asia, london, new_york
    confidence_level: int = Form(...),
    psychological_tags: str = Form(...),  # JSON string of list of strings
    plan_adherence: bool = Form(...),
    free_notes: str = Form(None),
    order_type: str = Form(...), # limit, market
    screenshot_before_entry: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # 1. Validate Trade exists
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade not found."
        )
        
    # 2. Check if locked
    if trade.locked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trade is locked and cannot be updated."
        )
        
    # 3. Parse JSON structures
    try:
        setup_ids = json.loads(setup)
        if not isinstance(setup_ids, list):
            raise ValueError()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid setup field. Expected a JSON list of taxonomy UUIDs."
        )
        
    try:
        psych_tags = json.loads(psychological_tags)
        if not isinstance(psych_tags, list):
            raise ValueError()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid psychological_tags field. Expected a JSON list of strings."
        )
        
    # Validate confidence level range
    if not (1 <= confidence_level <= 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confidence_level must be between 1 and 10."
        )
        
    # Validate Enum values
    if bias_arah_manual not in ['bull_trend', 'bear_trend', 'range']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bias_arah_manual. Expected bull_trend, bear_trend, or range."
        )
        
    if session not in ['asia', 'london', 'new_york']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session. Expected asia, london, or new_york."
        )
        
    if order_type not in ['limit', 'market']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid order_type. Expected limit or market."
        )
        
    # Check if this is the first save or an edit
    is_first_save = trade.psychology is None
    
    # 4. Handle Screenshot Upload
    screenshot_url = None
    if screenshot_before_entry:
        # Validate size (< 5MB)
        content_size = 0
        # Read a chunk to check size
        chunk = await screenshot_before_entry.read(1024 * 1024 * 6) # read up to 6MB
        content_size = len(chunk)
        # Reset file cursor for upload
        await screenshot_before_entry.seek(0)
        
        if content_size > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Screenshot file size exceeds 5MB limit."
            )
            
        # Validate type
        content_type = screenshot_before_entry.content_type
        if content_type not in ["image/png", "image/jpeg", "image/jpg"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Screenshot file must be a PNG, JPG, or JPEG image."
            )
            
        # Upload to MinIO
        try:
            s3 = get_minio_client()
            ext = screenshot_before_entry.filename.split(".")[-1]
            file_name = f"{uuid.uuid4()}.{ext}"
            
            s3.upload_fileobj(
                screenshot_before_entry.file,
                settings.MINIO_BUCKET_NAME,
                file_name,
                ExtraArgs={"ContentType": content_type}
            )
            # Save S3 URL (accessible publicly from host browser)
            screenshot_url = f"http://localhost:9000/{settings.MINIO_BUCKET_NAME}/{file_name}"
        except Exception as e:
            logger.error(f"Failed to upload screenshot to MinIO: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload screenshot to object storage: {str(e)}"
            )

    # 5. Save/Update Psychology
    psych = trade.psychology
    if not psych:
        psych = Psychology(
            trade_id=trade_id,
            confidence_level=confidence_level,
            psychological_tags=psych_tags,
            plan_adherence=plan_adherence,
            free_notes=free_notes
        )
        db.add(psych)
    else:
        psych.confidence_level = confidence_level
        psych.psychological_tags = psych_tags
        psych.plan_adherence = plan_adherence
        psych.free_notes = free_notes
        
    # 6. Save/Update Trade Execution (order_type)
    exec_rec = trade.execution
    if not exec_rec:
        exec_rec = TradeExecution(
            trade_id=trade_id,
            order_type=order_type,
            moved_to_breakeven=False,
            trailing_stop_used=False
        )
        db.add(exec_rec)
    else:
        exec_rec.order_type = order_type
        
    # 7. Update/Create Setup Tags
    # Clear existing tags
    db.query(TradeSetupTag).filter(TradeSetupTag.trade_id == trade_id).delete()
    for setup_id in setup_ids:
        # Validate that the setup ID is valid in taxonomy
        tax = db.query(SetupTaxonomyVersion).filter(SetupTaxonomyVersion.id == setup_id).first()
        if not tax:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Setup taxonomy ID {setup_id} is invalid."
            )
        db.add(TradeSetupTag(trade_id=trade_id, taxonomy_version_id=setup_id))
        
    # 8. Save Screenshot record
    if screenshot_url:
        # Check if a screenshot already exists for this stage
        sc = db.query(Screenshot).filter(Screenshot.trade_id == trade_id, Screenshot.stage == 'before_entry').first()
        if not sc:
            sc = Screenshot(
                trade_id=trade_id,
                stage='before_entry',
                file_path=screenshot_url,
                uploaded_at=datetime.now()
            )
            db.add(sc)
        else:
            sc.file_path = screenshot_url
            sc.uploaded_at = datetime.now()
            
    # 9. Update/Save Market Context (bias_arah_manual and session)
    ctx = trade.market_context
    if not ctx:
        # Create a new market context record
        from app.models.models import MarketContext
        new_ctx = MarketContext(
            trade_id=trade_id,
            bias_arah_manual=bias_arah_manual,
            session=session,
            captured_at=datetime.now()
        )
        db.add(new_ctx)
    else:
        # If there are already records in the list, update the first one
        ctx[0].bias_arah_manual = bias_arah_manual
        ctx[0].session = session
        
    db.commit()
    
    # 10. Schedule lock task in Celery and collect market context (only if this is the first save)
    if is_first_save:
        lock_trade.apply_async(args=[trade_id], countdown=120)
        collect_market_context.delay(trade_id)
        logger.info(f"Scheduled lock_trade and collect_market_context Celery tasks for trade {trade_id}.")
        
    return {"status": "success", "message": "Trade tagged successfully."}


class CorrectionRequest(BaseModel):
    original_trade_id: str
    field_name: str
    old_value: Optional[str] = None
    new_value: str
    reason: str


@router.post("/journal/correct")
def submit_trade_correction(
    request: CorrectionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Submits a formal trade correction record into trade_corrections audit log table.
    Enforces minimum 10 characters for correction reason.
    Handles SQL trigger exceptions gracefully (HTTP 409 Conflict).
    """
    # 1. Validate trade existence
    trade = db.query(Trade).filter(Trade.id == request.original_trade_id).first()
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade dengan ID {request.original_trade_id} tidak ditemukan."
        )

    # 2. Validate reason length (minimum 10 characters)
    reason_clean = (request.reason or "").strip()
    if len(reason_clean) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alasan koreksi (reason) wajib diisi minimal 10 karakter."
        )

    # 3. Validate allowed field names
    allowed_fields = [
        "confidence_level",
        "plan_adherence",
        "psychological_tags",
        "bias_arah_manual",
        "session",
        "free_notes",
        "setup_tags",
        "order_type",
        "moved_to_breakeven",
        "trailing_stop_used",
        "entry_price",
        "stop_loss",
        "take_profit",
        "exit_reason"
    ]
    if request.field_name not in allowed_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Field '{request.field_name}' tidak terdaftar dalam taksonomi koreksi yang diizinkan."
        )

    # 4. Insert into trade_corrections table and update active trade data
    try:
        corr = TradeCorrection(
            original_trade_id=request.original_trade_id,
            field_name=request.field_name,
            old_value=request.old_value,
            new_value=request.new_value,
            reason=reason_clean,
            corrected_at=datetime.now()
        )
        db.add(corr)
        db.flush()

        # Temporarily clear locked_at via raw SQL to permit official correction
        original_locked_at = trade.locked_at
        if original_locked_at:
            db.execute(text("UPDATE trades SET locked_at = NULL WHERE id = :tid"), {"tid": trade.id})
            db.flush()

        # Update target model field
        field = request.field_name
        val = request.new_value.strip()

        if field == "confidence_level":
            psy = trade.psychology
            if psy:
                psy.confidence_level = int(val)
        elif field == "plan_adherence":
            psy = trade.psychology
            if psy:
                psy.plan_adherence = (val.lower() in ["true", "ya", "1", "yes", "patuh"])
        elif field == "free_notes":
            psy = trade.psychology
            if psy:
                psy.free_notes = val
        elif field == "psychological_tags":
            psy = trade.psychology
            if psy:
                tags = [t.strip() for t in val.split(",") if t.strip()]
                psy.psychological_tags = tags
        elif field == "order_type":
            ex = trade.execution
            if ex:
                ex.order_type = val.lower()
        elif field == "moved_to_breakeven":
            ex = trade.execution
            if ex:
                ex.moved_to_breakeven = (val.lower() in ["true", "ya", "1", "yes"])
        elif field == "trailing_stop_used":
            ex = trade.execution
            if ex:
                ex.trailing_stop_used = (val.lower() in ["true", "ya", "1", "yes"])
        elif field == "exit_reason":
            ex = trade.execution
            if ex:
                ex.exit_reason = val
        elif field == "bias_arah_manual":
            if trade.market_context:
                trade.market_context[0].bias_arah_manual = val
        elif field == "session":
            if trade.market_context:
                trade.market_context[0].session = val
        elif field == "stop_loss":
            trade.stop_loss = Decimal(val)
        elif field == "take_profit":
            trade.take_profit = Decimal(val)
        elif field == "entry_price":
            trade.entry_price = Decimal(val)

        db.flush()

        # Restore original locked_at
        if original_locked_at:
            db.execute(
                text("UPDATE trades SET locked_at = :lock_val WHERE id = :tid"),
                {"lock_val": original_locked_at, "tid": trade.id}
            )

        db.commit()
        db.refresh(corr)
        logger.info(f"Berhasil mencatat audit koreksi dan memperbarui data trade {trade.id} pada field {request.field_name}.")
        return {
            "status": "success",
            "message": "Koreksi data trade berhasil dicatat dan diterapkan pada data aktif.",
            "correction": {
                "id": corr.id,
                "original_trade_id": corr.original_trade_id,
                "field_name": corr.field_name,
                "old_value": corr.old_value,
                "new_value": corr.new_value,
                "reason": corr.reason,
                "corrected_at": corr.corrected_at.isoformat()
            }
        }
    except (OperationalError, IntegrityError) as e:
        db.rollback()
        err_str = str(e)
        if "Trade sudah terkunci" in err_str or "45000" in err_str:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Trade sudah terkunci oleh sistem. Modifikasi langsung dilarang, namun audit log koreksi telah diproses."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gagal mencatat koreksi: {err_str}"
        )


@router.get("/journal/detail/{trade_id}")
def get_trade_detail(
    trade_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Returns full comprehensive details for a single trade record.
    Includes fills, psychology tags, market context, setups, screenshots, execution params, and audit corrections.
    """
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade with ID {trade_id} not found."
        )

    def sanitize_url(raw_url: Optional[str]) -> Optional[str]:
        if not raw_url:
            return None
        return raw_url.replace("http://minio:9000", "http://localhost:9000")

    linked_fills = []
    for tf in trade.fills:
        ef = tf.exchange_fill
        if ef:
            linked_fills.append({
                "id": ef.id,
                "binance_trade_id": ef.binance_trade_id,
                "binance_order_id": ef.binance_order_id,
                "role": tf.role,
                "side": ef.side,
                "price": float(ef.price),
                "qty": float(ef.qty),
                "fee": float(ef.fee),
                "executed_at": ef.executed_at.isoformat() if ef.executed_at else None
            })

    setup_names = [tag.taxonomy_version.tag_name for tag in trade.setup_tags if tag.taxonomy_version]

    psy = trade.psychology
    psy_data = {
        "confidence_level": psy.confidence_level,
        "psychological_tags": psy.psychological_tags if isinstance(psy.psychological_tags, list) else json.loads(psy.psychological_tags or "[]"),
        "plan_adherence": psy.plan_adherence,
        "free_notes": psy.free_notes
    } if psy else None

    exec_rec = trade.execution
    exec_data = {
        "order_type": exec_rec.order_type if exec_rec else "market",
        "moved_to_breakeven": exec_rec.moved_to_breakeven if exec_rec else False,
        "trailing_stop_used": exec_rec.trailing_stop_used if exec_rec else False,
        "exit_reason": exec_rec.exit_reason if exec_rec else None
    } if exec_rec else None

    corrections_data = [
        {
            "id": c.id,
            "field_name": c.field_name,
            "old_value": c.old_value,
            "new_value": c.new_value,
            "reason": c.reason,
            "corrected_at": c.corrected_at.isoformat() if c.corrected_at else None
        }
        for c in trade.corrections
    ]

    screenshots_data = [
        {
            "id": sc.id,
            "stage": sc.stage,
            "url": sanitize_url(sc.file_path),
            "uploaded_at": sc.uploaded_at.isoformat() if sc.uploaded_at else None
        }
        for sc in trade.screenshots
    ]

    ctx = trade.market_context[0] if trade.market_context else None
    ctx_data = {
        "trend_htf": ctx.trend_htf,
        "trend_ltf": ctx.trend_ltf,
        "bias_arah_manual": ctx.bias_arah_manual,
        "atr": str(ctx.atr) if ctx and ctx.atr else None,
        "volume_24h": str(ctx.volume_24h) if ctx and ctx.volume_24h else None,
        "open_interest": str(ctx.open_interest) if ctx and ctx.open_interest else None,
        "funding_rate": str(ctx.funding_rate) if ctx and ctx.funding_rate else None,
        "btc_dominance": str(ctx.btc_dominance) if ctx and ctx.btc_dominance else None,
        "fear_greed_index": ctx.fear_greed_index if ctx else None,
        "session": ctx.session if ctx else None
    } if ctx else None

    badge_map = {
        "binance_sync": "Live",
        "historical_import": "Import",
        "manual": "Manual"
    }

    return {
        "id": trade.id,
        "pair": trade.pair,
        "direction": trade.direction,
        "entry_price": float(trade.entry_price),
        "exit_price": float(trade.exit_price) if trade.exit_price else None,
        "pnl": float(trade.pnl) if trade.pnl is not None else None,
        "fee": float(trade.fee) if trade.fee is not None else None,
        "risk_amount": float(trade.risk_amount) if trade.risk_amount else 10.0,
        "rr_planned": float(trade.rr_planned) if trade.rr_planned else None,
        "rr_realized": float(trade.rr_realized) if trade.rr_realized is not None else None,
        "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
        "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
        "holding_time_sec": trade.holding_time_sec,
        "status": "Closed" if trade.exit_time else "Open",
        "data_source": trade.data_source,
        "source_badge": badge_map.get(trade.data_source, "Live"),
        "is_locked": trade.locked_at is not None,
        "locked_at": trade.locked_at.isoformat() if trade.locked_at else None,
        "setups": setup_names,
        "fills": linked_fills,
        "psychology": psy_data,
        "execution": exec_data,
        "corrections": corrections_data,
        "screenshots": screenshots_data,
        "market_context": ctx_data
    }

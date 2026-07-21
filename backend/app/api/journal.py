import json
import logging
import uuid
import boto3
from datetime import datetime
from decimal import Decimal
from typing import List
from botocore.client import Config
from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.config import settings
from app.models.models import (
    Trade, 
    Psychology, 
    TradeSetupTag, 
    TradeExecution, 
    Screenshot, 
    SetupTaxonomyVersion
)
from app.tasks.worker import lock_trade

logger = logging.getLogger(__name__)
router = APIRouter(tags=["journal"])

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
    count = db.query(SetupTaxonomyVersion).count()
    if count == 0:
        setups = [
            ("Liquidity Sweep", "Mengambil likuiditas di atas/bawah key level sebelum pembalikan arah."),
            ("Order Block", "Area konsolidasi sebelum ekspansi harga yang kuat."),
            ("FVG", "Fair Value Gap / Ketidakseimbangan harga (imbalance)."),
            ("CHOCH", "Change of Character / Indikasi awal perubahan trend."),
            ("Equal High", "Level resistance rata yang berpotensi menyapu likuiditas.")
        ]
        for name, desc in setups:
            tax = SetupTaxonomyVersion(
                version_number=1,
                tag_name=name,
                tag_definition=desc,
                effective_from=datetime.now()
            )
            db.add(tax)
        db.commit()

@router.get("/journal/pending")
def get_pending_trades(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    # Seed setup options if empty
    seed_taxonomy_if_empty(db)
    
    # Retrieve trades where locked_at is NULL
    trades = db.query(Trade).filter(Trade.locked_at == None).order_by(Trade.entry_time.desc()).all()
    taxonomy = db.query(SetupTaxonomyVersion).all()
    
    results = []
    for t in trades:
        # Calculate seconds elapsed if already tagged
        seconds_left = None
        if t.psychology:
            # Correction window starts from the first save (which is created_at)
            # Find the time elapsed
            elapsed = (datetime.now() - t.created_at).total_seconds()
            seconds_left = max(0.0, 120.0 - elapsed)
            
        results.append({
            "id": t.id,
            "pair": t.pair,
            "direction": t.direction,
            "entry_price": float(t.entry_price),
            "leverage": float(t.leverage) if t.leverage is not None else None,
            "entry_time": t.entry_time.isoformat(),
            "is_tagged": t.psychology is not None,
            "seconds_left": seconds_left,
            "psychology": {
                "confidence_level": t.psychology.confidence_level,
                "psychological_tags": t.psychology.psychological_tags,
                "plan_adherence": t.psychology.plan_adherence,
                "free_notes": t.psychology.free_notes,
            } if t.psychology else None,
            "order_type": t.execution.order_type if t.execution else None,
            "setups": [tag.taxonomy_version_id for tag in t.setup_tags] if t.setup_tags else [],
            "screenshot_url": t.screenshots[0].file_path if t.screenshots else None
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
            # Save S3 URL
            screenshot_url = f"http://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET_NAME}/{file_name}"
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
    
    # 10. Schedule lock task in Celery (only if this is the first save)
    if is_first_save:
        lock_trade.apply_async(args=[trade_id], countdown=120)
        logger.info(f"Scheduled lock_trade Celery task for trade {trade_id} with 120s countdown.")
        
    return {"status": "success", "message": "Trade tagged successfully."}

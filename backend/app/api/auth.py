from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.auth import (
    LoginRequest, LoginResponse, Verify2FARequest, TokenResponse,
    BinanceKeyRequest, BinanceKeyStatusResponse
)
from app.models.models import User, APICredential
from app.services.auth import (
    verify_password, verify_totp, create_access_token
)
from app.services.crypto import cipher
from app.api.deps import get_current_user, get_current_user_pending_2fa

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings_router = APIRouter(prefix="/settings", tags=["Settings"])

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah."
        )
    
    # Check if user has TOTP enabled
    if user.totp_secret:
        # Generate temporary token with pending_2fa=True
        temp_token = create_access_token(data={"sub": user.username, "pending_2fa": True})
        return LoginResponse(session_token=temp_token, require_2fa=True)
    else:
        # Generate final token directly if 2FA is not set up
        access_token = create_access_token(data={"sub": user.username, "pending_2fa": False})
        return LoginResponse(session_token=access_token, require_2fa=False)

@router.post("/verify-2fa", response_model=TokenResponse)
def verify_2fa(
    request: Verify2FARequest,
    current_user: User = Depends(get_current_user_pending_2fa)
):
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA belum diaktifkan untuk akun ini."
        )
        
    if not verify_totp(current_user.totp_secret, request.totp_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kode 2FA tidak valid atau sudah kedaluwarsa."
        )
        
    # Issue final token
    access_token = create_access_token(data={"sub": current_user.username, "pending_2fa": False})
    return TokenResponse(access_token=access_token)


@settings_router.post("/binance-key", response_model=BinanceKeyStatusResponse)
def save_binance_key(
    request: BinanceKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Encrypt keys using AES-256-GCM
    try:
        encrypted_key = cipher.encrypt(request.api_key)
        encrypted_secret = cipher.encrypt(request.api_secret)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal melakukan enkripsi kunci API: {str(e)}"
        )
        
    # Check if credential already exists
    cred = db.query(APICredential).filter(APICredential.service_name == "binance").first()
    if not cred:
        cred = APICredential(
            service_name="binance",
            encrypted_api_key=encrypted_key,
            encrypted_api_secret=encrypted_secret
        )
        db.add(cred)
    else:
        cred.encrypted_api_key = encrypted_key
        cred.encrypted_api_secret = encrypted_secret
        
    db.commit()
    return BinanceKeyStatusResponse(has_key=True, service_name="binance")

@settings_router.get("/binance-key", response_model=BinanceKeyStatusResponse)
def get_binance_key_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cred = db.query(APICredential).filter(APICredential.service_name == "binance").first()
    return BinanceKeyStatusResponse(
        has_key=cred is not None,
        service_name="binance"
    )

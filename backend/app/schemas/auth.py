from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)

class LoginResponse(BaseModel):
    session_token: str
    require_2fa: bool

class Verify2FARequest(BaseModel):
    totp_code: str = Field(..., min_length=6, max_length=6)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class BinanceKeyRequest(BaseModel):
    api_key: str = Field(...)
    api_secret: str = Field(...)

class BinanceKeyStatusResponse(BaseModel):
    has_key: bool
    service_name: str

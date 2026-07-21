from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.database import get_db

from app.api.auth import router as auth_router, settings_router as settings_api_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for Trading Edge Intelligence System (TEIS)",
    version="1.1.0",
)

# Set CORS origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(settings_api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs"
    }

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        # Perform simple DB check
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "api_status": "healthy",
        "database_status": db_status
    }

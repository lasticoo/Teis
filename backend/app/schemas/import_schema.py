"""
Pydantic schemas for Historical Import Wizard (Fitur 9).
Follows SOLID: Single Responsibility — only defines request/response data contracts.
"""
from pydantic import BaseModel, field_validator, model_validator
from datetime import date, datetime
from typing import Optional


class ImportRequest(BaseModel):
    """Payload from frontend to trigger a historical import job."""
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def end_date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("end_date tidak boleh melebihi hari ini.")
        return v

    @model_validator(mode="after")
    def date_range_valid(self) -> "ImportRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date harus sebelum atau sama dengan end_date.")
        return self


class ImportJobResponse(BaseModel):
    """Response returned immediately after job is queued."""
    job_id: str
    status: str
    message: str
    start_date: str
    end_date: str


class ImportProgressEvent(BaseModel):
    """WebSocket broadcast payload during import progress."""
    job_id: str
    event: str          # "progress" | "complete" | "error"
    pct: int            # 0-100
    fills_found: int
    trades_saved: int
    skipped: int
    current_symbol: Optional[str] = None
    message: str


class ImportSummary(BaseModel):
    """Final summary broadcast when job finishes."""
    job_id: str
    event: str          # "complete"
    total_fills: int
    total_trades: int
    total_skipped: int
    duration_seconds: float
    message: str

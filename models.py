from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

class IncidentEvent(BaseModel):
    event: str = Field(..., min_length=1, max_length=50)
    incident_id: str = Field(..., min_length=1, max_length=100)
    status: str = Field(..., min_length=1, max_length=30)
    location: str = Field(..., min_length=1, max_length=200)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    severity: Optional[str] = Field("HIGH", max_length=30)
    timestamp: Optional[str] = None

    @field_validator("event", "status", "incident_id")
    def strip_and_upper(cls, v):
        return v.strip().upper()

    @field_validator("severity")
    def default_severity(cls, v):
        return v or "HIGH"


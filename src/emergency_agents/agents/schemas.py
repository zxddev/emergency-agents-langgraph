# Copyright 2025 msq
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

class Coordinates(BaseModel):
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")

class Casualties(BaseModel):
    estimated: int = Field(..., description="Estimated total casualties")
    confirmed: int = Field(..., description="Confirmed casualties")

class Situation(BaseModel):
    disaster_type: str = Field(..., description="Type of disaster: earthquake, flood, fire, etc.")
    magnitude: Optional[float] = Field(None, description="Magnitude or scale of the disaster")
    epicenter: Optional[Coordinates] = Field(None, description="Epicenter coordinates")
    depth_km: Optional[float] = Field(None, description="Depth in km for earthquakes")
    time: Optional[str] = Field(None, description="Time of occurrence (ISO8601)")
    affected_area: Optional[str] = Field(None, description="Name of the affected area")
    nearby_facilities: List[str] = Field(default_factory=list, description="Critical facilities nearby")
    initial_casualties: Optional[Casualties] = Field(None, description="Casualty estimates")
    summary: Optional[str] = Field(None, description="Brief summary of the situation")

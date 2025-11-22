# Copyright 2025 msq
from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RiskItem(BaseModel):
    type: str = Field(..., description="Type of risk (e.g., flood, landslide)")
    display_name: str = Field(..., description="Display name of the risk")
    probability: float = Field(..., description="Probability (0.0-1.0)")
    severity: str = Field(..., description="Severity: low, medium, high, critical")
    eta_hours: float = Field(..., description="Estimated time of arrival in hours")
    rationale: str = Field(..., description="Rationale for the prediction")

class TimelineEvent(BaseModel):
    time: str = Field(..., description="Time point (e.g., T+0h)")
    event: str = Field(..., description="Event description")

class RiskPrediction(BaseModel):
    predicted_risks: List[RiskItem] = Field(default_factory=list, description="List of predicted secondary risks")
    risk_level: int = Field(..., description="Overall risk level (1-5)")
    timeline: List[TimelineEvent] = Field(default_factory=list, description="Predicted timeline of events")

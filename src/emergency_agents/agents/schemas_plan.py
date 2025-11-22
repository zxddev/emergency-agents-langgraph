# Copyright 2025 msq
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

class Phase(BaseModel):
    phase: str = Field(..., description="Phase name (e.g., Initial Response)")
    duration_hours: float = Field(..., description="Estimated duration in hours")
    tasks: List[str] = Field(..., description="List of tasks")
    required_equipment: List[str] = Field(default_factory=list, description="Required equipment")
    personnel: int = Field(..., description="Required personnel count")

class Plan(BaseModel):
    name: str = Field(..., description="Name of the plan")
    priority: str = Field(..., description="Priority level (P0-P3)")
    objectives: List[str] = Field(..., description="Key objectives")
    phases: List[Phase] = Field(..., description="Execution phases")
    estimated_duration_hours: float = Field(..., description="Total estimated duration")
    estimated_cost: float = Field(..., description="Estimated cost")

class AlternativePlan(BaseModel):
    name: str = Field(..., description="Alternative plan name")
    priority: str = Field(..., description="Priority level")
    difference: str = Field(..., description="Key difference from primary plan")

class RescuePlanOutput(BaseModel):
    primary_plan: Plan = Field(..., description="The recommended primary plan")
    alternative_plans: List[AlternativePlan] = Field(default_factory=list, description="Alternative options")
    critical_warnings: List[str] = Field(default_factory=list, description="Critical safety warnings")

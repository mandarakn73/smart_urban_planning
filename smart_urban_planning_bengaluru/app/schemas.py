from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float
    longitude: float


class ScenarioRequest(BaseModel):
    query: str


class ContextRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_m: float = Field(default=500, ge=1, le=10000)


class SpatialRequest(ContextRequest):
    development_type: Optional[str] = None


class DomainRequest(ContextRequest):
    domain: str


class ScenarioAnalyzeRequest(ContextRequest):
    location: Location
    development: Dict[str, Any]


class ScenarioCompareRequest(BaseModel):
    scenarios: List[Dict[str, Any]]


class DesignRequest(BaseModel):
    site: Dict[str, Any]
    development: Dict[str, Any]
    existing_context: Dict[str, Any] = {}
    planning_rules: Any = {}
    impact_analysis: Dict[str, Any] = {}
    strategy: str = "balanced"


class AlternativesRequest(BaseModel):
    site: Dict[str, Any]
    development: Dict[str, Any]
    existing_context: Dict[str, Any] = {}
    planning_rules: Any = {}
    impact_analysis: Dict[str, Any] = {}


class ReportRequest(BaseModel):
    scenario: Dict[str, Any] = {}
    spatial: Dict[str, Any] = {}
    impact_analysis: Dict[str, Any] = {}
    planning_knowledge: Dict[str, Any] = {}
    alternatives: Dict[str, Any] = {}

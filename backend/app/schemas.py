from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RiskProfileRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=18, le=100)
    monthly_income: float = Field(ge=0)
    occupation: Literal["DESK_JOB", "HAZARDOUS", "UNEMPLOYED"]
    is_smoker: bool = False
    has_chronic_illness: bool = False
    owns_vehicle: bool = False
    vehicle_value: float = Field(default=0, ge=0)
    owns_property: bool = False
    property_value: float = Field(default=0, ge=0)
    # Inputs for the ML charges-prediction signal (see backend/ml/). All default
    # so existing callers of this contract keep working unchanged.
    sex: Literal["male", "female"] = "male"
    bmi: float = Field(default=25.0, ge=10, le=60)
    children: int = Field(default=0, ge=0, le=10)
    region: Literal["northeast", "northwest", "southeast", "southwest"] = "southeast"


class RecommendationItem(BaseModel):
    rank: int
    policy_id: int
    policy_name: str
    policy_type: str
    suitability_score: float
    final_premium: float
    rule_based_adjustment: float
    ml_predicted_adjustment: float
    ml_predicted_charges: float
    reasoning: str


class RecommendationResponse(BaseModel):
    customer_id: int
    recommendations: list[RecommendationItem]


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_id: int
    policy_name: str
    policy_type: str
    description: str | None
    base_premium: float
    min_age: int
    max_age: int
    min_income: float
    coverage_amount: float
    is_active: bool


class RecommendationLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    customer_id: int
    policy_id: int
    calculated_suitability_score: float
    final_premium_quoted: float
    recommendation_rank: int
    generated_reasoning: str | None
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: str

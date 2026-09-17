"""Pure, independently unit-testable scoring and premium logic.

No I/O here — everything is a plain function of its inputs so it can be
tested exhaustively without a database or network.
"""

from dataclasses import dataclass

from app.schemas import RiskProfileRequest

# Score deltas applied per policy_type based on risk attributes.
# Positive = increases suitability, negative = decreases it.
SCORE_WEIGHTS: dict[str, dict[str, float]] = {
    "HEALTH": {
        "is_smoker": -10,
        "has_chronic_illness": -15,
        "occupation_hazardous": -5,
        "base": 60,
    },
    "AUTO": {
        "owns_vehicle": 25,
        "vehicle_value_scale": 0.00002,  # per unit of vehicle_value
        "occupation_hazardous": -5,
        "base": 40,
    },
    "LIFE": {
        "is_smoker": -15,
        "has_chronic_illness": -20,
        "occupation_hazardous": -10,
        "owns_property": 5,
        "base": 55,
    },
    "PROPERTY": {
        "owns_property": 30,
        "property_value_scale": 0.000005,
        "base": 40,
    },
}

# Risk-loading coefficients: final_premium = base_premium * (1 + sum(applicable deltas))
RISK_LOADING = {
    "smoker": 0.25,
    "hazardous_occupation": 0.15,
    "chronic_illness": 0.20,
    "unemployed": 0.10,
}


@dataclass
class ScoreResult:
    score: float
    reasoning: str


def score_policy(profile: RiskProfileRequest, policy_type: str) -> ScoreResult:
    """Return a 0-100 suitability score (clamped) and a human-readable reason."""
    weights = SCORE_WEIGHTS.get(policy_type, {"base": 50})
    score = weights.get("base", 50)
    reasons: list[str] = []

    if policy_type == "HEALTH":
        if profile.is_smoker:
            score += weights["is_smoker"]
            reasons.append("smoking status decreased suitability")
        if profile.has_chronic_illness:
            score += weights["has_chronic_illness"]
            reasons.append("chronic illness decreased suitability")
        if profile.occupation == "HAZARDOUS":
            score += weights["occupation_hazardous"]
            reasons.append("hazardous occupation decreased suitability")
        if not profile.is_smoker and not profile.has_chronic_illness:
            reasons.append("clean health profile increased suitability")

    elif policy_type == "AUTO":
        if profile.owns_vehicle:
            score += weights["owns_vehicle"]
            score += profile.vehicle_value * weights["vehicle_value_scale"]
            reasons.append("vehicle ownership and value increased suitability")
        else:
            score -= 20
            reasons.append("no vehicle owned decreased suitability")
        if profile.occupation == "HAZARDOUS":
            score += weights["occupation_hazardous"]
            reasons.append("hazardous occupation decreased suitability")

    elif policy_type == "LIFE":
        if profile.is_smoker:
            score += weights["is_smoker"]
            reasons.append("smoking status decreased suitability")
        if profile.has_chronic_illness:
            score += weights["has_chronic_illness"]
            reasons.append("chronic illness decreased suitability")
        if profile.occupation == "HAZARDOUS":
            score += weights["occupation_hazardous"]
            reasons.append("hazardous occupation decreased suitability")
        if profile.owns_property:
            score += weights["owns_property"]
            reasons.append("property ownership increased suitability")

    elif policy_type == "PROPERTY":
        if profile.owns_property:
            score += weights["owns_property"]
            score += profile.property_value * weights["property_value_scale"]
            reasons.append("property ownership and value increased suitability")
        else:
            score -= 25
            reasons.append("no property owned decreased suitability")

    score = max(0.0, min(100.0, score))
    reasoning = (
        "; ".join(reasons)
        if reasons
        else "baseline suitability for this policy category"
    )
    return ScoreResult(score=round(score, 2), reasoning=reasoning.capitalize() + ".")


def calculate_risk_coefficient(profile: RiskProfileRequest) -> float:
    """Deterministic risk-loading coefficient applied on top of base premium."""
    coefficient = 1.0
    if profile.is_smoker:
        coefficient += RISK_LOADING["smoker"]
    if profile.occupation == "HAZARDOUS":
        coefficient += RISK_LOADING["hazardous_occupation"]
    if profile.has_chronic_illness:
        coefficient += RISK_LOADING["chronic_illness"]
    if profile.occupation == "UNEMPLOYED":
        coefficient += RISK_LOADING["unemployed"]
    return round(coefficient, 4)


def calculate_premium(base_premium: float, profile: RiskProfileRequest) -> float:
    coefficient = calculate_risk_coefficient(profile)
    return round(base_premium * coefficient, 2)


def calculate_hybrid_premium(
    base_premium: float, profile: RiskProfileRequest, ml_predicted_adjustment: float
) -> tuple[float, float]:
    """Blend the deterministic rule-based coefficient with the ML adjustment.

    Returns (final_premium, rule_based_adjustment) so both components can be
    reported separately in the API response — the ML signal augments the
    rule-based one, it never replaces or hides it.
    """
    rule_based_adjustment = calculate_risk_coefficient(profile) - 1.0
    combined_coefficient = max(
        0.5, 1.0 + rule_based_adjustment + ml_predicted_adjustment
    )
    final_premium = round(base_premium * combined_coefficient, 2)
    return final_premium, round(rule_based_adjustment, 4)


def is_eligible(
    profile: RiskProfileRequest, min_age: int, max_age: int, min_income: float
) -> bool:
    return min_age <= profile.age <= max_age and profile.monthly_income >= min_income

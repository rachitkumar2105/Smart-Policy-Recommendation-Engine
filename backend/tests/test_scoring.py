import pytest

from app.schemas import RiskProfileRequest
from app.services.scoring import (
    calculate_premium,
    calculate_risk_coefficient,
    is_eligible,
    score_policy,
)


def make_profile(**overrides) -> RiskProfileRequest:
    defaults = dict(
        full_name="Test User",
        age=30,
        monthly_income=50000,
        occupation="DESK_JOB",
        is_smoker=False,
        has_chronic_illness=False,
        owns_vehicle=False,
        vehicle_value=0,
        owns_property=False,
        property_value=0,
    )
    defaults.update(overrides)
    return RiskProfileRequest(**defaults)


class TestEligibility:
    def test_within_range_is_eligible(self):
        profile = make_profile(age=30, monthly_income=50000)
        assert is_eligible(profile, min_age=18, max_age=65, min_income=20000) is True

    def test_below_min_age_is_ineligible(self):
        profile = make_profile(age=18, monthly_income=50000)
        assert is_eligible(profile, min_age=25, max_age=65, min_income=0) is False

    def test_above_max_age_is_ineligible(self):
        profile = make_profile(age=80, monthly_income=50000)
        assert is_eligible(profile, min_age=18, max_age=65, min_income=0) is False

    def test_below_min_income_is_ineligible(self):
        profile = make_profile(age=30, monthly_income=0)
        assert is_eligible(profile, min_age=18, max_age=65, min_income=20000) is False

    def test_boundary_ages_are_eligible(self):
        profile_min = make_profile(age=18, monthly_income=50000)
        profile_max = make_profile(age=100, monthly_income=50000)
        assert is_eligible(profile_min, min_age=18, max_age=100, min_income=0) is True
        assert is_eligible(profile_max, min_age=18, max_age=100, min_income=0) is True


class TestRiskCoefficient:
    def test_baseline_coefficient_is_one(self):
        profile = make_profile()
        assert calculate_risk_coefficient(profile) == 1.0

    def test_smoker_adds_expected_loading(self):
        profile = make_profile(is_smoker=True)
        assert calculate_risk_coefficient(profile) == pytest.approx(1.25)

    def test_hazardous_occupation_adds_expected_loading(self):
        profile = make_profile(occupation="HAZARDOUS")
        assert calculate_risk_coefficient(profile) == pytest.approx(1.15)

    def test_chronic_illness_adds_expected_loading(self):
        profile = make_profile(has_chronic_illness=True)
        assert calculate_risk_coefficient(profile) == pytest.approx(1.20)

    def test_unemployed_adds_expected_loading(self):
        profile = make_profile(occupation="UNEMPLOYED")
        assert calculate_risk_coefficient(profile) == pytest.approx(1.10)

    def test_multiple_risk_factors_stack(self):
        profile = make_profile(
            is_smoker=True, occupation="HAZARDOUS", has_chronic_illness=True
        )
        assert calculate_risk_coefficient(profile) == pytest.approx(1.60)


class TestPremiumCalculator:
    def test_zero_base_premium_yields_zero(self):
        profile = make_profile(is_smoker=True)
        assert calculate_premium(0, profile) == 0

    def test_baseline_premium_unchanged(self):
        profile = make_profile()
        assert calculate_premium(1000, profile) == 1000.0

    def test_smoker_premium_loaded(self):
        profile = make_profile(is_smoker=True)
        assert calculate_premium(1000, profile) == 1250.0

    def test_stacked_risk_premium_loaded(self):
        profile = make_profile(is_smoker=True, occupation="HAZARDOUS")
        assert calculate_premium(1000, profile) == 1400.0


class TestScoringEngine:
    def test_health_score_penalizes_smoker(self):
        clean = score_policy(make_profile(), "HEALTH")
        smoker = score_policy(make_profile(is_smoker=True), "HEALTH")
        assert smoker.score < clean.score

    def test_health_score_penalizes_chronic_illness(self):
        clean = score_policy(make_profile(), "HEALTH")
        ill = score_policy(make_profile(has_chronic_illness=True), "HEALTH")
        assert ill.score < clean.score

    def test_auto_score_rewards_vehicle_ownership(self):
        no_vehicle = score_policy(make_profile(owns_vehicle=False), "AUTO")
        with_vehicle = score_policy(
            make_profile(owns_vehicle=True, vehicle_value=500000), "AUTO"
        )
        assert with_vehicle.score > no_vehicle.score

    def test_property_score_rewards_property_ownership(self):
        no_property = score_policy(make_profile(owns_property=False), "PROPERTY")
        with_property = score_policy(
            make_profile(owns_property=True, property_value=2000000), "PROPERTY"
        )
        assert with_property.score > no_property.score

    def test_life_score_penalizes_smoker_and_chronic_illness(self):
        clean = score_policy(make_profile(), "LIFE")
        risky = score_policy(
            make_profile(is_smoker=True, has_chronic_illness=True), "LIFE"
        )
        assert risky.score < clean.score

    def test_score_is_clamped_between_zero_and_hundred(self):
        extreme = score_policy(
            make_profile(
                is_smoker=True, has_chronic_illness=True, occupation="HAZARDOUS"
            ),
            "LIFE",
        )
        assert 0.0 <= extreme.score <= 100.0

    def test_unknown_policy_type_falls_back_to_default_score(self):
        result = score_policy(make_profile(), "UNKNOWN_TYPE")
        assert result.score == 50.0

    def test_reasoning_is_nonempty_string(self):
        result = score_policy(make_profile(is_smoker=True), "HEALTH")
        assert isinstance(result.reasoning, str)
        assert len(result.reasoning) > 0

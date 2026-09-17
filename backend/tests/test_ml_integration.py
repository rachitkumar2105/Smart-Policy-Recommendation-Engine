from app.schemas import RiskProfileRequest
from app.services.scoring import calculate_hybrid_premium
from ml.inference import ml_adjustment, predict_charges


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
        sex="male",
        bmi=25,
        children=0,
        region="southeast",
    )
    defaults.update(overrides)
    return RiskProfileRequest(**defaults)


class TestMLInferenceDeterminism:
    def test_same_input_yields_identical_output(self):
        args = dict(
            age=40,
            sex="female",
            bmi=28,
            children=1,
            is_smoker=False,
            region="northwest",
        )
        first = predict_charges(**args)
        second = predict_charges(**args)
        assert first == second

    def test_returns_finite_positive_prediction(self):
        charges = predict_charges(
            age=35, sex="male", bmi=27, children=0, is_smoker=False, region="southeast"
        )
        assert charges > 0

    def test_does_not_crash_on_extreme_bmi(self):
        charges, adj = ml_adjustment(
            age=40, sex="male", bmi=60, children=0, is_smoker=True, region="southeast"
        )
        assert charges > 0
        assert -0.20 <= adj <= 0.50

    def test_does_not_crash_at_age_eligibility_boundaries(self):
        for boundary_age in (18, 100):
            charges, adj = ml_adjustment(
                age=boundary_age,
                sex="female",
                bmi=25,
                children=0,
                is_smoker=False,
                region="southeast",
            )
            assert charges > 0
            assert -0.20 <= adj <= 0.50

    def test_smoker_predicted_higher_than_non_smoker(self):
        non_smoker, _ = ml_adjustment(
            age=40, sex="male", bmi=28, children=0, is_smoker=False, region="southeast"
        )
        smoker, _ = ml_adjustment(
            age=40, sex="male", bmi=28, children=0, is_smoker=True, region="southeast"
        )
        assert smoker > non_smoker


class TestHybridPremium:
    def test_zero_ml_adjustment_matches_rule_based_only(self):
        profile = make_profile(is_smoker=True)
        premium, rule_adj = calculate_hybrid_premium(
            1000, profile, ml_predicted_adjustment=0.0
        )
        assert rule_adj == 0.25
        assert premium == 1250.0

    def test_positive_ml_adjustment_increases_premium(self):
        profile = make_profile()
        baseline, _ = calculate_hybrid_premium(
            1000, profile, ml_predicted_adjustment=0.0
        )
        loaded, _ = calculate_hybrid_premium(1000, profile, ml_predicted_adjustment=0.3)
        assert loaded > baseline

    def test_combined_coefficient_never_drops_premium_below_half_base(self):
        profile = make_profile()
        premium, _ = calculate_hybrid_premium(
            1000, profile, ml_predicted_adjustment=-0.9
        )
        assert premium == 500.0

    def test_rule_based_and_ml_adjustments_reported_separately(self):
        profile = make_profile(occupation="HAZARDOUS")
        premium, rule_adj = calculate_hybrid_premium(
            1000, profile, ml_predicted_adjustment=0.1
        )
        assert rule_adj == 0.15
        assert premium == 1250.0  # 1000 * (1 + 0.15 + 0.10)

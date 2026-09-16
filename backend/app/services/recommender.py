from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, Policy, RecommendationLog
from app.schemas import RecommendationItem, RiskProfileRequest
from app.services.scoring import calculate_premium, is_eligible, score_policy

TOP_N = 5


async def get_eligible_policies(
    db: AsyncSession, profile: RiskProfileRequest
) -> list[Policy]:
    stmt = select(Policy).where(Policy.is_active.is_(True))
    result = await db.execute(stmt)
    all_active = result.scalars().all()
    return [
        p
        for p in all_active
        if is_eligible(profile, p.min_age, p.max_age, float(p.min_income))
    ]


async def generate_recommendations(
    db: AsyncSession, profile: RiskProfileRequest
) -> tuple[int, list[RecommendationItem]]:
    customer = Customer(
        full_name=profile.full_name,
        age=profile.age,
        monthly_income=profile.monthly_income,
        occupation=profile.occupation,
        is_smoker=profile.is_smoker,
        has_chronic_illness=profile.has_chronic_illness,
        owns_vehicle=profile.owns_vehicle,
        vehicle_value=profile.vehicle_value,
        owns_property=profile.owns_property,
        property_value=profile.property_value,
    )
    db.add(customer)
    await db.flush()  # assign customer_id without committing yet

    eligible = await get_eligible_policies(db, profile)

    scored = []
    for policy in eligible:
        result = score_policy(profile, policy.policy_type)
        premium = calculate_premium(float(policy.base_premium), profile)
        scored.append((policy, result, premium))

    scored.sort(key=lambda t: t[1].score, reverse=True)
    top = scored[:TOP_N]

    items: list[RecommendationItem] = []
    for rank, (policy, result, premium) in enumerate(top, start=1):
        log = RecommendationLog(
            customer_id=customer.customer_id,
            policy_id=policy.policy_id,
            calculated_suitability_score=result.score,
            final_premium_quoted=premium,
            recommendation_rank=rank,
            generated_reasoning=result.reasoning,
        )
        db.add(log)
        items.append(
            RecommendationItem(
                rank=rank,
                policy_id=policy.policy_id,
                policy_name=policy.policy_name,
                policy_type=policy.policy_type,
                suitability_score=result.score,
                final_premium=premium,
                reasoning=result.reasoning,
            )
        )

    await db.commit()
    return customer.customer_id, items

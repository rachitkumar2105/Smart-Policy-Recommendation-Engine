"""Seed the policies table with realistic mock catalog data.

Run with: python -m app.seed
"""

import asyncio

from sqlalchemy import func, select

from app.database import AsyncSessionLocal, Base, engine
from app.models import Policy

POLICIES = [
    dict(
        policy_name="Basic Health Shield",
        policy_type="HEALTH",
        description="Entry-level health coverage for individuals.",
        base_premium=800,
        min_age=18,
        max_age=65,
        min_income=15000,
        coverage_amount=300000,
    ),
    dict(
        policy_name="Comprehensive Health Plus",
        policy_type="HEALTH",
        description="Broad health coverage including chronic condition management.",
        base_premium=1800,
        min_age=18,
        max_age=70,
        min_income=30000,
        coverage_amount=1000000,
    ),
    dict(
        policy_name="Senior Care Health",
        policy_type="HEALTH",
        description="Health plan tailored for older adults.",
        base_premium=2200,
        min_age=55,
        max_age=100,
        min_income=20000,
        coverage_amount=750000,
    ),
    dict(
        policy_name="Family Health Guard",
        policy_type="HEALTH",
        description="Family floater health policy.",
        base_premium=2500,
        min_age=18,
        max_age=65,
        min_income=40000,
        coverage_amount=1500000,
    ),
    dict(
        policy_name="Critical Illness Cover",
        policy_type="HEALTH",
        description="Lump-sum payout on diagnosis of critical illness.",
        base_premium=1200,
        min_age=25,
        max_age=60,
        min_income=25000,
        coverage_amount=500000,
    ),
    dict(
        policy_name="Comprehensive Auto Shield",
        policy_type="AUTO",
        description="Full coverage for vehicle damage, theft, and liability.",
        base_premium=1450,
        min_age=21,
        max_age=75,
        min_income=20000,
        coverage_amount=900000,
    ),
    dict(
        policy_name="Third-Party Auto Basic",
        policy_type="AUTO",
        description="Minimum legal liability coverage for vehicle owners.",
        base_premium=450,
        min_age=18,
        max_age=80,
        min_income=10000,
        coverage_amount=200000,
    ),
    dict(
        policy_name="Premium Auto Elite",
        policy_type="AUTO",
        description="High-value vehicle coverage with zero depreciation.",
        base_premium=3200,
        min_age=25,
        max_age=70,
        min_income=60000,
        coverage_amount=2500000,
    ),
    dict(
        policy_name="Two-Wheeler Shield",
        policy_type="AUTO",
        description="Coverage for two-wheeler vehicles.",
        base_premium=350,
        min_age=18,
        max_age=75,
        min_income=8000,
        coverage_amount=100000,
    ),
    dict(
        policy_name="Commercial Fleet Auto",
        policy_type="AUTO",
        description="Coverage for commercially used vehicles.",
        base_premium=2800,
        min_age=21,
        max_age=70,
        min_income=35000,
        coverage_amount=1800000,
    ),
    dict(
        policy_name="Term Life Essential",
        policy_type="LIFE",
        description="Pure protection term life insurance.",
        base_premium=900,
        min_age=18,
        max_age=65,
        min_income=15000,
        coverage_amount=5000000,
    ),
    dict(
        policy_name="Whole Life Secure",
        policy_type="LIFE",
        description="Lifetime coverage with maturity benefit.",
        base_premium=2400,
        min_age=25,
        max_age=60,
        min_income=30000,
        coverage_amount=3000000,
    ),
    dict(
        policy_name="Family Income Protector",
        policy_type="LIFE",
        description="Provides regular income to family in case of death.",
        base_premium=1600,
        min_age=21,
        max_age=55,
        min_income=25000,
        coverage_amount=4000000,
    ),
    dict(
        policy_name="Senior Life Cover",
        policy_type="LIFE",
        description="Life cover designed for senior citizens.",
        base_premium=3000,
        min_age=50,
        max_age=80,
        min_income=20000,
        coverage_amount=1500000,
    ),
    dict(
        policy_name="Young Professional Life Plan",
        policy_type="LIFE",
        description="Affordable term cover for early-career professionals.",
        base_premium=600,
        min_age=21,
        max_age=35,
        min_income=20000,
        coverage_amount=2500000,
    ),
    dict(
        policy_name="Homeowner Property Shield",
        policy_type="PROPERTY",
        description="Coverage against fire, theft, and structural damage.",
        base_premium=1100,
        min_age=21,
        max_age=100,
        min_income=20000,
        coverage_amount=5000000,
    ),
    dict(
        policy_name="Renters Contents Cover",
        policy_type="PROPERTY",
        description="Coverage for personal belongings in a rented home.",
        base_premium=350,
        min_age=18,
        max_age=100,
        min_income=10000,
        coverage_amount=500000,
    ),
    dict(
        policy_name="Commercial Property Guard",
        policy_type="PROPERTY",
        description="Coverage for commercial buildings and equipment.",
        base_premium=4500,
        min_age=21,
        max_age=100,
        min_income=50000,
        coverage_amount=10000000,
    ),
    dict(
        policy_name="Luxury Home Elite",
        policy_type="PROPERTY",
        description="High-value home coverage with agreed-value settlement.",
        base_premium=3800,
        min_age=25,
        max_age=100,
        min_income=80000,
        coverage_amount=15000000,
    ),
    dict(
        policy_name="Natural Disaster Add-On Property",
        policy_type="PROPERTY",
        description="Extended coverage for floods, earthquakes, and storms.",
        base_premium=1500,
        min_age=21,
        max_age=100,
        min_income=25000,
        coverage_amount=6000000,
    ),
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(func.count()).select_from(Policy))
        ).scalar_one()
        if existing > 0:
            print(f"Policies table already has {existing} rows — skipping seed.")
            return
        for data in POLICIES:
            db.add(Policy(**data))
        await db.commit()
        print(f"Seeded {len(POLICIES)} policies.")


if __name__ == "__main__":
    asyncio.run(seed())

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Policy, RecommendationLog
from app.schemas import (
    PolicyOut,
    RecommendationLogOut,
    RecommendationResponse,
    RiskProfileRequest,
)
from app.services.recommender import generate_recommendations

logger = logging.getLogger("spre.recommend")
limiter = Limiter(key_func=get_remote_address)

RECOMMEND_RATE_LIMIT = os.getenv("RECOMMEND_RATE_LIMIT", "20/minute")

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


@router.post("/recommend", response_model=RecommendationResponse)
@limiter.limit(RECOMMEND_RATE_LIMIT)
async def recommend(
    request: Request, payload: RiskProfileRequest, db: AsyncSession = Depends(get_db)
):
    customer_id, items = await generate_recommendations(db, payload)
    logger.info(
        "recommendation_generated",
        extra={"customer_id": customer_id, "num_recommendations": len(items)},
    )
    return RecommendationResponse(customer_id=customer_id, recommendations=items)


@router.get("/policies", response_model=list[PolicyOut])
async def list_policies(db: AsyncSession = Depends(get_db)):
    stmt = select(Policy).where(Policy.is_active.is_(True))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/recommendations/{customer_id}", response_model=list[RecommendationLogOut])
async def get_recommendations_for_customer(
    customer_id: int, db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(RecommendationLog)
        .where(RecommendationLog.customer_id == customer_id)
        .order_by(RecommendationLog.recommendation_rank)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()
    if not logs:
        raise HTTPException(
            status_code=404, detail="No recommendations found for this customer"
        )
    return logs

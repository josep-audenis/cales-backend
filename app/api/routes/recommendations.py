from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.db.crud import get_recommendation_history, log_recommendation
from app.db.models import RecommendationLogDB
from app.db.session import get_session
from app.decision.recommender import get_recommendation
from app.schemas.common import MaterialKey
from app.schemas.recommendation import Recommendation, RecommendationRequest

router = APIRouter(prefix="/recommendation", tags=["recommendation"])


@router.post("", response_model=Recommendation)
def recommend(req: RecommendationRequest, session: Session = Depends(get_session)) -> Recommendation:
    result = get_recommendation(req)
    log_recommendation(session, result)
    return result


@router.get("/history/{material}", response_model=list[RecommendationLogDB])
def recommendation_history(
    material: MaterialKey,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[RecommendationLogDB]:
    return get_recommendation_history(session, material.value, limit)

from fastapi import APIRouter

from app.decision.recommender import get_recommendation
from app.schemas.recommendation import Recommendation, RecommendationRequest

router = APIRouter(prefix="/recommendation", tags=["recommendation"])


@router.post("", response_model=Recommendation)
def recommend(req: RecommendationRequest) -> Recommendation:
    return get_recommendation(req)

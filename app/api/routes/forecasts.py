from fastapi import APIRouter, Query

from app.forecasting.forecast_service import get_forecast
from app.schemas.common import MaterialKey
from app.schemas.forecast import Forecast

router = APIRouter(prefix="/materials", tags=["forecasts"])


@router.get("/{material}/forecast", response_model=Forecast)
def forecast(
    material: MaterialKey,
    horizon_days: int = Query(default=180, ge=1, le=365),
) -> Forecast:
    return get_forecast(material, horizon_days)

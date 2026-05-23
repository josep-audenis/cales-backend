from fastapi import APIRouter

from app.features.material_profiles import MATERIAL_PROFILES
from app.schemas.material import MaterialList

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("", response_model=MaterialList)
def list_materials() -> MaterialList:
    return MaterialList(items=list(MATERIAL_PROFILES.values()))

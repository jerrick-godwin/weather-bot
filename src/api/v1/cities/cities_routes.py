from typing import Optional

import structlog
from fastapi import APIRouter, Depends, status, HTTPException, Query

from src.api.auth import verify_token
from src.models.cities.cities import get_cities_by_region, get_cities_list

logger = structlog.get_logger(__name__)

# Create router
router = APIRouter(prefix="/cities", tags=["Cities"])


@router.get("", summary="Get Monitored Cities")
async def get_monitored_cities(
    limit: Optional[int] = Query(
        default=None, 
        ge=1, 
        description="Maximum number of cities to return"
    ),
    authenticated: bool = Depends(verify_token),
):
    """
    Get the list of cities being monitored by the system.

    When a `limit` is provided, returns a flat list of up to `limit` cities.
    Otherwise, returns both a region-grouped mapping and the complete list.

    Args:
        limit: Optional maximum number of cities to return.

    Returns:
        If limited: a dictionary with keys `cities`, `count`, `limited`, `limit`.
        If not limited: a dictionary with `cities_by_region`, `all_cities`,
        `total_count`, and `regions`.

    Raises:
        HTTPException: 500 if the cities could not be retrieved.
    """
    try:
        if limit:
            cities = get_cities_list(limit)

            return {
                "cities": cities,
                "count": len(cities),
                "limited": True,
                "limit": limit
            }
        else:
            cities_by_region = get_cities_by_region()
            all_cities = get_cities_list()

            return {
                "cities_by_region": cities_by_region,
                "all_cities": all_cities,
                "total_count": len(all_cities),
                "regions": list(cities_by_region.keys()),
            }

    except Exception as e:
        logger.error("Failed to get monitored cities", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get monitored cities: {str(e)}"
        )

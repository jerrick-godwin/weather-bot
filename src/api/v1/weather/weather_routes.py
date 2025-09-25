import structlog
from fastapi import APIRouter, Depends, status, HTTPException, Query

from src.api.auth import verify_token
from src.services.bigquery_service import bigquery_service
from src.services.weather_service import weather_service

logger = structlog.get_logger(__name__)

# Create router
router = APIRouter(prefix="/weather", tags=["Weather"])


@router.get("/current/{city}", summary="Get Current Weather")
async def get_current_weather(city: str, authenticated: bool = Depends(verify_token)):
    """
    Get current weather data for a specific city.

    This endpoint returns the most recent weather data for the specified city,
    either from the database (if recent) or from the live API.

    Args:
        city: City name to query.
        authenticated: Dependency that enforces optional token verification.

    Returns:
        JSON object with core weather attributes and coordinates.

    Raises:
        HTTPException: 404 if city not found, 500 for unexpected errors.
    """
    logger.info(
        "API request: Get current weather",
        city=city,
        authenticated=authenticated
    )
    try:
        weather_record = await bigquery_service.get_latest_weather(city)

        if not weather_record:
            # Fallback to live API
            weather_record = await weather_service.get_current_weather(city)

        logger.info(
            "Successfully retrieved current weather",
            city=city,
            temperature=weather_record.temperature
        )

        response = {
            "city": weather_record.city_name,
            "country": weather_record.country_code,
            "temperature": weather_record.temperature,
            "feels_like": weather_record.feels_like,
            "condition": weather_record.weather_main,
            "description": weather_record.weather_description,
            "humidity": weather_record.humidity,
            "pressure": weather_record.pressure,
            "wind_speed": weather_record.wind_speed,
            "timestamp": weather_record.data_timestamp.isoformat(),
            "coordinates": {
                "latitude": weather_record.latitude,
                "longitude": weather_record.longitude,
            },
        }
        return response

    except Exception as e:
        logger.error(
            "Failed to get current weather",
            city=city,
            error=str(e)
        )
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(e).lower() else status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(
            status_code=status_code,
            detail=f"Failed to get weather for {city}: {str(e)}",
        )


@router.get("/history/{city}", summary="Get Weather History")
async def get_weather_history(
    city: str,
    days: int = Query(
        default=7,
        ge=1,
        le=365,
        description="Number of days of history"
    ),
    authenticated: bool = Depends(verify_token),
):
    """
    Get historical weather data for a specific city.

    Returns weather records for the specified city over the requested time period.

    Args:
        city: City name to query.
        days: Number of previous days to include in the history window.
        authenticated: Dependency for optional token verification.

    Returns:
        A list of daily weather snapshots ordered by timestamp (newest first).

    Raises:
        HTTPException: 404 if no history found, 500 otherwise.
    """
    try:
        logger.info(
            "Getting weather history",
            city=city,
            days=days
        )

        weather_records = await bigquery_service.get_weather_history(
            city=city,
            days=days
        )
        if not weather_records:
            raise RuntimeError()

        return [
            {
                "date": record.data_timestamp.isoformat(),
                "temperature": record.temperature,
                "feels_like": record.feels_like,
                "condition": record.weather_main,
                "description": record.weather_description,
                "humidity": record.humidity,
                "pressure": record.pressure,
                "wind_speed": record.wind_speed,
            }
            for record in weather_records
        ]

    except RuntimeError as e:
        logger.error("Failed to get historical weather history", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No historical weather data found for {city}"
        )

    except Exception as e:
        logger.error("Failed to get weather history", city=city, days=days, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get weather history for {city}: {str(e)}"
        )


@router.get("/summary/{city}", summary="Get Weather Summary")
async def get_weather_summary(
    city: str,
    days: int = Query(
        default=7,
        ge=1,
        le=365,
        description="Number of days to analyze"
    ),
    authenticated: bool = Depends(verify_token),
):
    """
    Get weather summary statistics for a specific city.

    Returns aggregated statistics and insights for the specified city
    over the requested time period.

    Args:
        city: City name to summarize.
        days: Number of previous days to analyze for summary statistics.
        authenticated: Dependency for optional token verification.

    Returns:
        A dictionary of overall metrics and a distribution of weather conditions.

    Raises:
        HTTPException: 500 when summary generation fails.
    """
    try:
        logger.info(
            "Getting weather summary",
            city=city,
            days=days
        )
        summary = await bigquery_service.get_weather_summary(
            city=city,
            days=days
        )

        return summary

    except Exception as e:
        logger.error(
            "Failed to get weather summary",
            city=city,
            days=days,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get weather summary for {city}: {str(e)}"
        )

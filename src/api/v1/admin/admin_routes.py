from datetime import datetime

import structlog
from fastapi import APIRouter, status, Depends, HTTPException

from src.api.auth import verify_token
from src.models.admin import ManualUpdateRequest, SystemStatusResponse
from src.services.bigquery_service import bigquery_service
from src.utils.utils import utils
from src.services.schedule_service import schedule_service
from src.services.weather_service import weather_service

logger = structlog.get_logger(__name__)


# Create router
router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/update", summary="Trigger Manual Update")
async def trigger_manual_update(
        request: ManualUpdateRequest,
        authenticated: bool = Depends(verify_token)
):
    """
    Trigger a manual data update.

    This endpoint allows administrators to manually trigger data updates
    or backfill operations.

    Args:
        request: Payload specifying the type of update ("current" or "backfill").

    Returns:
        A status object including the action that was triggered and timestamp.

    Raises:
        HTTPException: 400 for invalid update type, 500 for processing errors.
    """
    logger.info(
        "API request: Manual update triggered",
        update_type=request.type,
        authenticated=authenticated
    )
    try:
        if request.type == "current":
            result = await utils.run_hourly_update()
        elif request.type == "backfill":
            result = await utils.run_backfill()
        else:
            raise NotImplementedError("Unknown request type")

        logger.info(
            "Manual update completed successfully",
            update_type=request.type,
            result_status=result.get("status")
        )

        return {
            "message": f"Manual {request.type} update triggered successfully",
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        logger.error("Invalid update type", update_type=request.type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid update type. Use 'current' or 'backfill'"
        )
    except Exception as e:
        logger.error("Manual update failed", update_type=request.type, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger {request.type} update: {str(e)}"
        )


@router.get("/status", response_model=SystemStatusResponse, summary="Get System Status")
async def get_system_status(authenticated: bool = Depends(verify_token)):
    """
    Get comprehensive system status information.

    Returns the status of all services, job scheduler, database statistics,
    and overall system health.

    Returns:
        A `SystemStatusResponse` model describing service health and metrics.

    Raises:
        HTTPException: 500 if system status cannot be computed.
    """
    try:
        logger.info("Getting system status")

        # Get status from each service
        job_status = schedule_service.get_job_status()
        db_stats = await bigquery_service.get_database_stats()
        api_stats = weather_service.get_api_usage_stats()
        
        # Get backfill status
        try:
            is_backfill_complete = await utils.is_backfill_complete()
        except Exception as e:
            logger.warning("Could not check backfill status for system status", error=str(e))
            is_backfill_complete = None

        # Determine overall status
        overall_status = "healthy" if job_status["is_running"] else "unhealthy"

        # Determine the individual status
        scheduler_status = "running" if job_status["is_running"] else "stopped"
        backfill_status = "complete" if is_backfill_complete else "incomplete" if is_backfill_complete is False else "unknown"
        weather_api_status = "configured" if api_stats["api_key_configured"] else "not_configured"

        return SystemStatusResponse(
            status=overall_status,
            timestamp=datetime.now().isoformat(),
            services={
                "scheduler": {
                    "status": scheduler_status,
                    "job_status": job_status,
                },
                "weather_api": {
                    "status": weather_api_status,
                    "usage": api_stats,
                },
                "database": {
                    "status": "connected",
                    "stats": db_stats
                },
                "backfill": {
                    "status": backfill_status,
                    "is_complete": is_backfill_complete
                }
            },
            database_stats=db_stats,
        )

    except Exception as e:
        logger.error("Failed to get system status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system status: {str(e)}"
        )


@router.get("/backfill-status", summary="Get Backfill Status")
async def get_backfill_status(authenticated: bool = Depends(verify_token)):
    """
    Get detailed backfill status information.
    
    This endpoint checks the database to determine if historical data backfill
    is complete for all monitored cities.

    Returns:
        Dictionary containing detailed backfill completion status.

    Raises:
        HTTPException: 500 when the status cannot be retrieved.
    """
    try:
        logger.info("API request: Getting backfill status")
        backfill_status = await utils.check_backfill_status()

        logger.info(
            "Backfill status retrieved successfully",
            is_complete=backfill_status["is_backfill_complete"]
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "backfill_status": backfill_status
        }

    except Exception as e:
        logger.error("Failed to get backfill status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backfill status: {str(e)}"
        )


@router.get("/jobs", summary="Get Job Information")
async def get_job_information(authenticated: bool = Depends(verify_token)):
    """
    Get detailed information about scheduled jobs and their execution history.

    Returns:
        Dictionary with job scheduler status and recent execution history.

    Raises:
        HTTPException: 500 when job information cannot be retrieved.
    """
    try:
        job_status = schedule_service.get_job_status()

        return {
            "timestamp": datetime.now().isoformat(),
            "job_status": job_status
        }

    except Exception as e:
        logger.error("Failed to get job information", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job information: {str(e)}"
        )

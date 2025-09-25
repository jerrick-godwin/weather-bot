from datetime import datetime
from typing import Any, Dict

import structlog

from src.config.config import config
from src.exceptions.orchestration import DataPipelineError
from src.models.cities.cities import get_cities_list
from src.services.bigquery_service import bigquery_service
from src.services.weather_service import weather_service
from src.utils.singleton import Singleton

logger = structlog.get_logger(__name__)


class Utils(Singleton):
    """
    Utils for orchestrating weather data collection and processing.

    This service manages:
    - Hourly weather data updates
    - Historical data backfilling
    - Job scheduling and monitoring
    - Error handling and retry logic
    """

    def __init__(self):
        """Initialize the orchestration service."""
        super().__init__()

        if hasattr(self, "_orchestration_initialized"):
            return

        self.weather_service = weather_service
        self.bigquery_service = bigquery_service

        self._orchestration_initialized = True
        logger.info("Orchestration service initialized")

    async def run_hourly_update(self):
        """
        Perform hourly weather data update for all monitored cities.

        Returns:
            Dictionary with update results
        """
        start_time = datetime.now()
        logger.info("Starting hourly weather update", cities_to_monitor=config.cities_to_monitor)

        try:
            # Get list of cities to monitor
            cities = get_cities_list(config.cities_to_monitor)

            # Fetch weather data for all cities
            weather_records = await self.weather_service.get_weather_batch(cities)

            if not weather_records:
                logger.warning("No weather data retrieved in hourly update")
                return {"status": "warning", "message": "No data retrieved"}

            # Insert records into database
            inserted_count = await self.bigquery_service.insert_weather_records(
                records=weather_records,
                ignore_duplicates=True
            )
            duration = (datetime.now() - start_time).total_seconds()

            result = {
                "status": "success",
                "cities_requested": len(cities),
                "records_retrieved": len(weather_records),
                "records_inserted": inserted_count,
                "duration_seconds": duration,
                "timestamp": start_time.isoformat(),
            }

            logger.info(
                "Hourly weather update completed successfully",
                **result,
                performance_metrics={
                    "records_per_second": len(weather_records) / duration if duration > 0 else 0,
                    "success_rate": len(weather_records) / len(cities) if cities else 0
                }
            )
            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_result = {
                "status": "error",
                "error": str(e),
                "duration_seconds": duration,
                "timestamp": start_time.isoformat(),
            }

            logger.error("Hourly weather update failed", **error_result)
            raise DataPipelineError(f"Hourly update failed: {str(e)}")

    async def run_backfill(self):
        """
        Collect current weather data for all monitored cities to start building historical data.

        Note: This system builds historical data by continuously collecting real-time weather data.
        Historical patterns emerge naturally as the system runs over time.
        """
        start_time = datetime.now()
        logger.info("Starting initial weather data collection for all cities")

        try:
            cities = get_cities_list(config.cities_to_monitor)
            
            # Collect current weather for all cities to bootstrap the database
            weather_records = await self.weather_service.get_weather_batch(cities)
            total_records = len(weather_records)
            total_inserted = 0

            if weather_records:
                total_inserted = await self.bigquery_service.insert_weather_records(
                    records=weather_records,
                    ignore_duplicates=True
                )

                logger.info(
                    "Initial weather data collection completed",
                    cities_processed=len(cities),
                    records_collected=total_records,
                    records_inserted=total_inserted,
                )

            duration = (datetime.now() - start_time).total_seconds()

            result = {
                "status": "success",
                "cities_processed": len(cities),
                "total_records_collected": total_records,
                "total_records_inserted": total_inserted,
                "duration_seconds": duration,
                "timestamp": start_time.isoformat(),
            }

            logger.info("Initial weather data collection completed successfully", **result)
            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_result = {
                "status": "error",
                "error": str(e),
                "duration_seconds": duration,
                "timestamp": start_time.isoformat(),
            }

            logger.error("Initial weather data collection failed", **error_result)
            raise DataPipelineError(f"Initial weather data collection failed: {str(e)}")

    async def run_weekly_stats_update(self):
        """Update database statistics weekly."""
        logger.info("Starting weekly stats update")

        try:
            stats = await self.bigquery_service.get_database_stats()
            logger.info("Weekly database statistics", **stats)

            return {"status": "success", "stats": stats}

        except Exception as e:
            logger.error("Weekly stats update failed", error=str(e))
            return {"status": "error", "error": str(e)}

    async def check_backfill_status(self) -> Dict[str, Any]:
        """
        Check if the system has collected sufficient weather data by querying the database.
        
        This checks if cities have accumulated enough real weather data over time.
        The system builds historical data naturally as it runs continuously.
        
        Returns:
            Dictionary with data collection status information
        """
        logger.info("Checking data collection status from database")
        
        try:
            # Get list of cities to check
            cities = get_cities_list(config.cities_to_monitor)
            
            # Calculate expected days of historical data
            expected_days = 30 * config.backfill_months
            
            # Check data collection status from database
            backfill_status = await self.bigquery_service.check_backfill_status(
                cities, expected_days
            )
            
            logger.info(
                "Backfill status check completed",
                is_complete=backfill_status["is_backfill_complete"],
                cities_with_data=backfill_status["cities_with_data"],
                total_cities=backfill_status["total_cities_expected"]
            )
            
            return backfill_status
            
        except Exception as e:
            logger.error("Failed to check backfill status", error=str(e))
            raise DataPipelineError(f"Failed to check backfill status: {str(e)}")
    
    async def is_backfill_complete(self) -> bool:
        """
        Check if sufficient weather data has been collected.
        
        Returns:
            True if enough data has been collected over time, False otherwise
        """
        try:
            status = await self.check_backfill_status()

            return status["is_backfill_complete"]

        except Exception as e:
            logger.warning("Could not check data collection status, assuming incomplete", error=str(e))
            return False


utils = Utils()

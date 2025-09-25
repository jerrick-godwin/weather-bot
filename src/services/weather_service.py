import asyncio
import inspect
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import structlog
from pydantic import ValidationError

from src.config.config import config
from src.exceptions.weather import (
    APIRequestError,
    InvalidCityError,
    RateLimitError,
    WeatherServiceError,
)
from src.models.cities.cities import get_cities_list
from src.models.weather.weather import OpenWeatherMapResponse, WeatherRecord
from src.utils.singleton import Singleton

logger = structlog.get_logger(__name__)


class WeatherService(Singleton):
    """
    Service for collecting weather data from OpenWeatherMap API.

    This service provides methods to fetch current weather data and historical
    weather data for cities, with proper error handling and rate limiting.
    """

    def __init__(self):
        """Initialize the weather service."""
        super().__init__()

        if hasattr(self, "_weather_initialized"):
            return

        self.base_url = config.openweather_base_url
        self.api_key = config.openweather_api_key
        self.units = config.openweather_units

        # Rate limiting
        self.max_requests_per_minute = 60  # OpenWeatherMap free tier limit
        self.request_timestamps: List[datetime] = []

        # HTTP client configuration
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self.retry_attempts = 3
        self.retry_backoff = 1.0  # seconds

        self._weather_initialized = True

        if not self.api_key:
            raise APIRequestError("OpenWeatherMap API key is required")

    async def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an HTTP request to the OpenWeatherMap API with rate limiting and retry logic.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response from the API

        Raises:
            APIRateLimitError: If rate limit is exceeded
            CityNotFoundError: If city is not found (404)
            WeatherServiceError: For other API errors
        """
        # Add API key to parameters
        params["appid"] = self.api_key
        params["units"] = self.units

        # Rate limiting check
        await self._check_rate_limit()

        for attempt in range(self.retry_attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(
                        "Making API request",
                        url=self.base_url,
                        params=params,
                        attempt=attempt + 1
                    )

                    response = await client.get(self.base_url, params=params)

                    # Record request timestamp for rate limiting
                    self.request_timestamps.append(datetime.now())

                    if response.status_code == 200:
                        data = response.json()
                        return await data if inspect.isawaitable(data) else data
                    elif response.status_code == 404:
                        raise InvalidCityError(f"Invalid city or request: {response.text}")
                    elif response.status_code == 401:
                        raise APIRequestError("Invalid API key")
                    elif response.status_code == 429:
                        raise RateLimitError("API rate limit exceeded")
                    else:
                        logger.warning(
                            "API request failed",
                            status_code=response.status_code,
                            response_text=response.text,
                        )
                        response.raise_for_status()

            except httpx.TimeoutException:
                logger.warning("Request timeout", attempt=attempt + 1)
                if attempt == self.retry_attempts - 1:
                    raise WeatherServiceError("Request timeout after all retry attempts")
                await asyncio.sleep(self.retry_backoff * (attempt + 1))

            except httpx.RequestError as e:
                logger.warning("Request error", error=str(e), attempt=attempt + 1)
                if attempt == self.retry_attempts - 1:
                    raise WeatherServiceError(f"Request failed: {str(e)}")
                await asyncio.sleep(self.retry_backoff * (attempt + 1))

        raise WeatherServiceError("All retry attempts failed")

    async def _check_rate_limit(self):
        """
        Check and enforce rate limiting.

        Raises:
            APIRateLimitError: If rate limit would be exceeded
        """
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)

        # Remove old timestamps
        self.request_timestamps = [ts for ts in self.request_timestamps if ts > one_minute_ago]

        if len(self.request_timestamps) >= self.max_requests_per_minute:
            # Wait until we can make another request
            oldest_request = min(self.request_timestamps)
            wait_time = 60 - (now - oldest_request).total_seconds()
            if wait_time > 0:
                logger.info("Rate limit reached, waiting", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)

    async def get_current_weather(self, city: str) -> WeatherRecord:
        """
        Get current weather data for a city.

        Args:
            city: Name of the city

        Returns:
            WeatherRecord with current weather data

        Raises:
            CityNotFoundError: If city is not found
            WeatherServiceError: For other API errors
        """
        logger.info("Fetching current weather", city=city)
        try:
            params = {"q": city}
            data = await self._make_request(params)

            # Parse and validate the response
            response = OpenWeatherMapResponse(**data)
            weather_record = WeatherRecord.from_openweather_response(response)

            logger.info("Successfully fetched current weather", city=city)
            return weather_record

        except ValidationError as e:
            logger.error("Failed to parse weather data", city=city, error=str(e))
            raise WeatherServiceError(f"Invalid weather data received for {city}: {str(e)}")

    async def get_current_weather_by_id(self, city_id: int) -> WeatherRecord:
        """
        Get current weather data for a city by its OpenWeatherMap ID.

        Args:
            city_id: OpenWeatherMap city ID

        Returns:
            WeatherRecord with current weather data

        Raises:
            CityNotFoundError: If city ID is not found
            WeatherServiceError: For other API errors
        """
        try:
            params = {"id": str(city_id)}
            data = await self._make_request(params)

            response = OpenWeatherMapResponse(**data)
            weather_record = WeatherRecord.from_openweather_response(response)

            logger.info("Successfully fetched current weather by ID", city_id=city_id)
            return weather_record

        except ValidationError as e:
            logger.error("Failed to parse weather data", city_id=city_id, error=str(e))
            raise WeatherServiceError(
                f"Invalid weather data received for city ID {city_id}: {str(e)}"
            )

    async def get_weather_batch(
        self, cities: List[str], max_concurrent: int = 10
    ) -> List[WeatherRecord]:
        """
        Get current weather data for multiple cities concurrently.

        Args:
            cities: List of city names
            max_concurrent: Maximum number of concurrent requests

        Returns:
            List of WeatherRecord objects (may be fewer than input if some cities fail)
        """
        async def fetch_with_semaphore(city: str) -> Optional[WeatherRecord]:
            semaphore = asyncio.Semaphore(max_concurrent)
            async with semaphore:
                try:
                    return await self.get_current_weather(city)
                except Exception as e:
                    logger.warning(
                        "Failed to fetch weather for city", 
                        city=city, 
                        error=str(e)
                    )
                    return None

        logger.info(
            "Starting batch weather fetch", 
            city_count=len(cities), 
            max_concurrent=max_concurrent
        )
        
        start_time = datetime.now()
        tasks = [fetch_with_semaphore(city) for city in cities]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Filter out None results
        weather_records = [record for record in results if record is not None]

        duration = (datetime.now() - start_time).total_seconds()
        success_rate = len(weather_records) / len(cities) if cities else 0
        
        logger.info(
            "Batch weather fetch completed",
            requested_cities=len(cities),
            successful_fetches=len(weather_records),
            duration_seconds=duration,
            success_rate=success_rate,
            requests_per_second=len(cities) / duration if duration > 0 else 0
        )

        return weather_records


    async def get_all_cities_weather(self, limit: int = None) -> List[WeatherRecord]:
        """
        Get current weather data for all monitored cities.

        Args:
            limit: Maximum number of cities to fetch (uses all cities if None)

        Returns:
            List of WeatherRecord objects
        """
        cities = get_cities_list(limit or config.cities_to_monitor)
        return await self.get_weather_batch(cities)

    def get_api_usage_stats(self) -> Dict[str, Any]:
        """
        Get API usage statistics.

        Returns:
            Dictionary with usage statistics
        """
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)

        requests_last_hour = len([ts for ts in self.request_timestamps if ts > one_hour_ago])

        requests_last_day = len([ts for ts in self.request_timestamps if ts > one_day_ago])

        return {
            "requests_last_hour": requests_last_hour,
            "requests_last_day": requests_last_day,
            "total_requests_tracked": len(self.request_timestamps),
            "rate_limit_per_minute": self.max_requests_per_minute,
            "api_key_configured": bool(self.api_key),
            "base_url": self.base_url,
            "units": self.units,
        }


weather_service = WeatherService()

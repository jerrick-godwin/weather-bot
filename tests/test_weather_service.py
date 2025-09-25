from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

import httpx
import pytest

from src.exceptions.weather import (
    APIRequestError,
    InvalidCityError,
    RateLimitError,
    WeatherServiceError,
)
from src.models.weather.weather import WeatherRecord
from src.services.weather_service import WeatherService


class TestWeatherService:
    """Test cases for the WeatherService class."""

    @pytest.mark.asyncio
    async def test_make_request_success(self, mock_config):
        """Test successful API request."""
        WeatherService._instances = {}

        with patch('src.services.weather_service.config', mock_config):
            service = WeatherService()

            mock_response_data = {"weather": "data"}

            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_response_data
                mock_client.get.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                result = await service._make_request({"q": "London"})

                assert result == mock_response_data
                mock_client.get.assert_called_once()
                call_args = mock_client.get.call_args
                assert call_args[1]["params"]["q"] == "London"
                assert call_args[1]["params"]["appid"] == mock_config.openweather_api_key
                assert call_args[1]["params"]["units"] == "metric"

    @pytest.mark.asyncio
    async def test_make_request_city_not_found(self, mock_config):
        """Test API request with 404 response."""
        WeatherService._instances = {}

        service = WeatherService()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_response.text = "City not found"
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(InvalidCityError, match="Invalid city or request"):
                await service._make_request({"q": "InvalidCity"})

    @pytest.mark.asyncio
    async def test_make_request_invalid_api_key(self, mock_config):
        """Test API request with 401 response."""
        WeatherService._instances = {}

        service = WeatherService()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(APIRequestError, match="Invalid API key"):
                await service._make_request({"q": "London"})

    @pytest.mark.asyncio
    async def test_make_request_rate_limit(self, mock_config):
        """Test API request with 429 response."""
        WeatherService._instances = {}

        service = WeatherService()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(RateLimitError, match="API rate limit exceeded"):
                await service._make_request({"q": "London"})

    @pytest.mark.asyncio
    async def test_make_request_timeout_retry(self, mock_config):
        """Test API request with timeout and retry logic."""
        WeatherService._instances = {}

        service = WeatherService()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"weather": "data"}

            # First two calls timeout, third succeeds
            mock_client.get.side_effect = [
                httpx.TimeoutException("Timeout"),
                httpx.TimeoutException("Timeout"),
                mock_response
            ]
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await service._make_request({"q": "London"})

            assert result == {"weather": "data"}
            assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_make_request_all_retries_failed(self, mock_config):
        """Test API request when all retries fail."""
        WeatherService._instances = {}

        service = WeatherService()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Timeout")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(WeatherServiceError, match=r"Request timeout after all retry attempts"):
                await service._make_request({"q": "London"})

    @pytest.mark.asyncio
    async def test_check_rate_limit_no_wait(self, mock_config):
        """Test rate limit check when under limit."""
        WeatherService._instances = {}

        service = WeatherService()
        service.request_timestamps = [datetime.now() - timedelta(seconds=30) for _ in range(50)]

        # Should not raise or wait
        await service._check_rate_limit()

    @pytest.mark.asyncio
    async def test_check_rate_limit_with_wait(self, mock_config):
        """Test rate limit check when at limit."""
        WeatherService._instances = {}

        service = WeatherService()
        # Fill up the rate limit
        recent_time = datetime.now() - timedelta(seconds=30)
        service.request_timestamps = [recent_time] * 60

        with patch('asyncio.sleep') as mock_sleep:
            await service._check_rate_limit()
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_current_weather_success(self, mock_config):
        """Test successful current weather fetch."""
        WeatherService._instances = {}

        service = WeatherService()

        mock_api_response = {
            "coord": {"lon": -0.1278, "lat": 51.5074},
            "weather": [{"id": 801, "main": "Clouds", "description": "few clouds", "icon": "02d"}],
            "base": "stations",
            "main": {
                "temp": 15.5,
                "feels_like": 14.8,
                "temp_min": 12.3,
                "temp_max": 18.7,
                "pressure": 1013,
                "humidity": 65,
                "sea_level": 1013,
                "grnd_level": 1009
            },
            "visibility": 10000,
            "wind": {"speed": 3.5, "deg": 180, "gust": 5.0},
            "clouds": {"all": 20},
            "dt": 1696161600,
            "sys": {
                "type": 2,
                "id": 2075535,
                "country": "GB",
                "sunrise": 1696138800,
                "sunset": 1696182000
            },
            "timezone": 3600,
            "id": 2643743,
            "name": "London",
            "cod": 200
        }

        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_make_request:
            mock_make_request.return_value = mock_api_response

            result = await service.get_current_weather("London")

            assert isinstance(result, WeatherRecord)
            assert result.city_name == "London"
            assert result.temperature == 15.5
            assert result.humidity == 65
            assert result.weather_description == "few clouds"

            mock_make_request.assert_called_once_with({"q": "London"})

    @pytest.mark.asyncio
    async def test_get_current_weather_validation_error(self, mock_config):
        """Test current weather fetch with invalid API response."""
        WeatherService._instances = {}

        service = WeatherService()

        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_make_request:
            mock_make_request.return_value = {"invalid": "data"}

            with pytest.raises(WeatherServiceError, match="Invalid weather data received"):
                await service.get_current_weather("London")

    @pytest.mark.asyncio
    async def test_get_current_weather_by_id_success(self, mock_config):
        """Test successful current weather fetch by city ID."""
        WeatherService._instances = {}

        service = WeatherService()

        mock_api_response = {
            "coord": {"lon": -0.1278, "lat": 51.5074},
            "weather": [{"id": 801, "main": "Clouds", "description": "few clouds", "icon": "02d"}],
            "base": "stations",
            "main": {
                "temp": 15.5,
                "feels_like": 14.8,
                "temp_min": 12.3,
                "temp_max": 18.7,
                "pressure": 1013,
                "humidity": 65
            },
            "dt": 1696161600,
            "sys": {
                "country": "GB",
                "sunrise": 1696138800,
                "sunset": 1696182000
            },
            "timezone": 3600,
            "id": 2643743,
            "name": "London",
            "cod": 200
        }

        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_make_request:
            mock_make_request.return_value = mock_api_response

            result = await service.get_current_weather_by_id(2643743)

            assert isinstance(result, WeatherRecord)
            assert result.city_name == "London"

            mock_make_request.assert_called_once_with({"id": "2643743"})

    @pytest.mark.asyncio
    async def test_get_weather_batch_success(self, mock_config):
        """Test successful batch weather fetch."""
        WeatherService._instances = {}

        service = WeatherService()

        mock_weather_record = WeatherRecord(
            city_id=2643743,
            city_name="London",
            country_code="GB",
            latitude=51.5074,
            longitude=-0.1278,
            base="stations",
            temperature=15.5,
            feels_like=14.8,
            temp_min=12.3,
            temp_max=18.7,
            pressure=1013,
            humidity=65,
            sea_level_pressure=1013,
            ground_level_pressure=1009,
            weather_main="Clouds",
            weather_description="Partly cloudy",
            weather_icon="02d",
            weather_conditions=[],
            data_timestamp=datetime.fromisoformat("2023-10-01T12:00:00"),
            sunrise=datetime.fromisoformat("2023-10-01T07:00:00"),
            sunset=datetime.fromisoformat("2023-10-01T18:00:00"),
            timezone_offset=3600,
            created_at=datetime.now()
        )

        with patch.object(service, 'get_current_weather', new_callable=AsyncMock) as mock_get_weather:
            mock_get_weather.return_value = mock_weather_record

            cities = ["London", "Paris", "Berlin"]
            result = await service.get_weather_batch(cities, max_concurrent=2)

            assert len(result) == 3
            assert all(isinstance(record, WeatherRecord) for record in result)
            assert mock_get_weather.call_count == 3

    @pytest.mark.asyncio
    async def test_get_weather_batch_with_failures(self, mock_config):
        """Test batch weather fetch with some failures."""
        WeatherService._instances = {}

        service = WeatherService()

        mock_weather_record = WeatherRecord(
            city_id=2643743,
            city_name="London",
            country_code="GB",
            latitude=51.5074,
            longitude=-0.1278,
            base="stations",
            temperature=15.5,
            feels_like=14.8,
            temp_min=12.3,
            temp_max=18.7,
            pressure=1013,
            humidity=65,
            sea_level_pressure=1013,
            ground_level_pressure=1009,
            weather_main="Clouds",
            weather_description="Partly cloudy",
            weather_icon="02d",
            weather_conditions=[],
            data_timestamp=datetime.fromisoformat("2023-10-01T12:00:00"),
            sunrise=datetime.fromisoformat("2023-10-01T07:00:00"),
            sunset=datetime.fromisoformat("2023-10-01T18:00:00"),
            timezone_offset=3600,
            created_at=datetime.now()
        )

        with patch.object(service, 'get_current_weather', new_callable=AsyncMock) as mock_get_weather:
            # London succeeds, Paris fails, Berlin succeeds
            mock_get_weather.side_effect = [
                mock_weather_record,
                Exception("City not found"),
                mock_weather_record
            ]

            cities = ["London", "Paris", "Berlin"]
            result = await service.get_weather_batch(cities)

            assert len(result) == 2  # Only successful fetches
            assert all(isinstance(record, WeatherRecord) for record in result)

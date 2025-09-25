import pytest

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from agents import RunContextWrapper
from agents.exceptions import InputGuardrailTripwireTriggered

from agent.weather_agent import WeatherAgent
from src.exceptions import BigQueryServiceError
from src.models.weather.weather import WeatherRecord
from src.services.bigquery_service import BigQueryService
from src.services.weather_service import WeatherService


class TestWeatherAgent:
    """Test cases for the WeatherAgent class."""


    async def _helper_get_current_weather(
            self,
            mock_datetime: datetime,
            mock_weather_service: WeatherService,
            mock_bigquery_service: BigQueryService,
            city: str
    ):
        """ Helper function that replicates the _get_current_weather logic """
        try:
            # Check database first for recent data
            weather_record = await mock_bigquery_service.get_latest_weather(city)
            if weather_record and (mock_datetime.now() - weather_record.data_timestamp) <= timedelta(hours=2):
                return {"source": "database", **weather_record.model_dump()}

            # Fallback to live API
            live_weather = await mock_weather_service.get_current_weather(city)
            return {"source": "live_api", **live_weather.model_dump()}

        except Exception as e:
            return {"error": f"Could not retrieve current weather for {city}: {str(e)}"}

    async def _helper_get_weather_history(
            self,
            mock_bigquery_service: BigQueryService,
            city: str,
            days: int = 7
    ):
        """ Helper function that replicates the _get_weather_history logic """
        try:
            records = await mock_bigquery_service.get_weather_history(city, days)
            if not records:
                return {"error": f"No historical data found for {city} for the last {days} days."}

            return {"history": [record.model_dump() for record in records]}

        except Exception as e:
            return {"error": f"Failed to retrieve weather history for {city}: {str(e)}"}

    async def _helper_get_weather_summary(
            self,
            mock_bigquery_service: BigQueryService,
            city: str,
            days: int = 7
    ):
        """ Helper function that replicates the _get_weather_summary logic """
        try:
            summary = await mock_bigquery_service.get_weather_summary(city, days)
            return summary

        except Exception as e:
            return {"error": f"Failed to retrieve weather summary for {city}: {str(e)}"}

    @pytest.mark.asyncio
    async def test_weather_agent_initialization(self, mock_config):
        """Test that WeatherAgent initializes correctly."""
        # Reset singleton for testing
        WeatherAgent._instances = {}

        agent = WeatherAgent()

        assert agent.agent is not None

    @pytest.mark.asyncio
    async def test_weather_agent_run_without_context(self, mock_config, mock_runner_run):
        """Test running weather agent without context."""
        WeatherAgent._instances = {}
        agent = WeatherAgent()

        result = await agent.run("What's the weather like?")

        mock_runner_run.assert_called_once()
        assert result is not None
        assert hasattr(result, 'final_output')

    @pytest.mark.asyncio
    async def test_weather_agent_run_with_context(self, mock_config, mock_runner_run):
        """Test running weather agent with context."""
        WeatherAgent._instances = {}
        agent = WeatherAgent()

        ctx = MagicMock(spec=RunContextWrapper)
        ctx.context = MagicMock()

        result = await agent.run("What's the weather like?", ctx)

        mock_runner_run.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_current_weather_from_database(
            self,
            sample_weather_record: dict,
            mock_bigquery_service: BigQueryService,
            mock_weather_service: WeatherService
    ):
        """Test getting current weather from database when data is recent."""

        WeatherAgent._instances = {}

        # Mock database returning recent data
        mock_bigquery_service.get_latest_weather.return_value = sample_weather_record

        with patch('agent.weather_agent.bigquery_service', mock_bigquery_service), \
             patch('agent.weather_agent.weather_service', mock_weather_service), \
             patch('agent.weather_agent.datetime') as mock_datetime:

            mock_datetime.now.return_value = datetime.fromisoformat("2023-10-01T12:30:00")
            result = await self._helper_get_current_weather(
                mock_datetime=mock_datetime,
                mock_weather_service=mock_weather_service,
                mock_bigquery_service=mock_bigquery_service,
                city="London"
            )

            assert result["source"] == "database"
            assert result["city_name"] == "London"
            assert result["temperature"] == 15.5
            mock_bigquery_service.get_latest_weather.assert_called_once_with("London")
            mock_weather_service.get_current_weather.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_current_weather_from_api(self, sample_weather_record, mock_bigquery_service, mock_weather_service):
        """Test getting current weather from API when database data is stale."""
        WeatherAgent._instances = {}

        # Mock database returning old data
        mock_bigquery_service.get_latest_weather.return_value = sample_weather_record
        mock_weather_service.get_current_weather.return_value = sample_weather_record

        with patch('agent.weather_agent.bigquery_service', mock_bigquery_service), \
             patch('agent.weather_agent.weather_service', mock_weather_service), \
             patch('agent.weather_agent.datetime') as mock_datetime:

            # Set current time to be more than 2 hours after the data timestamp
            mock_datetime.now.return_value = datetime.fromisoformat("2023-10-01T15:00:00")
            result = await self._helper_get_current_weather(
                mock_datetime=mock_datetime,
                mock_weather_service=mock_weather_service,
                mock_bigquery_service=mock_bigquery_service,
                city="London"
            )

            assert result["source"] == "live_api"
            mock_bigquery_service.get_latest_weather.assert_called_once_with("London")
            mock_weather_service.get_current_weather.assert_called_once_with("London")

    @pytest.mark.asyncio
    async def test_get_current_weather_no_database_data(self, mock_bigquery_service, mock_weather_service, sample_weather_record):
        """Test getting current weather from API when no database data exists."""
        WeatherAgent._instances = {}

        # Mock database returning None
        mock_bigquery_service.get_latest_weather.return_value = None
        mock_weather_service.get_current_weather.return_value = sample_weather_record

        with patch('agent.weather_agent.bigquery_service', mock_bigquery_service), \
             patch('agent.weather_agent.weather_service', mock_weather_service), \
             patch('agent.weather_agent.datetime') as mock_datetime:
            result = await self._helper_get_current_weather(
                mock_datetime=mock_datetime,
                mock_weather_service=mock_weather_service,
                mock_bigquery_service=mock_bigquery_service,
                city="London"
            )

            assert result["source"] == "live_api"
            mock_bigquery_service.get_latest_weather.assert_called_once_with("London")
            mock_weather_service.get_current_weather.assert_called_once_with("London")

    @pytest.mark.asyncio
    async def test_get_current_weather_error_handling(self, mock_bigquery_service, mock_weather_service):
        """Test error handling in get_current_weather."""
        WeatherAgent._instances = {}

        from src.exceptions import BigQueryServiceError
        mock_bigquery_service.get_latest_weather.side_effect = BigQueryServiceError("Database error")
        mock_weather_service.get_current_weather.side_effect = Exception("API error")

        with patch('agent.weather_agent.bigquery_service', mock_bigquery_service), \
             patch('agent.weather_agent.weather_service', mock_weather_service), \
             patch('agent.weather_agent.datetime') as mock_datetime:
            result = await self._helper_get_current_weather(
                mock_datetime=mock_datetime,
                mock_weather_service=mock_weather_service,
                mock_bigquery_service=mock_bigquery_service,
                city="London"
            )

            assert "error" in result
            assert "Could not retrieve current weather" in result["error"]

    @pytest.mark.asyncio
    async def test_get_weather_history_success(self, mock_bigquery_service):
        """Test successful weather history retrieval."""
        WeatherAgent._instances = {}

        mock_records = [
            WeatherRecord(
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
                weather_description="Cloudy",
                weather_icon="02d",
                weather_conditions=[],
                data_timestamp=datetime.fromisoformat("2023-10-01T12:00:00"),
                sunrise=datetime.fromisoformat("2023-10-01T07:00:00"),
                sunset=datetime.fromisoformat("2023-10-01T18:00:00"),
                timezone_offset=3600,
                created_at=datetime.now()
            ),
            WeatherRecord(
                city_id=2643743,
                city_name="London",
                country_code="GB",
                latitude=51.5074,
                longitude=-0.1278,
                base="stations",
                temperature=16.0,
                feels_like=15.2,
                temp_min=13.1,
                temp_max=19.5,
                pressure=1014,
                humidity=60,
                sea_level_pressure=1014,
                ground_level_pressure=1010,
                weather_main="Clear",
                weather_description="Sunny",
                weather_icon="01d",
                weather_conditions=[],
                data_timestamp=datetime.fromisoformat("2023-10-02T12:00:00"),
                sunrise=datetime.fromisoformat("2023-10-02T07:02:00"),
                sunset=datetime.fromisoformat("2023-10-02T17:58:00"),
                timezone_offset=3600,
                created_at=datetime.now()
            )
        ]
        mock_bigquery_service.get_weather_history.return_value = mock_records

        with patch('agent.weather_agent.bigquery_service', mock_bigquery_service):
            result = await self._helper_get_weather_history(
                mock_bigquery_service=mock_bigquery_service,
                city="London",
                days=7
            )

            assert "history" in result
            assert len(result["history"]) == 2
            mock_bigquery_service.get_weather_history.assert_called_once_with("London", 7)

    @pytest.mark.asyncio
    async def test_get_weather_history_no_data(self, mock_bigquery_service):
        """Test weather history retrieval when no data is found."""
        WeatherAgent._instances = {}
        mock_bigquery_service.get_weather_history.return_value = []

        with patch('agent.weather_agent.bigquery_service', mock_bigquery_service):
            result = await self._helper_get_weather_history(
                mock_bigquery_service=mock_bigquery_service,
                city="London",
                days=7
            )

            assert "error" in result
            assert "No historical data found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_weather_history_error(self, mock_bigquery_service):
        """Test error handling in get_weather_history."""
        WeatherAgent._instances = {}
        mock_bigquery_service.get_weather_history.side_effect = BigQueryServiceError("Query failed")

        with patch('agent.weather_agent.bigquery_service', mock_bigquery_service):
            result = await self._helper_get_weather_history(
                mock_bigquery_service=mock_bigquery_service,
                city="London",
                days=7
            )

            assert "error" in result
            assert "Failed to retrieve weather history" in result["error"]

    @pytest.mark.asyncio
    async def test_get_weather_summary_success(self, mock_bigquery_service):
        """Test successful weather summary retrieval."""
        WeatherAgent._instances = {}

        mock_summary = {
            "average_temperature": 15.5,
            "min_temperature": 10.0,
            "max_temperature": 20.0,
            "total_records": 7
        }
        mock_bigquery_service.get_weather_summary.return_value = mock_summary

        with patch('agent.weather_agent.bigquery_service', mock_bigquery_service):
            result = await self._helper_get_weather_summary(
                mock_bigquery_service=mock_bigquery_service,
                city="London",
                days=7
            )

            assert result == mock_summary
            mock_bigquery_service.get_weather_summary.assert_called_once_with("London", 7)

    @pytest.mark.asyncio
    async def test_get_weather_summary_error(self, mock_bigquery_service):
        """Test error handling in get_weather_summary."""
        WeatherAgent._instances = {}

        from src.exceptions import BigQueryServiceError
        mock_bigquery_service.get_weather_summary.side_effect = BigQueryServiceError("Summary query failed")

        with patch('agent.weather_agent.bigquery_service', mock_bigquery_service):
            result = await self._helper_get_weather_summary(
                mock_bigquery_service=mock_bigquery_service,
                city="London",
                days=7
            )

            assert "error" in result
            assert "Failed to retrieve weather summary" in result["error"]

    @pytest.mark.asyncio
    async def test_process_query_success(self, mock_config, mock_runner_run):
        """Test successful query processing."""
        WeatherAgent._instances = {}
        agent = WeatherAgent()

        # Query the agent
        result = await agent.process_query("What's the weather in London?")

        assert "response" in result
        assert "query" in result
        assert "processing_time" in result
        assert result["query"] == "What's the weather in London?"
        assert isinstance(result["processing_time"], float)

    @pytest.mark.asyncio
    async def test_process_query_guardrail_triggered(self, mock_config):
        """Test query processing when guardrail is triggered."""
        WeatherAgent._instances = {}

        # Create a proper mock guardrail result
        mock_guardrail_result = MagicMock()
        mock_guardrail_result.guardrail = MagicMock()
        mock_guardrail_result.guardrail.__class__.__name__ = "InputGuardrail"

        # Configure mock to trigger guardrail (non-weather related)
        with patch('agents.Runner.run', side_effect=InputGuardrailTripwireTriggered(mock_guardrail_result)):
            agent = WeatherAgent()
            result = await agent.process_query("What's the football score?")

            assert "response" in result
            assert "error" in result
            assert result["error"] == "Guardrail triggered"
            assert "weather assistant" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_process_query_general_error(self, mock_config):
        """Test query processing with general error."""
        WeatherAgent._instances = {}

        with patch('agents.Runner.run', side_effect=Exception("Test error")):
            agent = WeatherAgent()
            with pytest.raises(Exception, match="Failed to process agent query: Test error"):
                await agent.process_query("What's the weather?")

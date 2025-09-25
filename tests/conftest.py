import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.guardrail.guardrail_output import GuardrailOutput
from src.models.orchestrator.agent_response import AgentResponse
from src.models.weather.weather import WeatherRecord


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for agent testing."""
    mock_client = AsyncMock()
    with patch('openai.AsyncOpenAI', return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_bigquery_service():
    """Mock BigQuery service for testing."""
    mock_service = AsyncMock()
    mock_service.get_latest_weather = AsyncMock()
    mock_service.get_weather_history = AsyncMock()
    mock_service.get_weather_summary = AsyncMock()
    return mock_service


@pytest.fixture
def mock_weather_service():
    """Mock weather service for testing."""
    mock_service = AsyncMock()
    mock_service.get_current_weather = AsyncMock()
    return mock_service


@pytest.fixture
def sample_weather_record():
    """Sample weather record for testing with all required fields."""
    return WeatherRecord(
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


@pytest.fixture
def guardrail_output_weather_related():
    """Guardrail output indicating weather-related content."""
    return GuardrailOutput(
        is_weather_related=True,
        reasoning="The query is about weather conditions in a city."
    )


@pytest.fixture
def guardrail_output_not_weather_related():
    """Guardrail output indicating non-weather-related content."""
    return GuardrailOutput(
        is_weather_related=False,
        reasoning="The query is about sports scores, not weather."
    )


@pytest.fixture
def agent_response():
    """Sample agent response."""
    return AgentResponse(
        response="The weather in London is 15.5°C with partly cloudy conditions."
    )


@pytest.fixture
def mock_guardrail_agent_run():
    """Mock guardrail agent run method."""
    with patch('agent.guardrail_agent.guardrail_agent.run') as mock_run:
        mock_result = MagicMock()
        mock_result.final_output = GuardrailOutput(
            is_weather_related=True,
            reasoning="Weather query detected"
        )
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_runner_run():
    """Mock agents Runner.run method."""
    with patch('agents.Runner.run') as mock_run:
        mock_result = MagicMock()
        mock_result.final_output = AgentResponse(
            response="Weather information response"
        )
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_config():
    """Mock the config object."""
    with patch('src.config.config') as mock_config:
        mock_config.openai_api_key = "test-openai-key"
        mock_config.openweather_api_key = "test-weather-key"
        mock_config.openweather_base_url = "https://api.openweathermap.org/data/2.5/weather"
        mock_config.openweather_units = "metric"
        mock_config.google_project_id = "test-project"
        mock_config.cities_to_monitor = 5
        yield mock_config


@pytest.fixture
def mock_run_context():
    """Mock RunContextWrapper for guardrail testing."""
    mock_ctx = MagicMock()
    mock_ctx.context = MagicMock()
    return mock_ctx

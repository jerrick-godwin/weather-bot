# Testing Guide for Weather Bot

This document provides comprehensive guidance on how to perform test cases for the Weather Bot application. It covers test setup, patterns, best practices, and execution strategies.

## Table of Contents

1. [Test Structure Overview](#test-structure-overview)
2. [Test Environment Setup](#test-environment-setup)
3. [Test Fixtures and Mocking](#test-fixtures-and-mocking)
4. [Test Types and Patterns](#test-types-and-patterns)
5. [Writing Effective Tests](#writing-effective-tests)
6. [Running Tests](#running-tests)
7. [Test Coverage and Quality](#test-coverage-and-quality)
8. [Best Practices](#best-practices)

## Test Structure Overview

The Weather Bot uses **pytest** as the primary testing framework with the following structure:

```
tests/
├── __init__.py                 # Makes tests a Python package
├── conftest.py                 # Shared fixtures and configuration
├── test_guardrail_agent.py     # Tests for guardrail functionality
├── test_weather_agent.py       # Tests for weather agent logic
└── test_weather_service.py     # Tests for weather service API calls
```

### Key Testing Dependencies

- **pytest**: Main testing framework
- **pytest-asyncio**: Support for async/await testing
- **pytest-cov**: Code coverage reporting
- **unittest.mock**: Mocking and patching utilities

## Test Environment Setup

### Prerequisites

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**: 
   - Tests use mocked configurations, so no real API keys are required
   - The `mock_config` fixture provides test-safe configuration values

### Project Structure for Testing

Tests are organized to mirror the source code structure:
- `src/services/` → `tests/test_*_service.py`
- `agent/` → `tests/test_*_agent.py`

## Test Fixtures and Mocking

### Core Fixtures (from conftest.py)

#### 1. Event Loop Management
```python
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

#### 2. Mock Services
```python
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
```

#### 3. Sample Data
```python
@pytest.fixture
def sample_weather_record():
    """Sample weather record for testing with all required fields."""
    return WeatherRecord(
        city_id=2643743,
        city_name="London",
        country_code="GB",
        latitude=51.5074,
        longitude=-0.1278,
        # ... additional fields
    )
```

#### 4. Configuration Mocking
```python
@pytest.fixture
def mock_config():
    """Mock the config object."""
    with patch('src.config.config') as mock_config:
        mock_config.openai_api_key = "test-openai-key"
        mock_config.openweather_api_key = "test-weather-key"
        mock_config.openweather_base_url = "https://api.openweathermap.org/data/2.5/weather"
        # ... additional config values
        yield mock_config
```

### Mocking Strategies

#### 1. Service-Level Mocking
```python
# Mock at the service import level
with patch('src.services.weather_service.config', mock_config):
    service = WeatherService()
```

#### 2. Method-Level Mocking
```python
# Mock specific methods
with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_make_request:
    mock_make_request.return_value = mock_response_data
    result = await service.get_current_weather("London")
```

#### 3. External API Mocking
```python
# Mock HTTP client
with patch('httpx.AsyncClient') as mock_client_class:
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"weather": "data"}
    mock_client.get.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client
```

## Test Types and Patterns

### 1. Unit Tests

Test individual methods and functions in isolation.

**Example: Testing API Request Logic**
```python
@pytest.mark.asyncio
async def test_make_request_success(self, mock_config):
    """Test successful API request."""
    WeatherService._instances = {}  # Reset singleton
    
    with patch('src.services.weather_service.config', mock_config):
        service = WeatherService()
        
        mock_response_data = {"weather": "data"}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Execute test
            result = await service._make_request({"q": "London"})
            
            # Assertions
            assert result == mock_response_data
            mock_client.get.assert_called_once()
```

### 2. Integration Tests

Test interactions between multiple components.

**Example: Testing Service Integration**
```python
@pytest.mark.asyncio
async def test_get_weather_batch_success(self, mock_config):
    """Test successful batch weather fetch."""
    WeatherService._instances = {}
    
    service = WeatherService()
    
    # Create mock data
    mock_weather_record = WeatherRecord(...)
    
    with patch.object(service, 'get_current_weather', new_callable=AsyncMock) as mock_get_weather:
        mock_get_weather.return_value = mock_weather_record
        
        cities = ["London", "Paris", "Berlin"]
        result = await service.get_weather_batch(cities, max_concurrent=2)
        
        assert len(result) == 3
        assert all(isinstance(record, WeatherRecord) for record in result)
        assert mock_get_weather.call_count == 3
```

### 3. Exception Testing

Test error handling and edge cases.

**Example: Testing API Error Responses**
```python
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
```

### 4. Async Testing

All async methods must be decorated with `@pytest.mark.asyncio`.

**Example: Testing Async Methods**
```python
@pytest.mark.asyncio
async def test_async_method(self):
    """Test an async method."""
    # Test implementation
    result = await some_async_function()
    assert result is not None
```

### 5. Retry Logic Testing

Test retry mechanisms and timeout handling.

**Example: Testing Retry Logic**
```python
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
```

## Writing Effective Tests

### Test Structure Pattern

Follow the **Arrange-Act-Assert** pattern:

```python
@pytest.mark.asyncio
async def test_example(self, mock_config):
    """Test description explaining what is being tested."""
    # ARRANGE: Setup test data and mocks
    WeatherService._instances = {}  # Reset singleton if needed
    service = WeatherService()
    mock_data = {"expected": "response"}
    
    # ACT: Execute the code under test
    with patch('some.module.function') as mock_function:
        mock_function.return_value = mock_data
        result = await service.method_under_test()
    
    # ASSERT: Verify the results
    assert result == expected_result
    mock_function.assert_called_once_with(expected_args)
```

### Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<method_name>_<scenario>`

**Examples:**
- `test_make_request_success`
- `test_make_request_timeout_retry`
- `test_get_current_weather_validation_error`

### Test Documentation

Each test should have a clear docstring explaining:
- What is being tested
- The expected behavior
- Any special conditions or edge cases

```python
@pytest.mark.asyncio
async def test_make_request_rate_limit(self, mock_config):
    """Test API request with 429 response.
    
    Verifies that the service properly handles rate limit errors
    by raising a RateLimitError exception when the API returns
    a 429 status code.
    """
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_weather_service.py

# Run specific test class
pytest tests/test_weather_service.py::TestWeatherService

# Run specific test method
pytest tests/test_weather_service.py::TestWeatherService::test_make_request_success
```

### Test Options

```bash
# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=src --cov-report=html

# Run tests in parallel (if pytest-xdist is installed)
pytest -n auto

# Stop on first failure
pytest -x

# Show local variables in tracebacks
pytest -l

# Run only failed tests from last run
pytest --lf
```

### Async Test Configuration

Ensure `pytest-asyncio` is properly configured in `pytest.ini` or `pyproject.toml`:

```ini
[tool:pytest]
asyncio_mode = auto
```

## Test Coverage and Quality

### Coverage Analysis

```bash
# Generate coverage report
pytest --cov=src --cov-report=html --cov-report=term

# View coverage in browser
open htmlcov/index.html
```

### Coverage Goals

- **Minimum**: 80% overall coverage
- **Target**: 90%+ for critical components
- **Focus Areas**: 
  - Service classes (weather_service, bigquery_service)
  - Agent logic (weather_agent, guardrail_agent)
  - Error handling paths

### Quality Metrics

Monitor these test quality indicators:
- **Test execution time**: Keep individual tests under 1 second
- **Test isolation**: Tests should not depend on each other
- **Mock usage**: Prefer mocking external dependencies
- **Assertion clarity**: Use specific, meaningful assertions


## Best Practices

### 1. Test Independence
- Each test should be completely independent
- Use fixtures to provide clean state
- Reset singletons between tests

### 2. Mock External Dependencies
- Always mock external APIs (OpenWeather, BigQuery)
- Mock file system operations
- Mock time-dependent operations

### 3. Test Edge Cases
- Test error conditions
- Test boundary values
- Test timeout scenarios
- Test rate limiting

---

For specific implementation details, refer to the existing test files in the `tests/` directory, which demonstrate these patterns in practice.

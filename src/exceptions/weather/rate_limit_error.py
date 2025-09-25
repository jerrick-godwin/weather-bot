from src.exceptions.weather.weather_service_error import WeatherServiceError


class RateLimitError(WeatherServiceError):
    """Exception for API rate limit errors."""

    pass

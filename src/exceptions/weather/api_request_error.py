from src.exceptions.weather.weather_service_error import WeatherServiceError


class APIRequestError(WeatherServiceError):
    """Exception for errors during API requests."""

    pass

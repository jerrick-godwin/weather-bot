from src.exceptions.weather.weather_service_error import WeatherServiceError


class InvalidCityError(WeatherServiceError):
    """Exception for invalid or not found city names."""

    pass

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator, field_validator


class WeatherCondition(BaseModel):
    """Weather condition details."""

    id: int = Field(..., description="Weather condition ID")
    main: str = Field(..., description="Main weather condition (e.g., Rain, Snow, Clear)")
    description: str = Field(..., description="Detailed weather description")
    icon: str = Field(..., description="Weather icon code")


class MainWeatherData(BaseModel):
    """Main weather measurements."""

    temp: float = Field(..., description="Current temperature")
    feels_like: float = Field(..., description="Human perception of temperature")
    temp_min: float = Field(..., description="Minimum temperature")
    temp_max: float = Field(..., description="Maximum temperature")
    pressure: int = Field(..., description="Atmospheric pressure in hPa")
    humidity: int = Field(..., ge=0, le=100, description="Humidity percentage")
    sea_level: Optional[int] = Field(None, description="Sea level pressure in hPa")
    grnd_level: Optional[int] = Field(None, description="Ground level pressure in hPa")


class WindData(BaseModel):
    """Wind information."""

    speed: float = Field(..., ge=0, description="Wind speed in m/s")
    deg: Optional[int] = Field(None, ge=0, le=360, description="Wind direction in degrees")
    gust: Optional[float] = Field(None, ge=0, description="Wind gust speed in m/s")


class CloudData(BaseModel):
    """Cloud information."""

    all: int = Field(..., ge=0, le=100, description="Cloudiness percentage")


class RainData(BaseModel):
    """Rain information."""

    one_hour: Optional[float] = Field(
        None, alias="1h", description="Rain volume for last hour in mm"
    )
    three_hours: Optional[float] = Field(
        None, alias="3h", description="Rain volume for last 3 hours in mm"
    )


class SnowData(BaseModel):
    """Snow information."""

    one_hour: Optional[float] = Field(
        None, alias="1h", description="Snow volume for last hour in mm"
    )
    three_hours: Optional[float] = Field(
        None, alias="3h", description="Snow volume for last 3 hours in mm"
    )


class SystemData(BaseModel):
    """System information from API response."""

    type: Optional[int] = Field(None, description="Internal parameter")
    id: Optional[int] = Field(None, description="Internal parameter")
    country: str = Field(..., description="Country code (e.g., US, GB)")
    sunrise: int = Field(..., description="Sunrise time in Unix timestamp")
    sunset: int = Field(..., description="Sunset time in Unix timestamp")


class Coordinates(BaseModel):
    """Geographic coordinates."""

    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")


class OpenWeatherMapResponse(BaseModel):
    """Complete OpenWeatherMap API response model."""

    coord: Coordinates = Field(..., description="Geographic coordinates")
    weather: List[WeatherCondition] = Field(..., description="Weather conditions")
    base: str = Field(..., description="Internal parameter")
    main: MainWeatherData = Field(..., description="Main weather data")
    visibility: Optional[int] = Field(None, description="Visibility in meters")
    wind: Optional[WindData] = Field(None, description="Wind information")
    clouds: Optional[CloudData] = Field(None, description="Cloud information")
    rain: Optional[RainData] = Field(None, description="Rain information")
    snow: Optional[SnowData] = Field(None, description="Snow information")
    dt: int = Field(..., description="Data calculation time in Unix timestamp")
    sys: SystemData = Field(..., description="System information")
    timezone: int = Field(..., description="Shift in seconds from UTC")
    id: int = Field(..., description="City ID")
    name: str = Field(..., description="City name")
    cod: int = Field(..., description="Internal parameter")


class WeatherRecord(BaseModel):
    """Processed weather record for database storage."""

    city_id: int = Field(..., description="OpenWeatherMap city ID")
    city_name: str = Field(..., description="City name")
    country_code: str = Field(..., description="Country code")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    base: Optional[str] = Field(None, description="OpenWeatherMap response base field")

    # Weather measurements
    temperature: float = Field(..., description="Temperature in Celsius")
    feels_like: float = Field(..., description="Feels like temperature in Celsius")
    temp_min: float = Field(..., description="Minimum temperature")
    temp_max: float = Field(..., description="Maximum temperature")
    pressure: int = Field(..., description="Atmospheric pressure in hPa")
    humidity: int = Field(..., ge=0, le=100, description="Humidity percentage")
    sea_level_pressure: Optional[int] = Field(None, description="Sea level pressure in hPa")
    ground_level_pressure: Optional[int] = Field(None, description="Ground level pressure in hPa")

    # Weather conditions
    weather_condition_id: Optional[int] = Field(
        None, description="Weather condition ID provided by OpenWeatherMap"
    )
    weather_main: str = Field(..., description="Main weather condition")
    weather_description: str = Field(..., description="Weather description")
    weather_icon: str = Field(..., description="Weather icon code")
    weather_conditions: List[WeatherCondition] = Field(
        default_factory=list,
        description="Full list of weather conditions from the API response",
    )

    # Optional measurements
    visibility: Optional[int] = Field(None, description="Visibility in meters")
    cloudiness: Optional[int] = Field(None, description="Cloudiness percentage")
    wind_speed: Optional[float] = Field(None, description="Wind speed in m/s")
    wind_direction: Optional[int] = Field(None, description="Wind direction in degrees")
    wind_gust: Optional[float] = Field(None, description="Wind gust speed")
    rain_1h: Optional[float] = Field(None, description="Rain in last hour (mm)")
    rain_3h: Optional[float] = Field(None, description="Rain in last 3 hours (mm)")
    snow_1h: Optional[float] = Field(None, description="Snow in last hour (mm)")
    snow_3h: Optional[float] = Field(None, description="Snow in last 3 hours (mm)")

    # Timestamps and timezone
    data_timestamp: datetime = Field(..., description="When the weather data was recorded")
    sunrise: datetime = Field(..., description="Sunrise time")
    sunset: datetime = Field(..., description="Sunset time")
    timezone_offset: Optional[int] = Field(None, description="Timezone offset from UTC in seconds")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Record creation time"
    )
    system_type: Optional[int] = Field(None, description="System type metadata from API")
    system_id: Optional[int] = Field(None, description="System ID metadata from API")
    cod: Optional[int] = Field(None, description="OpenWeatherMap response code")

    @field_validator("data_timestamp", "sunrise", "sunset", mode="before")
    def parse_timestamps(cls, v):
        """Convert Unix timestamps to datetime objects."""
        if isinstance(v, int):
            return datetime.fromtimestamp(v)
        return v

    @classmethod
    def from_openweather_response(cls, response: OpenWeatherMapResponse) -> "WeatherRecord":
        """
        Create a WeatherRecord from OpenWeatherMap API response.

        Args:
            response: OpenWeatherMap API response

        Returns:
            WeatherRecord: Processed weather record
        """
        primary_weather = response.weather[0] if response.weather else None

        return cls(
            city_id=response.id,
            city_name=response.name,
            country_code=response.sys.country,
            latitude=response.coord.lat,
            longitude=response.coord.lon,
            base=response.base,
            temperature=response.main.temp,
            feels_like=response.main.feels_like,
            temp_min=response.main.temp_min,
            temp_max=response.main.temp_max,
            pressure=response.main.pressure,
            humidity=response.main.humidity,
            sea_level_pressure=response.main.sea_level,
            ground_level_pressure=response.main.grnd_level,
            weather_condition_id=primary_weather.id if primary_weather else None,
            weather_main=primary_weather.main if primary_weather else "Unknown",
            weather_description=(
                primary_weather.description if primary_weather else "No description"
            ),
            weather_icon=primary_weather.icon if primary_weather else "unknown",
            weather_conditions=response.weather,
            visibility=response.visibility,
            cloudiness=response.clouds.all if response.clouds else None,
            wind_speed=response.wind.speed if response.wind else None,
            wind_direction=response.wind.deg if response.wind else None,
            wind_gust=response.wind.gust if response.wind else None,
            rain_1h=response.rain.one_hour if response.rain else None,
            rain_3h=response.rain.three_hours if response.rain else None,
            snow_1h=response.snow.one_hour if response.snow else None,
            snow_3h=response.snow.three_hours if response.snow else None,
            data_timestamp=datetime.fromtimestamp(response.dt),
            sunrise=datetime.fromtimestamp(response.sys.sunrise),
            sunset=datetime.fromtimestamp(response.sys.sunset),
            timezone_offset=response.timezone,
            system_type=response.sys.type,
            system_id=response.sys.id,
            cod=response.cod,
        )

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.exceptions.openai.openai_key_error import OpenAIKeyError

from agents._config import set_default_openai_key

from src.exceptions.weather.api_key_error import WeatherAPIKeyError


class Config(BaseSettings):
    """
    Application settings loaded from environment variables and .env files.

    This class handles all configuration for the weather bot system including
    API keys, database connections, and scheduling parameters.
    """

    # API Keys
    openai_api_key: str = Field(..., description="OpenAI API key for agent functionality")
    openweather_api_key: str = Field(..., description="OpenWeatherMap API key for weather data")

    # BigQuery Configuration
    google_project_id: str = Field(..., description="Google Cloud Project ID")
    bigquery_dataset: str = Field(..., description="BigQuery dataset name")
    bigquery_table: str = Field(..., description="BigQuery table name")
    google_service_account_file: str = Field(..., description="Path to Google service account JSON file")

    # GCP Authentication
    gcp_auth_base_url: str = Field(..., description="Base URL for Google Cloud Platform Authentication")
    
    # OpenWeatherMap Configuration
    openweather_base_url: str = Field(..., description="OpenWeatherMap API base URL")
    openweather_units: str = Field(..., description="Temperature units (metric/imperial)")

    # Scheduling Configuration
    cronjob_start_hour: int = Field(..., ge=0, le=23, description="Hour to start cron jobs")
    cronjob_start_minute: int = Field(..., ge=0, le=59, description="Minute to start cron jobs")
    update_interval_hours: int = Field(..., ge=1, description="Hours between weather updates")

    # Data Configuration
    cities_to_monitor: int = Field(..., ge=1, description="Number of cities to monitor")
    backfill_months: int = Field(..., ge=1, description="Months of historical data to backfill")

    # API Configuration
    api_host: str = Field(..., description="FastAPI host")
    api_port: int = Field(..., ge=1, le=65535, description="FastAPI port")
    api_token: Optional[str] = Field(default=None, description="API authentication token")

    # Logging Configuration
    environment: str = Field(..., description="Environment name")
    log_level: str = Field(..., description="Logging level")
    log_format: str = Field(..., description="Log format (json/text)")

    @field_validator("openai_api_key")
    def validate_openai_api_key(cls, v):
        # Check whether OpenAI Key is provided
        if not v:
            raise OpenAIKeyError("OpenAI API key is required")

        # Set OpenAI API key as environment variable for the agents library
        os.environ["OPENAI_API_KEY"] = v

        # Configure default OpenAI client for the agents SDK
        set_default_openai_key(v, use_for_tracing=False)
        return v

    @field_validator("openweather_api_key")
    def validate_openweather_api_key(cls, v):
        if not v:
            raise WeatherAPIKeyError("Weather API key is required")
        return v

    @field_validator("google_service_account_file")
    def validate_service_account_file(cls, v):
        """Validate that the Google service account file exists."""
        if not os.path.exists(v):
            raise ValueError(f"Google service account file not found: {v}")
        return v

    @field_validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()

    def get_google_credentials_path(self) -> Path:
        """Get the absolute path to Google service account credentials."""
        return Path(self.google_service_account_file).resolve()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


config = Config()

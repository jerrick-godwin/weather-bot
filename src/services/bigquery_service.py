from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from google.oauth2 import service_account

from src.config.config import config
from src.exceptions.bigquery import (
    BigQueryServiceError,
    DataInsertionError,
    QueryExecutionError,
    TableCreationError,
)
from src.models.weather.weather import WeatherCondition, WeatherRecord
from src.utils.singleton import Singleton

logger = structlog.get_logger(__name__)


class BigQueryService(Singleton):
    """
    Service for managing weather data in Google BigQuery.

    This service provides methods for creating tables, inserting weather data,
    querying historical data, and ensuring data integrity with idempotency.
    """

    def __init__(self):
        """Initialize the BigQuery service."""
        super().__init__()

        if hasattr(self, "_bigquery_initialized"):
            return

        self.project_id = config.google_project_id
        self.dataset_id = config.bigquery_dataset
        self.table_id = config.bigquery_table

        # Initialize BigQuery client
        self.client = self._initialize_client()

        # Table and dataset references
        self.dataset_ref = bigquery.DatasetReference(
            project=self.client.project,
            dataset_id=self.dataset_id
        )
        self.table_ref = bigquery.TableReference(
            dataset_ref=self.dataset_ref,
            table_id=self.table_id
        )

        self._bigquery_initialized = True

        logger.info(
            "BigQuery service initialized",
            project_id=self.project_id,
            dataset_id=self.dataset_id,
            table_id=self.table_id,
        )

    def _initialize_client(self) -> bigquery.Client:
        """
        Initialize BigQuery client with service account credentials.

        Returns:
            Configured BigQuery client

        Raises:
            DatabaseServiceError: If client initialization fails
        """
        try:
            credentials_path = config.get_google_credentials_path()

            if not credentials_path.exists():
                raise BigQueryServiceError(f"Service account file not found: {credentials_path}")

            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                filename=str(credentials_path), 
                scopes=[config.gcp_auth_base_url]
            )

            # Create BigQuery client
            client = bigquery.Client(credentials=credentials, project=self.project_id)

            logger.info("BigQuery client initialized successfully")
            return client

        except Exception as e:
            logger.error("Failed to initialize BigQuery client", error=str(e))
            raise BigQueryServiceError(f"Failed to initialize BigQuery client: {str(e)}")

    @classmethod
    def _get_table_schema(cls) -> List[bigquery.SchemaField]:
        """
        Define the BigQuery table schema for weather records.

        Returns:
            List of BigQuery schema fields
        """
        return [
            bigquery.SchemaField(
                "coord",
                "RECORD",
                mode="NULLABLE",
                fields=[
                    bigquery.SchemaField("lon", "FLOAT", mode="NULLABLE"),
                    bigquery.SchemaField("lat", "FLOAT", mode="NULLABLE"),
                ],
            ),
            bigquery.SchemaField(
                "weather",
                "RECORD",
                mode="REPEATED",
                fields=[
                    bigquery.SchemaField("id", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("main", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("icon", "STRING", mode="NULLABLE"),
                ],
            ),
            bigquery.SchemaField("base", "STRING", mode="NULLABLE"),
            bigquery.SchemaField(
                "main",
                "RECORD",
                mode="NULLABLE",
                fields=[
                    bigquery.SchemaField("temp", "FLOAT", mode="NULLABLE"),
                    bigquery.SchemaField("feels_like", "FLOAT", mode="NULLABLE"),
                    bigquery.SchemaField("temp_min", "FLOAT", mode="NULLABLE"),
                    bigquery.SchemaField("temp_max", "FLOAT", mode="NULLABLE"),
                    bigquery.SchemaField("pressure", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("humidity", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("sea_level", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("grnd_level", "INTEGER", mode="NULLABLE"),
                ],
            ),
            bigquery.SchemaField("visibility", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField(
                "wind",
                "RECORD",
                mode="NULLABLE",
                fields=[
                    bigquery.SchemaField("speed", "FLOAT", mode="NULLABLE"),
                    bigquery.SchemaField("deg", "INTEGER", mode="NULLABLE"),
                ],
            ),
            bigquery.SchemaField(
                "clouds",
                "RECORD",
                mode="NULLABLE",
                fields=[
                    bigquery.SchemaField("all", "INTEGER", mode="NULLABLE"),
                ],
            ),
            bigquery.SchemaField("dt", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField(
                "sys",
                "RECORD",
                mode="NULLABLE",
                fields=[
                    bigquery.SchemaField("type", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("id", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("country", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("sunrise", "TIMESTAMP", mode="NULLABLE"),
                    bigquery.SchemaField("sunset", "TIMESTAMP", mode="NULLABLE"),
                ],
            ),
            bigquery.SchemaField("timezone", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("api_city_id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("cod", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
        ]

    async def initialize_database(self) -> bool:
        """
        Initialize the database by creating dataset and table if they don't exist.

        Returns:
            True if initialization successful, False otherwise

        Raises:
            TableCreationError: If table creation fails
        """
        try:
            # Create dataset if it doesn't exist
            await self._create_dataset_if_not_exists()

            # Create table if it doesn't exist
            await self._create_table_if_not_exists()

            logger.info("Database initialization completed successfully")
            return True

        except Exception as e:
            logger.error("Database initialization failed", error=str(e))
            raise TableCreationError(f"Failed to initialize database: {str(e)}")

    async def _create_dataset_if_not_exists(self):
        """Create BigQuery dataset if it doesn't exist."""
        try:
            # Check if dataset exists
            self.client.get_dataset(self.dataset_ref)
            logger.info(
                "Dataset already exists",
                dataset_id=self.dataset_id
            )

        except NotFound:
            # Create dataset
            dataset = bigquery.Dataset(self.dataset_ref)    # type: ignore[arg-type]
            dataset.location = "US" # Default fallback to US
            dataset.description = "Weather data collected from OpenWeatherMap API"

            _ = self.client.create_dataset(
                dataset=dataset,
                timeout=30
            )
            logger.info(
                "Dataset created successfully",
                dataset_id=self.dataset_id
            )

        except Exception as e:
            logger.error("Failed to create dataset", error=str(e))
            raise

    async def _create_table_if_not_exists(self):
        """Create BigQuery table if it doesn't exist."""
        try:
            # Check if table exists
            table = self.client.get_table(self.table_ref)
            logger.info(
                "Table already exists",
                table_id=self.table_id
            )

            # Verify whether the schema presents required fields
            self._ensure_table_schema(table)

        except NotFound:
            # Create table
            table_schema = self._get_table_schema()
            table = bigquery.Table(
                self.table_ref, # type: ignore[arg-type]
                schema=table_schema
            )
            table.description = "Weather records from OpenWeatherMap API"

            # Set up partitioning by dt for better performance
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,    # type: ignore[arg-type]
                field="dt"  # type: ignore[arg-type]
            )

            # Set up clustering for better query performance
            table.clustering_fields = ["sys.country", "api_city_id", "dt"]

            _ = self.client.create_table(table, timeout=30)
            logger.info("Table created successfully", table_id=self.table_id)

        except Exception as e:
            logger.error("Failed to create table", error=str(e))
            raise

    def _ensure_table_schema(self, table: bigquery.Table):
        """Ensure the BigQuery table schema includes all required fields."""
        try:
            existing_fields = {field.name for field in table.schema}
            required_fields = self._get_table_schema()

            new_fields = [field for field in required_fields if field.name not in existing_fields]

            if not new_fields:
                return

            updated_schema = list(table.schema) + new_fields
            table.schema = updated_schema
            self.client.update_table(table, ["schema"])

            logger.info(
                "BigQuery table schema updated",
                added_fields=[field.name for field in new_fields],
                table_id=self.table_id,
            )

        except Exception as e:
            logger.error("Failed to update table schema", error=str(e))
            raise

    @classmethod
    def _weather_record_to_dict(cls, record: WeatherRecord) -> Dict[str, Any]:
        """
        Convert WeatherRecord to dictionary for BigQuery insertion.

        Args:
            record: WeatherRecord to convert

        Returns:
            Dictionary representation suitable for BigQuery
        """
        # Helper to format timestamps as ISO 8601 strings in UTC for JSON serialization
        def _ts(v):
            if v is None:
                return None
            if isinstance(v, datetime):
                # Assume naive datetime are UTC
                if v.tzinfo is None:
                    v = v.replace(tzinfo=timezone.utc)
                else:
                    v = v.astimezone(timezone.utc)
                return v.isoformat()

            # Allow pre-formatted strings to pass through
            return v

        coord = None
        if record.longitude is not None or record.latitude is not None:
            coord = {
                "lon": record.longitude,
                "lat": record.latitude,
            }

        weather_conditions = record.weather_conditions
        if not weather_conditions and record.weather_main:
            weather_conditions = [
                WeatherCondition(
                    id=record.weather_condition_id or 0,
                    main=record.weather_main,
                    description=record.weather_description,
                    icon=record.weather_icon,
                )
            ]

        main_block = {
            "temp": record.temperature,
            "feels_like": record.feels_like,
            "temp_min": record.temp_min,
            "temp_max": record.temp_max,
            "pressure": record.pressure,
            "humidity": record.humidity,
            "sea_level": record.sea_level_pressure,
            "grnd_level": record.ground_level_pressure,
        }

        wind_block = None
        if record.wind_speed is not None or record.wind_direction is not None:
            wind_block = {
                "speed": record.wind_speed,
                "deg": record.wind_direction,
            }

        clouds_block = None
        if record.cloudiness is not None:
            clouds_block = {"all": record.cloudiness}

        sys_block = {
            "type": record.system_type,
            "id": record.system_id,
            "country": record.country_code,
            "sunrise": _ts(record.sunrise),
            "sunset": _ts(record.sunset),
        }
        weather_array = [condition.model_dump() for condition in weather_conditions]

        return {
            "coord": coord,
            "weather": weather_array,
            "base": record.base,
            "main": main_block,
            "visibility": record.visibility,
            "wind": wind_block,
            "clouds": clouds_block,
            "dt": _ts(record.data_timestamp),
            "sys": sys_block,
            "timezone": record.timezone_offset,
            "api_city_id": record.city_id,
            "name": record.city_name,
            "cod": record.cod,
            "ingested_at": _ts(record.created_at),
        }

    async def insert_weather_records(
            self,
            records: List[WeatherRecord],
            ignore_duplicates: bool = True
    ) -> int:
        """
        Insert weather records into BigQuery with idempotency.

        Args:
            records: List of WeatherRecord objects to insert
            ignore_duplicates: If True, ignore duplicate records based on country, city ID, and timestamp

        Returns:
            Number of records successfully inserted

        Raises:
            DataInsertionError: If insertion fails
        """
        logger.info(
            "Starting weather records insertion",
           record_count=len(records),
           ignore_duplicates=ignore_duplicates
        )
        
        if not records:
            logger.info("No records to insert")
            return 0

        try:
            # Convert records to dictionaries
            rows_to_insert = [self._weather_record_to_dict(record) for record in records]

            if ignore_duplicates:
                # Use MERGE statement for idempotency
                return await self._insert_with_merge(rows_to_insert)
            else:
                # Direct insertion
                return await self._insert_direct(rows_to_insert)

        except Exception as e:
            logger.error(
                "Failed to insert weather records", error=str(e), record_count=len(records)
            )
            raise DataInsertionError(f"Failed to insert weather records: {str(e)}")

    async def _insert_with_merge(self, rows: List[Dict[str, Any]]) -> int:
        """Insert records using MERGE statement for idempotency based on country, city ID, and timestamp."""
        if not rows:
            return 0

        # Create temporary table for staging data
        temp_table_id = f"temp_weather_{int(datetime.now().timestamp())}"
        temp_table_ref = self.dataset_ref.table(temp_table_id)  # type: ignore[arg-type]

        try:
            # Create temporary table
            table_schema = self._get_table_schema()
            temp_table = bigquery.Table(
                temp_table_ref,     # type: ignore[arg-type]
                schema=table_schema
            )
            temp_table = self.client.create_table(temp_table)

            # Insert data into temporary table
            errors = self.client.insert_rows_json(temp_table, rows)
            if errors:
                logger.error("Failed to insert into temporary table", errors=errors)
                raise DataInsertionError(f"Temporary table insertion failed: {errors}")

            # Use MERGE to insert/update data idempotently
            # Using country, city ID, and timestamp as composite key for duplicate entry detection
            merge_query = f"""
            MERGE `{self.project_id}.{self.dataset_id}.{self.table_id}` AS target
            USING `{self.project_id}.{self.dataset_id}.{temp_table_id}` AS source
            ON target.sys.country = source.sys.country 
               AND target.api_city_id = source.api_city_id
               AND target.dt = source.dt
            WHEN MATCHED THEN
              UPDATE SET
                coord = source.coord,
                weather = source.weather,
                base = source.base,
                main = source.main,
                visibility = source.visibility,
                wind = source.wind,
                clouds = source.clouds,
                sys = source.sys,
                timezone = source.timezone,
                api_city_id = source.api_city_id,
                cod = source.cod,
                ingested_at = source.ingested_at
            WHEN NOT MATCHED THEN
              INSERT ROW
            """

            query_job = self.client.query(merge_query)
            result = query_job.result()

            inserted_count = query_job.num_dml_affected_rows or 0
            logger.info("Records merged successfully", inserted_count=inserted_count)

            return inserted_count

        finally:
            # Clean up temporary table
            try:
                self.client.delete_table(temp_table_ref, not_found_ok=True)
            except Exception as e:
                logger.warning("Failed to delete temporary table", error=str(e))

    async def _insert_direct(self, rows: List[Dict[str, Any]]) -> int:
        """Insert records directly without duplicate checking."""
        errors = self.client.insert_rows_json(self.client.get_table(self.table_ref), rows)

        if errors:
            logger.error("Direct insertion failed", errors=errors)
            raise DataInsertionError(f"Direct insertion failed: {errors}")

        logger.info("Records inserted successfully", record_count=len(rows))
        return len(rows)

    async def get_latest_weather(self, city: str) -> Optional[WeatherRecord]:
        """
        Get the latest weather record for a city.

        Args:
            city: Name of the city

        Returns:
            Latest WeatherRecord or None if not found

        Raises:
            QueryExecutionError: If query execution fails
        """
        try:
            query = f"""
            SELECT *
            FROM `{self.project_id}.{self.dataset_id}.{self.table_id}`
            WHERE LOWER(name) = LOWER(@city)
            ORDER BY dt DESC
            LIMIT 1
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("city", "STRING", city)]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            if not results:
                logger.info("No weather data found for city", city=city)
                return None

            row = results[0]
            weather_record = self._row_to_weather_record(row)

            logger.info("Latest weather retrieved successfully", city=city)
            return weather_record

        except Exception as e:
            logger.error("Failed to get latest weather", city=city, error=str(e))
            raise QueryExecutionError(f"Failed to get latest weather for {city}: {str(e)}")

    async def get_weather_history(self, city: str, days: int = 7) -> List[WeatherRecord]:
        """
        Get historical weather records for a city.

        Args:
            city: Name of the city
            days: Number of days of history to retrieve

        Returns:
            List of WeatherRecord objects ordered by timestamp

        Raises:
            QueryExecutionError: If query execution fails
        """
        try:
            query = f"""
            SELECT *
            FROM `{self.project_id}.{self.dataset_id}.{self.table_id}`
            WHERE LOWER(name) = LOWER(@city)
              AND dt >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            ORDER BY dt DESC
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("city", "STRING", city),
                    bigquery.ScalarQueryParameter("days", "INT64", days),
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            weather_records = [self._row_to_weather_record(row) for row in results]

            logger.info(
                "Weather history retrieved successfully",
                city=city,
                days=days,
                record_count=len(weather_records),
            )

            return weather_records

        except Exception as e:
            logger.error("Failed to get weather history", city=city, days=days, error=str(e))
            raise QueryExecutionError(f"Failed to get weather history for {city}: {str(e)}")

    @classmethod
    def _row_to_weather_record(cls, row) -> WeatherRecord:
        """Convert BigQuery row to WeatherRecord."""
        coord = row.get("coord") if hasattr(row, "get") else None
        coord = dict(coord.items()) if coord is not None and hasattr(coord, "items") else coord

        main = row.get("main") if hasattr(row, "get") else None
        main = dict(main.items()) if main is not None and hasattr(main, "items") else main or {}

        wind = row.get("wind") if hasattr(row, "get") else None
        wind = dict(wind.items()) if wind is not None and hasattr(wind, "items") else wind or {}

        clouds = row.get("clouds") if hasattr(row, "get") else None
        clouds = dict(clouds.items()) if clouds is not None and hasattr(clouds, "items") else clouds or {}

        sys_block = row.get("sys") if hasattr(row, "get") else None
        sys_block = dict(sys_block.items()) if sys_block is not None and hasattr(sys_block, "items") else sys_block or {}

        weather_list = row.get("weather") if hasattr(row, "get") else []
        weather_conditions = []
        if weather_list:
            for condition in weather_list:
                condition_dict = (
                    dict(condition.items())
                    if condition is not None and hasattr(condition, "items")
                    else condition
                ) or {}
                try:
                    weather_conditions.append(WeatherCondition(**condition_dict))
                except Exception:
                    continue

        primary_weather = weather_conditions[0] if weather_conditions else None

        return WeatherRecord(
            city_id=row.get("api_city_id"),
            city_name=row.get("name"),
            country_code=sys_block.get("country"),
            latitude=(coord or {}).get("lat", 0.0),
            longitude=(coord or {}).get("lon", 0.0),
            base=row.get("base"),
            temperature=main.get("temp", 0.0),
            feels_like=main.get("feels_like", 0.0),
            temp_min=main.get("temp_min", 0.0),
            temp_max=main.get("temp_max", 0.0),
            pressure=main.get("pressure", 0),
            humidity=main.get("humidity", 0),
            sea_level_pressure=main.get("sea_level"),
            ground_level_pressure=main.get("grnd_level"),
            weather_condition_id=primary_weather.id if primary_weather else None,
            weather_main=primary_weather.main if primary_weather else "Unknown",
            weather_description=(
                primary_weather.description if primary_weather else "No description"
            ),
            weather_icon=primary_weather.icon if primary_weather else "unknown",
            weather_conditions=weather_conditions,
            visibility=row.get("visibility"),
            cloudiness=clouds.get("all"),
            wind_speed=wind.get("speed"),
            wind_direction=wind.get("deg"),
            wind_gust=None,
            rain_1h=None,
            rain_3h=None,
            snow_1h=None,
            snow_3h=None,
            data_timestamp=row.get("dt"),
            sunrise=sys_block.get("sunrise", datetime.now()),
            sunset=sys_block.get("sunset", datetime.now()),
            timezone_offset=row.get("timezone"),
            created_at=row.get("ingested_at"),
            system_type=sys_block.get("type"),
            system_id=sys_block.get("id"),
            cod=row.get("cod"),
        )

    async def get_weather_summary(self, city: str, days: int = 7) -> Dict[str, Any]:
        """
        Get weather summary statistics for a city.

        Args:
            city: Name of the city
            days: Number of days to analyze

        Returns:
            Dictionary with summary statistics
        """
        try:
            # Overall aggregates (non-grouped)
            overall_query = f"""
            SELECT 
                COUNT(*) as total_records,
                AVG(main.temp) as avg_temperature,
                MIN(main.temp) as min_temperature,
                MAX(main.temp) as max_temperature,
                AVG(main.humidity) as avg_humidity,
                AVG(main.pressure) as avg_pressure
            FROM `{self.project_id}.{self.dataset_id}.{self.table_id}`
            WHERE LOWER(name) = LOWER(@city)
              AND dt >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            """

            grouped_query = f"""
            SELECT 
                weather[SAFE_OFFSET(0)].main as weather_condition,
                COUNT(*) as condition_count
            FROM `{self.project_id}.{self.dataset_id}.{self.table_id}`
            WHERE LOWER(name) = LOWER(@city)
              AND dt >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            GROUP BY weather_condition
            ORDER BY condition_count DESC
            """

            job_params = [
                bigquery.ScalarQueryParameter("city", "STRING", city),
                bigquery.ScalarQueryParameter("days", "INT64", days),
            ]

            # Run overall aggregates
            overall_job = self.client.query(
                overall_query, job_config=bigquery.QueryJobConfig(query_parameters=job_params)
            )
            overall_rows = list(overall_job.result())
            overall = overall_rows[0] if overall_rows else None

            if not overall or overall.total_records == 0:
                return {"error": f"No data found for {city}"}

            total_records = overall.total_records

            # Run grouped distribution
            grouped_job = self.client.query(
                grouped_query, job_config=bigquery.QueryJobConfig(query_parameters=job_params)
            )
            grouped_results = list(grouped_job.result())

            conditions = [
                {
                    "condition": row.weather_condition or "Unknown",
                    "count": row.condition_count,
                    "percentage": (
                        (row.condition_count / total_records) * 100 if total_records else 0
                    ),
                }
                for row in grouped_results
            ]

            summary = {
                "city": city,
                "days_analyzed": days,
                "total_records": total_records,
                "avg_temperature": (
                    round(overall.avg_temperature, 2) if overall.avg_temperature else None
                ),
                "min_temperature": overall.min_temperature,
                "max_temperature": overall.max_temperature,
                "avg_humidity": (
                    round(overall.avg_humidity, 2) if overall.avg_humidity else None
                ),
                "avg_pressure": (
                    round(overall.avg_pressure, 2) if overall.avg_pressure else None
                ),
                "weather_conditions": conditions,
            }

            logger.info("Weather summary generated successfully", city=city, days=days)
            return summary

        except Exception as e:
            logger.error("Failed to get weather summary", city=city, days=days, error=str(e))
            raise QueryExecutionError(f"Failed to get weather summary for {city}: {str(e)}")

    async def check_backfill_status(self, cities: List[str], expected_days: int) -> Dict[str, Any]:
        """
        Check if historical data backfill is complete for given cities and date range.

        Args:
            cities: List of city names to check
            expected_days: Number of days of historical data expected

        Returns:
            Dictionary with backfill status information
        """
        try:
            lowercase_cities = [city.lower() for city in cities]

            if not lowercase_cities:
                return {
                    "is_backfill_complete": False,
                    "total_cities_expected": 0,
                    "cities_with_data": 0,
                    "complete_cities": 0,
                    "missing_cities": [],
                    "city_details": {},
                    "expected_days": expected_days,
                }

            query = f"""
            SELECT 
                name,
                COUNT(*) as record_count,
                MIN(DATE(dt)) as earliest_date,
                MAX(DATE(dt)) as latest_date,
                COUNT(DISTINCT DATE(dt)) as unique_days
            FROM `{self.project_id}.{self.dataset_id}.{self.table_id}`
            WHERE LOWER(name) IN UNNEST(@city_names)
              AND dt <= CURRENT_TIMESTAMP()
              AND dt >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @expected_days DAY)
            GROUP BY name
            ORDER BY name
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter(
                        name="city_names",   # type: ignore[arg-type]
                        array_type="STRING", # type: ignore[arg-type]
                        values=lowercase_cities
                    ),
                    bigquery.ScalarQueryParameter(
                        name="expected_days",
                        type_="INT64",
                        value=expected_days
                    ),
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            # Calculate backfill status for each city
            city_status = {}
            today_utc = datetime.now(timezone.utc).date()

            for row in results:
                earliest_date = row.earliest_date if row.earliest_date else None
                latest_date = row.latest_date if row.latest_date else None

                if earliest_date:
                    # `earliest_date` is already a date from BigQuery
                    days_since_first_record = (today_utc - earliest_date).days + 1
                else:
                    days_since_first_record = 0

                dynamic_expected_days = expected_days
                if days_since_first_record > 0:
                    dynamic_expected_days = min(expected_days, days_since_first_record)

                if dynamic_expected_days == 0 and row.record_count > 0:
                    dynamic_expected_days = 1

                completion_threshold = max(1, int(round(dynamic_expected_days * 0.9)))
                is_complete = row.unique_days >= completion_threshold

                city_status[row.name] = {
                    "record_count": row.record_count,
                    "earliest_date": earliest_date.isoformat() if earliest_date else None,
                    "latest_date": latest_date.isoformat() if latest_date else None,
                    "unique_days": row.unique_days,
                    "expected_days_target": dynamic_expected_days,
                    "completion_threshold": completion_threshold,
                    "is_complete": is_complete,
                }

            # Check for missing cities
            found_cities = {row.name.lower() for row in results}
            missing_cities = [city for city in cities if city.lower() not in found_cities]

            # Overall status
            cities_with_data = len(city_status)
            complete_cities = sum(
                1 for status in city_status.values() if status["is_complete"]
            )

            overall_status = {
                "is_backfill_complete": (
                    len(missing_cities) == 0 and 
                    complete_cities == len(cities) and
                    cities_with_data >= len(cities) * 0.9  # At least 90% of cities have data
                ),
                "total_cities_expected": len(cities),
                "cities_with_data": cities_with_data,
                "complete_cities": complete_cities,
                "missing_cities": missing_cities,
                "city_details": city_status,
                "expected_days": expected_days,
            }

            logger.info(
                "Backfill status check completed",
                total_cities=len(cities),
                cities_with_data=cities_with_data,
                complete_cities=complete_cities,
                is_complete=overall_status["is_backfill_complete"]
            )

            return overall_status

        except Exception as e:
            logger.error("Failed to check backfill status", error=str(e))
            raise QueryExecutionError(f"Failed to check backfill status: {str(e)}")

    async def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with database statistics
        """
        try:
            query = f"""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT api_city_id) as unique_cities,
                MIN(dt) as earliest_record,
                MAX(dt) as latest_record,
                COUNT(DISTINCT DATE(dt)) as unique_days
            FROM `{self.project_id}.{self.dataset_id}.{self.table_id}`
            """

            query_job = self.client.query(query)
            results = list(query_job.result())

            if not results:
                return {"error": "No data in database"}

            row = results[0]

            stats = {
                "total_records": row.total_records,
                "unique_cities": row.unique_cities,
                "earliest_record": row.earliest_record.isoformat() if row.earliest_record else None,
                "latest_record": row.latest_record.isoformat() if row.latest_record else None,
                "unique_days": row.unique_days,
                "project_id": self.project_id,
                "dataset_id": self.dataset_id,
                "table_id": self.table_id,
            }

            logger.info("Database statistics retrieved successfully")
            return stats

        except Exception as e:
            logger.error("Failed to get database statistics", error=str(e))
            raise QueryExecutionError(f"Failed to get database statistics: {str(e)}")


bigquery_service = BigQueryService()

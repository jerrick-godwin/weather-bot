# Database Structure Documentation

## Overview

The Weather Bot system uses Google BigQuery as its primary data warehouse for storing weather data. The database is designed to handle large volumes of time-series weather data efficiently with proper partitioning and clustering strategies.

### Implementation Details

The database schema is programmatically defined and managed through the `BigQueryService` class in `src/services/bigquery_service.py`. The service handles:

- **Automatic Schema Creation**: Tables and datasets are created automatically if they don't exist
- **Schema Evolution**: New fields can be added to existing tables without data loss
- **Idempotent Operations**: Duplicate records are handled gracefully using MERGE operations
- **Data Validation**: Type checking and constraint validation during insertion

## Database Schema

### Dataset: `weather_data`

The main dataset containing all weather-related tables and views.

### Primary Table: `weather_records`

The core table storing all weather observations from the OpenWeatherMap API.

#### Table Schema

```sql
CREATE TABLE `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}` (
  coord STRUCT<
    lon FLOAT64,
    lat FLOAT64
  >,
  weather ARRAY<STRUCT<
    id INT64,
    main STRING,
    description STRING,
    icon STRING
  >>,
  base STRING,
  main STRUCT<
    temp FLOAT64,
    feels_like FLOAT64,
    temp_min FLOAT64,
    temp_max FLOAT64,
    pressure INT64,
    humidity INT64,
    sea_level INT64,
    grnd_level INT64
  >,
  visibility INT64,
  wind STRUCT<
    speed FLOAT64,
    deg INT64
  >,
  clouds STRUCT<
    all INT64
  >,
  dt TIMESTAMP NOT NULL,
  sys STRUCT<
    type INT64,
    id INT64,
    country STRING,
    sunrise TIMESTAMP,
    sunset TIMESTAMP
  >,
  timezone INT64,
  api_city_id INT64 NOT NULL,
  name STRING NOT NULL,
  cod INT64,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(dt)
CLUSTER BY sys.country, api_city_id, dt;
```

#### Field Descriptions

| Field Path | Type | Description | Notes |
|------------|------|-------------|-------|
| `coord.lon` | FLOAT64 | Longitude coordinate | Nullable when API omits value |
| `coord.lat` | FLOAT64 | Latitude coordinate | Nullable when API omits value |
| `weather[]` | ARRAY<STRUCT> | All weather condition slices provided by the API | Each element mirrors OpenWeatherMap `weather` entries |
| `weather[].id` | INT64 | Condition identifier | Maps to OpenWeatherMap condition catalog |
| `weather[].main` | STRING | Condition group | e.g. "Rain", "Clear" |
| `weather[].description` | STRING | Detailed condition description | Lowercase textual description |
| `weather[].icon` | STRING | Icon identifier | Maps to OpenWeatherMap icon set |
| `base` | STRING | Source metadata | Typically "stations", nullable |
| `main.temp` | FLOAT64 | Current temperature | Celsius, nullable |
| `main.feels_like` | FLOAT64 | Perceived temperature | Celsius, nullable |
| `main.temp_min` | FLOAT64 | Minimum observed temperature | Celsius, nullable |
| `main.temp_max` | FLOAT64 | Maximum observed temperature | Celsius, nullable |
| `main.pressure` | INT64 | Atmospheric pressure | hPa, nullable |
| `main.humidity` | INT64 | Relative humidity | Percentage (0-100), nullable |
| `main.sea_level` | INT64 | Sea-level pressure | hPa, nullable |
| `main.grnd_level` | INT64 | Ground-level pressure | hPa, nullable |
| `visibility` | INT64 | Visibility distance | Meters, nullable |
| `wind.speed` | FLOAT64 | Wind speed | m/s, nullable |
| `wind.deg` | INT64 | Wind direction | Degrees (0-360), nullable |
| `clouds.all` | INT64 | Cloud coverage | Percentage (0-100), nullable |
| `dt` | TIMESTAMP | Observation timestamp | UTC, partition column, NOT NULL |
| `sys.type` | INT64 | Provider metadata | Nullable |
| `sys.id` | INT64 | Provider metadata | Nullable |
| `sys.country` | STRING | ISO 3166-1 alpha-2 country code | Derived from API response, clustering key, nullable |
| `sys.sunrise` | TIMESTAMP | Sunrise time | Converted from epoch seconds, nullable |
| `sys.sunset` | TIMESTAMP | Sunset time | Converted from epoch seconds, nullable |
| `timezone` | INT64 | Offset from UTC in seconds | Matches OpenWeatherMap `timezone`, nullable |
| `api_city_id` | INT64 | OpenWeatherMap city identifier | NOT NULL, clustering key |
| `name` | STRING | City name | NOT NULL |
| `cod` | INT64 | API status code | Useful for diagnostics, nullable |
| `ingested_at` | TIMESTAMP | Ingestion timestamp | NOT NULL, set by pipeline |

## Data Partitioning Strategy

### Time-based Partitioning

The table is partitioned by `DATE(dt)` to:
- Improve query performance for time-range queries
- Optimize data pruning for date-based filters
- Enable efficient data lifecycle management
- Reduce query costs by scanning only relevant partitions

### Clustering Strategy

The table is clustered by:
1. `sys.country` - ISO country code for geographic distribution and filtering
2. `api_city_id` - Primary OpenWeatherMap identifier for weather locations
3. `dt` - Timestamp for time-based sorting within each city

This clustering strategy optimizes queries that filter by:
- Geographic regions (countries)
- Specific cities
- Time ranges within cities
- Country-based aggregations

## Indexes and Performance

### Automatic Clustering

BigQuery automatically maintains clustering based on the specified columns, which provides:
- Faster queries when filtering by clustered columns
- Reduced query costs through better data organization
- Automatic re-clustering as data is inserted

### Query Performance Patterns

Optimized query patterns:
```sql
-- Efficient: Uses partition pruning + clustering
SELECT *
FROM weather_records
WHERE DATE(dt) = '2025-01-01'
  AND name = 'London';

-- Efficient: Time range with city filter
SELECT AVG(main.temp)
FROM weather_records
WHERE dt BETWEEN '2025-01-01' AND '2025-01-07'
  AND api_city_id = 2643743;

-- Less efficient: No partition or cluster filtering
SELECT *
FROM weather_records
WHERE main.temp > 30;
```

## Data Integrity and Constraints

### Primary Key Strategy

Logical primary key: `(sys.country, api_city_id, dt)`
- Ensures no duplicate weather readings for the same city in the same country at the same timestamp
- Handles cities with same names in different countries (e.g., Paris, France vs Paris, Texas)
- Supports upsert operations for data corrections

### Data Quality Constraints

1. **Geographic Constraints**: Latitude/longitude within valid ranges
2. **Measurement Constraints**: Humidity 0-100%, pressure positive values
3. **Timestamp Constraints**: All timestamps in UTC
4. **Referential Integrity**: City information consistent within records

## Incremental Data Handling

### Idempotency Strategy

The system handles incremental updates through:
1. **MERGE Operations**: Use `MERGE` statements for upserts
2. **Composite Key Duplicate Detection**: Country, city ID, and timestamp combination prevents duplicates
3. **Late-arriving Data**: Handles out-of-order data insertion
4. **Global City Support**:Handles cities with same names in different countries

### Example MERGE Operation

```sql
MERGE `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}` AS target
USING `{PROJECT_ID}.{DATASET_ID}.{TEMP_TABLE_ID}` AS source
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
```

## Data Lifecycle Management

### Retention Policy

- **Active Data**: Current + 2 years of historical data
- **Archive Data**: Older data moved to separate archive tables
- **Purge Policy**: Data older than 5 years is permanently deleted

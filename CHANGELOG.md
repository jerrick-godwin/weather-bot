# Changelog

All notable changes to the Weather Bot has been documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-25

### Features
- **Database-based Backfill Status**: Replaced unreliable in-memory backfill tracking with robust database-based status checking
- **Enhanced Admin API**: Added `/admin/backfill-status` endpoint for detailed backfill information
- **Comprehensive Deployment Documentation**: Added extensive deployment guides for multiple cloud platforms
- **Test Helper Functions**: Created test helper functions to handle `@function_tool` decorated methods properly

### Security

- **Environment Variable Security**: Improved secrets management with better environment variable defaults
- **Configuration Validation**: Added startup validation for critical configuration values

### Testing

- **Fixed Test Failures**: Resolved 39+ test failures related to configuration and function tool calling
- **Mock Configuration**: Improved mock configuration at service import level
- **Helper Functions**: Created test helper functions for `@function_tool` decorated methods
- **Exception Testing**: Fixed exception object construction for guardrail tests

### Core Features
- **Weather Data Collection**: Complete OpenWeatherMap API integration for 100+ cities worldwide
- **AI-Powered Query System**: Natural language weather queries using OpenAI GPT models
- **Data Pipeline Orchestration**: Automated hourly updates and historical data backfilling
- **BigQuery Integration**: Scalable data storage with partitioning and clustering optimization
- **REST API**: Comprehensive FastAPI-based web API with automatic documentation

### Services Architecture
- **Weather Service**: OpenWeatherMap API client with rate limiting and retry logic
- **Database Service**: BigQuery operations with idempotent data insertion
- **Orchestration Service**: APScheduler-based job management and monitoring
- **AI Agent Service**: OpenAI integration with custom weather data tools
- **API Service**: FastAPI application with authentication and error handling

### Data Management
- **BigQuery Schema**: Optimized table design for time-series weather data
- **Data Partitioning**: Date-based partitioning for query performance optimization
- **Data Clustering**: City-based clustering for efficient geographical queries
- **Idempotent Inserts**: MERGE-based upserts to prevent duplicate data
- **Historical Backfill**: Automated collection of 2+ months of historical data

### Cities Coverage
- **North America**: 63 cities (US, Canada, Mexico)
- **Europe**: 40 cities (UK, Germany, France, Spain, Italy, etc.)
- **Asia**: 80 cities (China, India, Japan, Southeast Asia, etc.)
- **South America**: 18 cities (Brazil, Argentina, Chile, etc.)
- **Africa**: 30 cities (Nigeria, Egypt, South Africa, etc.)
- **Oceania**: 49 cities (Australia, New Zealand)

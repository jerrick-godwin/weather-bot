# Weather Bot

An agent based weather data collection and query system that combines real-time weather APIs with intelligent natural language processing to provide comprehensive weather insights.

## Quick Start

### Prerequisites

- Python 3.11+ (3.13 recommended) ([Get one here](https://www.python.org/downloads/))
- OpenAI API Key ([Get one here](https://platform.openai.com/api-keys))
- OpenWeatherMap API Key ([Get one here](https://openweathermap.org/api))
- Google Cloud Project with BigQuery enabled

### Installation & Setup

1. **Clone and setup environment**:
   ```bash
   git clone https://github.com/jerrick-godwin/weather-bot
   cd weather-bot
   cp .env.example .env
   ```

2. **Configure your API keys** in `.env`:
   ```bash
   OPENAI_API_KEY=sk-your-openai-key-here
   OPENWEATHER_API_KEY=your-openweather-key-here
   GOOGLE_PROJECT_ID=your-google-project-id
   ```

3. **Setup BigQuery Service Account**:
   
   Create a service account in Google Cloud Console and download the credentials:
   
   a. **Create Service Account**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to **IAM & Admin** > **Service Accounts**
   - Click **Create Service Account**
   - Enter a name (e.g., `weather-bot-bigquery`)
   - Click **Create and Continue**
   
   b. **Assign Roles**:
   - Add the following roles:
     - `BigQuery Data Editor`
     - `BigQuery Job User`
     - `BigQuery User`
   - Click **Continue** and then **Done**
   
   c. **Download Credentials**:
   - Click on the created service account
   - Go to **Keys** tab
   - Click **Add Key** > **Create new key**
   - Select **JSON** format and click **Create**
   - Save the downloaded JSON file as `service-account-key.json`
   
   d. **Place Credentials**:
   ```bash
   # Create data directory
   mkdir -p data
   
   # Move the service account key to the data directory
   mv service-account-key.json data/
   ```
   
   e. **Update Environment Variables**:
   Add the following to your `.env` file:
   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=data/service-account-key.json
   ```

4. **Deploy with Docker** (Recommended):
   ```bash
   docker-compose up -d
   ```

5. **Verify deployment**:
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health
   - Admin Status: http://localhost:8000/api/v1/admin/status

## Features

- **AI-Powered Queries**: Natural language weather queries powered by OpenAI
- **Historical Data**: Automated collection and storage of weather data in BigQuery
- **Real-Time Updates**: Continuous weather data collection with intelligent scheduling
- **Guardrails**: Built-in safety mechanisms for AI responses
- **Analytics Ready**: Structured data storage optimized for analysis
- **Production Ready**: Containerized deployment with comprehensive monitoring

## Architecture

The Weather Bot follows a **service-oriented architecture** with these core components:

- **WeatherService**: External API integration and rate limiting
- **BigQueryService**: Data persistence and analytics
- **ScheduleService**: Job orchestration and timing
- **WeatherAgent**: AI-powered natural language processing
- **GuardrailAgent**: Input/output validation and safety

## API Usage

### Get Current Weather
```bash
curl "http://localhost:8000/api/v1/weather/current/London"
```

### Natural Language Query
```bash
curl -X POST "http://localhost:8000/api/v1/weather/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather like in Paris today?"}'
```

### Get Weather History
```bash
curl "http://localhost:8000/api/v1/weather/history/London?days=7"
```

## Development

### Local Development
```bash
# Setup development environment
cp .env.example .env

# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_weather_service.py
```

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Architecture & Design](docs/design/DESIGN_DOCUMENTATION.md)**: Detailed analysis of system architecture, technology choices, and design decisions
- **[Deployment Guide](docs/deployment/DEPLOYMENT_DOCUMENTATION.md)**: Complete deployment instructions for local, Docker, and cloud environments
- **[Database Structure](docs/database/DATABASE_STRUCTURE_DOCUMENTATION.md)**: BigQuery schema, partitioning strategy, and data management
- **[Testing Guide](docs/testing/TESTING_DOCUMENTATION.md)**: Testing patterns, fixtures, and best practices

## Configuration

Key environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for AI features | Yes |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key | Yes |
| `GOOGLE_PROJECT_ID` | Google Cloud Project ID | Yes |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to BigQuery service account JSON file | Yes |
| `API_TOKEN` | Optional API authentication token | No |
| `UPDATE_INTERVAL_HOURS` | Weather data update frequency | No (default: 1) |
| `CITIES_TO_MONITOR` | Number of cities to monitor | No (default: 100) |

## Deployment

### Docker Compose (Recommended)
```bash
docker-compose up -d
```

### Google Cloud Run
```bash
gcloud run deploy weather-bot \
  --image gcr.io/your-project/weather-bot \
  --platform managed \
  --region your_preferred_region
```

### Kubernetes
```bash
kubectl apply -f k8s/weather-bot-deployment.yaml
```

See the [Deployment Guide](docs/deployment/DEPLOYMENT_DOCUMENTATION.md) for detailed instructions.

## Monitoring

### Health Endpoints
- **Basic Health**: `GET /` - Application status
- **Detailed Status**: `GET /api/v1/admin/status` - System health details
- **Job Status**: `GET /api/v1/admin/jobs` - Scheduler status
- **Backfill Status**: `GET /api/v1/admin/backfill-status` - Data completeness

### Logs
```bash
# View application logs
docker-compose logs -f weather-bot

# Check specific service logs
docker logs weather-bot --tail 100
```

## Support

- **Documentation**: Check the `docs/` directory for detailed guides
- **Issues**: Report bugs and request features via GitHub Issues
- **Troubleshooting**: See the [Deployment Guide](docs/deployment/DEPLOYMENT_DOCUMENTATION.md#troubleshooting) for common issues

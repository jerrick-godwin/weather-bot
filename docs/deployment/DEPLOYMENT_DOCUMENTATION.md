# Deployment Guide

A comprehensive guide to deploy the Weather Bot application in various environments, from local to cloud deployments.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Local Development Deployment](#local-development-deployment)
4. [Docker Deployment](#docker-deployment)
5. [Cloud Deployment](#cloud-deployment)
6. [Environment Configuration](#environment-configuration)
7. [Security Configuration](#security-configuration)
8. [Monitoring and Logging](#monitoring-and-logging)
9. [Scaling and Performance](#scaling-and-performance)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Services and API Keys

Before deploying the Weather Bot, ensure you have access to the following services:

#### 1. OpenAI API Key
- **Purpose**: Powers the AI agent for natural language weather queries
- **How to get**: Visit [OpenAI Platform](https://platform.openai.com/api-keys)
- **Cost**: Pay-per-use based on API calls
- **Required permissions**: Access to GPT models

#### 2. OpenWeatherMap API Key
- **Purpose**: Fetches real-time weather data
- **How to get**: Register at [OpenWeatherMap](https://openweathermap.org/api)
- **Cost**: Free tier available (1000 calls/day), paid plans for higher usage
- **Required permissions**: Current Weather Data API access

#### 3. Google Cloud Platform Setup
- **Purpose**: Stores historical weather data in BigQuery
- **Requirements**:
  - Google Cloud Project with billing enabled
  - BigQuery API enabled
  - Service Account with BigQuery permissions
- **Setup steps**:
    ```bash
    # Create a new project (optional)
    gcloud projects create your-weather-bot-project
  
    # Enable BigQuery API
    gcloud services enable bigquery.googleapis.com
  
    # Create service account
    gcloud iam service-accounts create weather-bot-sa \
      --description="Service account for Weather Bot" \
      --display-name="Weather Bot Service Account"
  
    # Grant BigQuery permissions
    gcloud projects add-iam-policy-binding your-project-id \
      --member="serviceAccount:weather-bot-sa@your-project-id.iam.gserviceaccount.com" \
      --role="roles/bigquery.dataEditor"
  
    gcloud projects add-iam-policy-binding your-project-id \
      --member="serviceAccount:weather-bot-sa@your-project-id.iam.gserviceaccount.com" \
      --role="roles/bigquery.jobUser"
  
    # Create and download service account key
    gcloud iam service-accounts keys create service-account.json \
      --iam-account=weather-bot-sa@your-project-id.iam.gserviceaccount.com
    ```

### System Requirements

#### Software Requirements
- **Python**: 3.11 or higher (for local deployment)
- **Docker**: 20.10+ (for containerized deployment)

## Quick Start

### 1. Setup the application
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

### 2. Configure Environment
Edit the `.env` file with your credentials:
```bash
# Required API Keys
OPENAI_API_KEY=sk-your-openai-key-here
OPENWEATHER_API_KEY=your-openweather-key-here

# Google Cloud Configuration
GOOGLE_PROJECT_ID=your-google-project-id
GOOGLE_SERVICE_ACCOUNT_FILE=data/service-account.json

# Optional: API Authentication
API_TOKEN=your-secure-token-here
```

### 3. Place Service Account File
```bash
# Create data directory if it doesn't exist
mkdir -p data

# Copy your Google Cloud service account JSON file
cp /path/to/your/service-account.json data/service-account.json
```

### 4. Deploy with Docker Compose (Recommended)
```bash
# Start the application
docker-compose up -d

# Check status
curl http://localhost:8000/api/v1/admin/status

# View logs
docker-compose logs -f weather-bot
```

### 5. Verify Deployment
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Admin Status**: http://localhost:8000/api/v1/admin/status

## Local Development Deployment

### Using Direct Commands
```bash
# Complete setup
cp .env.example .env
pip install -r requirements.txt

# Start development server with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Check system status via API
curl http://localhost:8000/api/v1/admin/status
```

### Manual Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI application
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Development Environment Variables
Create a `.env.development` file for development-specific settings:
```bash
# Development configuration
LOG_LEVEL=DEBUG
UPDATE_INTERVAL_HOURS=24
CITIES_TO_MONITOR=10
API_TOKEN=  # No authentication for development
LOG_FORMAT=text
```

## Docker Deployment

### Single Container Deployment
```bash
# Build the image
docker build -t weather-bot:latest .

# Run with environment file
docker run -d \
  --name weather-bot \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/app/data:ro \
  -v weather-logs:/app/logs \
  --restart unless-stopped \
  weather-bot:latest

# Check logs
docker logs -f weather-bot

# Stop and remove
docker stop weather-bot && docker rm weather-bot
```

### Docker Compose Deployment (Production Ready)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f weather-bot

# Update and restart
docker-compose pull
docker-compose up -d

# Stop all services
docker-compose down

# Stop and remove volumes (careful - this deletes logs)
docker-compose down -v
```

## Cloud Deployment

### Google Cloud Run
```bash
# Set your project
gcloud config set project your-project-id

# Build and submit to Cloud Build
gcloud builds submit --tag gcr.io/your-project-id/weather-bot

# Deploy to Cloud Run
gcloud run deploy weather-bot \
  --image gcr.io/your-project-id/weather-bot \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 80 \
  --max-instances 10 \
  --set-env-vars OPENAI_API_KEY=your-key,OPENWEATHER_API_KEY=your-key,GOOGLE_PROJECT_ID=your-project-id \
  --set-env-vars LOG_LEVEL=INFO,LOG_FORMAT=json

# Get the service URL
gcloud run services describe weather-bot --region us-central1 --format 'value(status.url)'
```

### AWS ECS with Fargate
```bash
# Create ECR repository
aws ecr create-repository --repository-name weather-bot --region us-east-1

# Get login token and login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin your-account.dkr.ecr.us-east-1.amazonaws.com

# Build and tag image
docker build -t weather-bot:latest .
docker tag weather-bot:latest your-account.dkr.ecr.us-east-1.amazonaws.com/weather-bot:latest

# Push image
docker push your-account.dkr.ecr.us-east-1.amazonaws.com/weather-bot:latest

# Create task definition (create task-definition.json)
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create ECS cluster
aws ecs create-cluster --cluster-name weather-bot-cluster

# Create service
aws ecs create-service \
  --cluster weather-bot-cluster \
  --service-name weather-bot-service \
  --task-definition weather-bot:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-12345],assignPublicIp=ENABLED}"
```

### Azure Container Instances
```bash
# Create resource group
az group create --name weather-bot-rg --location eastus

# Create container registry (optional)
az acr create --resource-group weather-bot-rg --name weatherbotregistry --sku Basic

# Build and push to ACR (optional)
az acr build --registry weatherbotregistry --image weather-bot:latest .

# Deploy container
az container create \
  --resource-group weather-bot-rg \
  --name weather-bot \
  --image weatherbotregistry.azurecr.io/weather-bot:latest \
  --cpu 1 \
  --memory 2 \
  --ports 8000 \
  --dns-name-label weather-bot-unique \
  --environment-variables \
    OPENAI_API_KEY=your-key \
    OPENWEATHER_API_KEY=your-key \
    GOOGLE_PROJECT_ID=your-project-id \
    LOG_LEVEL=INFO \
    LOG_FORMAT=json

# Get the FQDN
az container show --resource-group weather-bot-rg --name weather-bot --query ipAddress.fqdn
```

### Kubernetes Deployment
```yaml
# weather-bot-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: weather-bot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: weather-bot
  template:
    metadata:
      labels:
        app: weather-bot
    spec:
      containers:
      - name: weather-bot
        image: your-registry/weather-bot:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: weather-bot-secrets
              key: openai-api-key
        - name: OPENWEATHER_API_KEY
          valueFrom:
            secretKeyRef:
              name: weather-bot-secrets
              key: openweather-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/admin/status
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: weather-bot-service
spec:
  selector:
    app: weather-bot
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

Deploy to Kubernetes:
```bash
# Create secrets
kubectl create secret generic weather-bot-secrets \
  --from-literal=openai-api-key=your-openai-key \
  --from-literal=openweather-api-key=your-openweather-key

# Deploy application
kubectl apply -f weather-bot-deployment.yaml

# Check status
kubectl get pods
kubectl get services

# View logs
kubectl logs -l app=weather-bot
```

## Environment Configuration

### Environment-Specific Settings

#### Development
```bash
# .env.development
LOG_LEVEL=DEBUG
UPDATE_INTERVAL_HOURS=24
CITIES_TO_MONITOR=10
API_TOKEN=  # No authentication
LOG_FORMAT=text
BACKFILL_MONTHS=1
```

#### Staging
```bash
# .env.staging
LOG_LEVEL=INFO
UPDATE_INTERVAL_HOURS=2
CITIES_TO_MONITOR=50
API_TOKEN=staging-secure-token-here
LOG_FORMAT=json
BACKFILL_MONTHS=2
```

#### Production
```bash
# .env.production
LOG_LEVEL=WARNING
UPDATE_INTERVAL_HOURS=1
CITIES_TO_MONITOR=100
API_TOKEN=production-very-secure-token-here
LOG_FORMAT=json
BACKFILL_MONTHS=3
```

### Configuration Validation
```bash
# Validate configuration before deployment
python main.py validate-config

# Test API connections
python main.py test-connections

# Check database connectivity
python main.py test-db
```

## Security Configuration

### API Authentication
```bash
# Generate secure API token
API_TOKEN=$(openssl rand -hex 32)
echo "API_TOKEN=$API_TOKEN" >> .env

# Use token in requests
curl -H "Authorization: Bearer $API_TOKEN" \
  http://your-api-url/api/v1/admin/status
```

### Network Security
```yaml
# docker-compose.yml - Network isolation
networks:
  weather-network:
    driver: bridge
    internal: false  # Set to true for complete isolation
```

### Secrets Management
```bash
# Using Docker secrets
echo "your-openai-key" | docker secret create openai_api_key -
echo "your-openweather-key" | docker secret create openweather_api_key -

# Update docker-compose.yml to use secrets
version: '3.8'
services:
  weather-bot:
    secrets:
      - openai_api_key
      - openweather_api_key
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key
      - OPENWEATHER_API_KEY_FILE=/run/secrets/openweather_api_key

secrets:
  openai_api_key:
    external: true
  openweather_api_key:
    external: true
```

### SSL/TLS Configuration
```nginx
# nginx.conf for reverse proxy with SSL
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    location / {
        proxy_pass http://weather-bot:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Monitoring and Logging

### Health Check Endpoints
- **Basic Health**: `GET /` - Returns 200 if application is running
- **Detailed Status**: `GET /api/v1/admin/status` - Returns system health details
- **Job Status**: `GET /api/v1/admin/jobs` - Returns scheduler job status
- **Backfill Status**: `GET /api/v1/admin/backfill-status` - Returns data backfill status

### Logging Configuration
```bash
# Structured JSON logging (production)
LOG_FORMAT=json
LOG_LEVEL=INFO

# Human-readable logging (development)
LOG_FORMAT=text
LOG_LEVEL=DEBUG
```

### Monitoring with Prometheus
```python
# Add to requirements.txt: prometheus-client
# Implement metrics endpoints
from prometheus_client import Counter, Histogram, generate_latest

api_requests = Counter('api_requests_total', 'Total API requests')
request_duration = Histogram('request_duration_seconds', 'Request duration')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### External Monitoring Integration
```bash
# Health check for external monitoring
curl -f http://your-api-url/ || exit 1

# Detailed health check
curl -f http://your-api-url/api/v1/admin/status | jq '.status' | grep -q "healthy" || exit 1
```

## Scaling and Performance

### Horizontal Scaling
```yaml
# docker-compose.yml with multiple replicas
version: '3.8'
services:
  weather-bot:
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
        reservations:
          memory: 512M
          cpus: '0.25'
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

### Load Balancing
```nginx
# nginx.conf
upstream weather-bot {
    least_conn;
    server weather-bot-1:8000 max_fails=3 fail_timeout=30s;
    server weather-bot-2:8000 max_fails=3 fail_timeout=30s;
    server weather-bot-3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    location / {
        proxy_pass http://weather-bot;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Resource Monitoring
```bash
# Monitor container resources
docker stats weather-bot

# Monitor disk usage
df -h

# Monitor memory usage
free -h

# Monitor CPU usage
top -p $(pgrep -f "python main.py")
```

## Troubleshooting

### Common Issues and Solutions

#### 1. BigQuery Authentication Errors
```bash
# Verify service account file exists and has correct permissions
ls -la data/service-account.json
chmod 600 data/service-account.json

# Test BigQuery connection
python -c "
from google.cloud import bigquery
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'data/service-account.json'
client = bigquery.Client()
print('BigQuery connection successful')
"

# Check service account permissions
gcloud auth activate-service-account --key-file=data/service-account.json
gcloud projects get-iam-policy your-project-id
```

#### 2. API Key Issues
```bash
# Test OpenWeatherMap API
curl "https://api.openweathermap.org/data/2.5/weather?q=London&appid=$OPENWEATHER_API_KEY"

# Test OpenAI API
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 5}' \
  https://api.openai.com/v1/chat/completions
```

#### 3. Container Issues
```bash
# Check container logs
docker logs weather-bot --tail 100

# Inspect container
docker exec -it weather-bot /bin/bash

# Check environment variables
docker exec weather-bot env | grep -E "(OPENAI|OPENWEATHER|GOOGLE)"

# Check file permissions
docker exec weather-bot ls -la /app/data/
```

#### 4. Network Issues
```bash
# Test container networking
docker exec weather-bot curl -I http://localhost:8000

# Check port binding
docker port weather-bot

# Test external connectivity
docker exec weather-bot curl -I https://api.openweathermap.org
docker exec weather-bot curl -I https://api.openai.com
```

#### 5. Database Issues
```bash
# Check BigQuery dataset exists
bq ls your-project-id:weather_data

# Check table schema
bq show your-project-id:weather_data.weather_records

# Test database connectivity
python main.py test-db
```

#### 6. Scheduler Issues
```bash
# Check job status
curl http://localhost:8000/api/v1/admin/jobs

# View scheduler logs
docker logs weather-bot | grep -i scheduler

# Manually trigger update
python main.py update-weather
```

### Performance Issues
```bash
# Check API response times
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:8000/api/v1/weather/current/London"

# Monitor resource usage
docker stats weather-bot

# Check for memory leaks
docker exec weather-bot ps aux | grep python
```

### Updates and Upgrades
```bash
# Update application
git pull origin main
docker-compose build
docker-compose up -d

# Update dependencies
pip install -r requirements.txt --upgrade

# Database migrations (if needed)
python main.py migrate-db
```

### Backup and Recovery
```bash
# Backup configuration
tar -czf weather-bot-config-$(date +%Y%m%d).tar.gz .env data/

# Backup BigQuery data
bq extract \
  --destination_format=NEWLINE_DELIMITED_JSON \
  your-project-id:weather_data.weather_records \
  gs://your-backup-bucket/weather_data_$(date +%Y%m%d).json

# Restore from backup
bq load \
  --source_format=NEWLINE_DELIMITED_JSON \
  your-project-id:weather_data.weather_records \
  gs://your-backup-bucket/weather_data_20231201.json
```

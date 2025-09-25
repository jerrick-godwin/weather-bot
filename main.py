import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from src.api import v1_router
from src.api.health import health_router
from src.config.config import config
from src.services.bigquery_service import bigquery_service
from src.services.schedule_service import schedule_service
from src.utils.logging_config import setup_logging

# Configure logging
setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown of the weather bot system including
    database initialization and the job scheduler.
    """
    logger.info("Starting Weather Bot application")

    # Startup
    try:
        # Initialize database
        await bigquery_service.initialize_database()

        # Start scheduler
        await schedule_service.start()

        # Store services in app state for access in routes
        app.state.schedule_service = schedule_service

        logger.info("Weather Bot application started successfully")

        yield

    except Exception as e:
        logger.error("Failed to start Weather Bot", error=str(e))
        raise

    # Shutdown
    finally:
        logger.info("Shutting down Weather Bot")
        if hasattr(app.state, "schedule_service"):
            app.state.schedule_service.stop()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    # Create FastAPI app with custom configuration
    app = FastAPI(
        title="Weather Bot API",
        description="""
        ## Weather Bot API
        
        A comprehensive weather data collection and AI-powered query system.
        
        ### Features:
        - **Current Weather**: Get real-time weather data for any city
        - **Historical Data**: Access historical weather records and trends  
        - **AI Agent**: Natural language weather queries powered by OpenAI
        - **Data Pipeline**: Automated hourly updates and historical backfilling
        - **Admin Tools**: System monitoring and manual controls
        
        ### Authentication:
        If an API token is configured, include it as a Bearer token in the Authorization header.
        
        ### Example Queries:
        - "What's the weather like in London today?"
        - "Show me the temperature trends in Tokyo last week"
        - "What was the average humidity in New York last month?"
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Add trusted host middleware for security
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["*"]  # Configure appropriately for production
    )

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all HTTP requests with timing information."""
        start_time = time.time()

        # Log request
        logger.info(
            "HTTP request started",
            method=request.method,
            url=str(request.url),
            client_ip=request.client.host if request.client else "unknown",
        )

        # Process request
        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log successful response
            logger.info(
                "HTTP request completed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                process_time=process_time,
            )

            # Add processing time header
            response.headers["X-Process-Time"] = str(process_time)
            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "HTTP request failed",
                method=request.method,
                url=str(request.url),
                error=str(e),
                process_time=process_time,
            )
            raise

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions globally."""
        logger.error(
            "Unhandled exception",
            method=request.method,
            url=str(request.url),
            error=str(exc),
            exc_info=True,
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred. Please try again later.",
                "timestamp": time.time(),
            },
        )

    # HTTP exception handler
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions with consistent formatting."""
        logger.warning(
            "HTTP exception",
            method=request.method,
            url=str(request.url),
            status_code=exc.status_code,
            detail=exc.detail,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "status_code": exc.status_code, "timestamp": time.time()},
        )

    # Include API routes
    app.include_router(health_router)
    app.include_router(v1_router)

    # Root endpoint (hide from swagger)
    @app.get("/", tags=["Root"], include_in_schema=False)
    async def root():
        """Root endpoint providing basic system information."""
        return {
            "message": "Weather Bot API",
            "version": "1.0.0",
            "status": "running",
            "timestamp": time.time(),
            "docs": "/docs",
            "redoc": "/redoc",
        }

    # Custom OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title="Weather Bot API",
            version="1.0.0",
            description="AI-powered weather data collection and query system",
            routes=app.routes,
        )

        # Add authentication scheme
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    return app


# Create the application instance
app = create_app()

def main():
    logger.info(
        f"Starting Weather Bot server in {config.environment} environment",
        host=config.api_host,
        port=config.api_port,
        reload=False,
    )

    try:
        uvicorn.run(
            app,
            host=config.api_host,
            port=config.api_port,
            log_level=config.log_level.lower(),
            access_log=True,
            server_header=False,
            date_header=False,
        )
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error("Server failed to start", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()

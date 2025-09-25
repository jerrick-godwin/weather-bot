import logging
import os
import sys
from pathlib import Path

from src.config.config import config


class CustomFormatter(logging.Formatter):
    """Custom formatter that implements the required format: [yyyy-mm-dd hh:mm:ss] [log_type] [class_name]: {message}"""
    
    def format(self, record):
        # Extract class name from the logger name
        class_name = record.name.split('.')[-1] if '.' in record.name else record.name
        
        # Format timestamp as yyyy-mm-dd hh:mm:ss
        timestamp = self.formatTime(record, '%Y-%m-%d %H:%M:%S')
        
        # Format the log message
        formatted_message = f"[{timestamp}] [{record.levelname}] [{class_name}]: {record.getMessage()}"
        
        # Add exception info if present
        if record.exc_info:
            formatted_message += '\n' + self.formatException(record.exc_info)
            
        return formatted_message


def ensure_logs_directory():
    """Ensure the logs directory exists."""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


def get_log_file_path() -> Path:
    """Get the log file path based on environment."""
    logs_dir = ensure_logs_directory()
    log_filename = f"weather_bot_{config.environment}.log"
    return logs_dir / log_filename


def setup_logging():
    """
    Configure logging for the application.

    Sets up file-based logging with custom format:
    [yyyy-mm-dd hh:mm:ss] [log_type] [class_name]: {message}
    """
    
    # Get log file path
    log_file_path = get_log_file_path()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level.upper()))
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create custom formatter
    formatter = CustomFormatter()
    
    # Create file handler
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(getattr(logging, config.log_level.upper()))
    file_handler.setFormatter(formatter)
    
    # Create console handler (optional - for development)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.log_level.upper()))
    console_handler.setFormatter(formatter)
    
    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log setup completion
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - writing to {log_file_path}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Name of the logger (typically __name__)

    Returns:
        Configured Python logger
    """
    return logging.getLogger(name)

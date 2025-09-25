from src.exceptions.bigquery.bigquery_service_error import BigQueryServiceError


class TableCreationError(BigQueryServiceError):
    """Exception raised when table creation fails."""

    pass

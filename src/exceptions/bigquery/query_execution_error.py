from src.exceptions.bigquery.bigquery_service_error import BigQueryServiceError


class QueryExecutionError(BigQueryServiceError):
    """Exception raised when query execution fails."""

    pass

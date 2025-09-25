from src.exceptions.bigquery.bigquery_service_error import BigQueryServiceError


class DataInsertionError(BigQueryServiceError):
    """Exception raised when data insertion fails."""

    pass

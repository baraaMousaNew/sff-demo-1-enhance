from enum import Enum


class ReportRowType(str, Enum):
    """Values of the 'Type' column in a decoded error report row."""

    ERROR = 'ERROR'
    WARNING = 'WARNING'
    NOTIFICATION = 'NOTIFICATION'

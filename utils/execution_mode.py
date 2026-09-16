from enum import Enum


class ExecutionMode(str, Enum):
    """Values of the SOAP_EXECUTION_MODE environment variable / --mode CLI flag."""

    SYSTEM1_ONLY = 'system1_only'
    SYSTEM2_ONLY = 'system2_only'
    BOTH_SYSTEMS = 'both_systems'
    SYSTEM1_BOTH_ENVS = 'system1_both_envs'
    UNKNOWN = 'unknown'

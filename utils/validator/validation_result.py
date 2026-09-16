from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    rule_id: str
    transaction: str
    type: str        # "ERROR" | "WARNING"
    message: str
    is_active: bool = True  # False for rules that are in the spec but currently inactive
    trace: tuple[str, ...] = ()  # ordered steps explaining how the violation was reached

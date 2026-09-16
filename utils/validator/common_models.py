"""
Shared dataclasses and constants used across all XSD transaction models.
CommonTypes constraints are enforced in __post_init__ — violations raise immediately.
"""

import re
from dataclasses import dataclass
from typing import Optional

# ── Shared patterns (CommonTypes.xsd: DateForm / DateTimeForm) ────────────────
DATE_RE = re.compile(r'^\d{2}/\d{2}/\d{4}$')
DATETIME_RE = re.compile(r'^\d{2}/\d{2}/\d{4} (20|21|22|23|[0-1]?\d):[0-5]?\d$')

# ── Shared enumerations (used across multiple XSD files) ──────────────────────
ACTIVITY_TYPES = frozenset({1, 2, 3, 4, 5, 6, 8, 9, 10})
ENCOUNTER_TYPES = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 41, 42})
DIAGNOSIS_TYPES = frozenset({"Principal", "Secondary", "Admitting", "ReasonForVisit"})

# ── Private enumerations (used only within this file) ─────────────────────────
_DISPOSITION_FLAGS = frozenset({
    "PRODUCTION", "TEST", "PTE_SUBMIT", "PTE_VALIDATE_ONLY", "PTE_RESPONSE",
    "PTE_SHADOW_NOT_FOR_PAYMENT_SUBMIT", "PTE_SHADOW_NOT_FOR_PAYMENT_VALIDATE_ONLY",
    "SHADOW_NOT_FOR_PAYMENT_SUBMIT", "SHADOW_NOT_FOR_PAYMENT_VALIDATE_ONLY",
})
_OBSERVATION_TYPES = frozenset({
    "CPT", "HL7v3 Native", "LOINC", "SNOMED CT", "Text",
    "File", "Flags", "Universal Dental", "Episode",
})
_DX_INFO_TYPES = frozenset({
    "POA", "Year of Onset", "Birth Weight", "ICD10-GM", "ICD10-CM", "KCD",
})
_RESUBMISSION_TYPES = frozenset({"correction", "internal complaint", "legacy"})


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class Header:
    sender_id: str
    receiver_id: str
    transaction_date: str
    record_count: int
    disposition_flag: str

    def __post_init__(self):
        if not self.sender_id.strip():
            raise ValueError("SenderID: minLength=1 violated")
        if not self.receiver_id.strip():
            raise ValueError("ReceiverID: minLength=1 violated")
        if not DATETIME_RE.match(self.transaction_date):
            raise ValueError(f"TransactionDate: must match dd/mm/yyyy HH:MM, got '{self.transaction_date}'")
        if self.record_count < 0:
            raise ValueError(f"RecordCount: must be non-negative, got {self.record_count}")
        if self.disposition_flag not in _DISPOSITION_FLAGS:
            raise ValueError(f"DispositionFlag: '{self.disposition_flag}' is not an allowed value")


@dataclass
class DxInfo:
    type: str
    code: str

    def __post_init__(self):
        if self.type not in _DX_INFO_TYPES:
            raise ValueError(f"DxInfo.Type: '{self.type}' is not an allowed value")
        if not self.code.strip():
            raise ValueError("DxInfo.Code: minLength=1 violated")


@dataclass
class Observation:
    type: str
    code: str
    value: Optional[str] = None
    value_type: Optional[str] = None
    value_date: Optional[str] = None  # used by Universal Dental observations (dd/mm/yyyy HH:MM)

    def __post_init__(self):
        if self.type not in _OBSERVATION_TYPES:
            raise ValueError(f"Observation.Type: '{self.type}' is not an allowed value")
        if not self.code.strip():
            raise ValueError("Observation.Code: minLength=1 violated")


@dataclass
class Resubmission:
    type: str
    comment: str
    attachment: Optional[bytes] = None

    def __post_init__(self):
        if self.type not in _RESUBMISSION_TYPES:
            raise ValueError(f"Resubmission.Type: '{self.type}' is not an allowed value")
        if not self.comment.strip():
            raise ValueError("Resubmission.Comment: minLength=1 violated")
        if len(self.comment) > 2000:
            raise ValueError(f"Resubmission.Comment: maxLength=2000 violated, got {len(self.comment)}")

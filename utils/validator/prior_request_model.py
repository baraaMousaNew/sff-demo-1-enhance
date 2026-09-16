"""
PriorRequest XSD model.
CommonTypes constraints enforced in __post_init__ — violations raise immediately.
Hierarchy (high → low):
  PriorRequest
    └── Header                      (common_models)
    └── Authorization (1)
          ├── Encounter (0..1)
          ├── Diagnosis (0..*)
          │     └── DxInfo (0..*)   (common_models)
          ├── Activity (0..*)
          │     └── Observation (0..*)  (common_models)
          └── Resubmission (0..1)   (common_models)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from utils.validator.common_models import (
    Header, DxInfo, Observation, Resubmission,
    DATETIME_RE, ACTIVITY_TYPES, ENCOUNTER_TYPES, DIAGNOSIS_TYPES,
)

_AUTHORIZATION_TYPES = frozenset({
    "Eligibility", "Authorization", "Cancellation",
    "Extension", "Status Inquiry", "Prescription",
})


@dataclass
class Encounter:
    facility_id: str
    type: Optional[int] = None
    start: Optional[str] = None     # dd/mm/yyyy HH:MM
    end: Optional[str] = None       # dd/mm/yyyy HH:MM

    def __post_init__(self):
        if self.type is not None and self.type not in ENCOUNTER_TYPES:
            raise ValueError(f"Encounter.Type: '{self.type}' is not an allowed value")
        if self.start is not None and not DATETIME_RE.match(self.start):
            raise ValueError(f"Encounter.Start: must match dd/mm/yyyy HH:MM, got '{self.start}'")
        if self.end is not None and not DATETIME_RE.match(self.end):
            raise ValueError(f"Encounter.End: must match dd/mm/yyyy HH:MM, got '{self.end}'")


@dataclass
class Diagnosis:
    type: str
    code: str
    dx_info: List[DxInfo] = field(default_factory=list)

    def __post_init__(self):
        if self.type not in DIAGNOSIS_TYPES:
            raise ValueError(f"Diagnosis.Type: '{self.type}' is not an allowed value")
        if not self.code.strip():
            raise ValueError("Diagnosis.Code: minLength=1 violated")


@dataclass
class Activity:
    id: str             # required here (unlike ClaimSubmission), max 30 chars
    type: int
    code: str
    net: float
    start: Optional[str] = None
    quantity: Optional[float] = None
    ordering_clinician: Optional[str] = None
    clinician: Optional[str] = None
    observations: List[Observation] = field(default_factory=list)

    def __post_init__(self):
        if not self.id.strip():
            raise ValueError("Activity.ID: minLength=1 violated")
        if len(self.id) > 30:
            raise ValueError(f"Activity.ID: maxLength=30 violated, got {len(self.id)}")
        if self.type not in ACTIVITY_TYPES:
            raise ValueError(f"Activity.Type: '{self.type}' is not an allowed value")
        if not self.code.strip():
            raise ValueError("Activity.Code: minLength=1 violated")
        if self.start is not None and not DATETIME_RE.match(self.start):
            raise ValueError(f"Activity.Start: must match dd/mm/yyyy HH:MM, got '{self.start}'")


@dataclass
class Authorization:
    type: str           # Eligibility | Authorization | Cancellation | Extension | Status Inquiry | Prescription
    id: str
    member_id: str
    payer_id: str
    emirates_id_number: str
    id_payer: Optional[str] = None
    date_ordered: Optional[str] = None  # dd/mm/yyyy
    encounter: Optional[Encounter] = None
    diagnoses: List[Diagnosis] = field(default_factory=list)
    activities: List[Activity] = field(default_factory=list)
    resubmission: Optional[Resubmission] = None

    def __post_init__(self):
        if self.type not in _AUTHORIZATION_TYPES:
            raise ValueError(f"Authorization.Type: '{self.type}' is not an allowed value")
        if not self.id.strip():
            raise ValueError("Authorization.ID: minLength=1 violated")
        if not self.member_id.strip():
            raise ValueError("Authorization.MemberID: minLength=1 violated")
        if not self.payer_id.strip():
            raise ValueError("Authorization.PayerID: minLength=1 violated")
        if not self.emirates_id_number.strip():
            raise ValueError("Authorization.EmiratesIDNumber: minLength=1 violated")


@dataclass
class PriorRequest:
    header: Header
    authorization: Authorization

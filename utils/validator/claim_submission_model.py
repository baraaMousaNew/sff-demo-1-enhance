"""
ClaimSubmission XSD model.
CommonTypes constraints enforced in __post_init__ — violations raise immediately.
Hierarchy (high → low):
  ClaimSubmission
    └── Header               (common_models)
    └── Claim (1..*)
          ├── Encounter (1..*)
          ├── Diagnosis (1..*)
          │     └── DxInfo (0..*)   (common_models)
          ├── Activity (1..*)
          │     └── Observation (0..*)  (common_models)
          ├── Resubmission (0..1)    (common_models)
          └── Contract (0..1)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from utils.validator.common_models import (
    Header, DxInfo, Observation, Resubmission,
    DATETIME_RE, ACTIVITY_TYPES, ENCOUNTER_TYPES, DIAGNOSIS_TYPES,
)

_ENCOUNTER_START_TYPES = frozenset({1, 2, 3, 4, 5, 6, 7, 8})
_ENCOUNTER_END_TYPES = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12})


@dataclass
class Encounter:
    facility_id: str
    type: int
    patient_id: str
    start: str
    eligibility_id_payer: Optional[str] = None
    end: Optional[str] = None
    start_type: Optional[int] = None
    end_type: Optional[int] = None
    transfer_source: Optional[str] = None
    transfer_destination: Optional[str] = None

    def __post_init__(self):
        if self.type not in ENCOUNTER_TYPES:
            raise ValueError(f"Encounter.Type: '{self.type}' is not an allowed value")
        if not self.patient_id.strip():
            raise ValueError("Encounter.PatientID: minLength=1 violated")
        if not DATETIME_RE.match(self.start):
            raise ValueError(f"Encounter.Start: must match dd/mm/yyyy HH:MM, got '{self.start}'")
        if self.end is not None and not DATETIME_RE.match(self.end):
            raise ValueError(f"Encounter.End: must match dd/mm/yyyy HH:MM, got '{self.end}'")
        if self.start_type is not None and self.start_type not in _ENCOUNTER_START_TYPES:
            raise ValueError(f"Encounter.StartType: '{self.start_type}' is not an allowed value")
        if self.end_type is not None and self.end_type not in _ENCOUNTER_END_TYPES:
            raise ValueError(f"Encounter.EndType: '{self.end_type}' is not an allowed value")


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
    start: str
    type: int
    code: str
    quantity: float
    net: float
    id: Optional[str] = None
    ordering_clinician: Optional[str] = None
    clinician: Optional[str] = None
    prior_authorization_id: Optional[str] = None
    vat: Optional[float] = None
    vat_percent: Optional[float] = None
    date_ordered: Optional[str] = None
    observations: List[Observation] = field(default_factory=list)

    def __post_init__(self):
        if not DATETIME_RE.match(self.start):
            raise ValueError(f"Activity.Start: must match dd/mm/yyyy HH:MM, got '{self.start}'")
        if self.type not in ACTIVITY_TYPES:
            raise ValueError(f"Activity.Type: '{self.type}' is not an allowed value")
        if not self.code.strip():
            raise ValueError("Activity.Code: minLength=1 violated")
        if self.id is not None and len(self.id) > 30:
            raise ValueError(f"Activity.ID: maxLength=30 violated, got {len(self.id)}")
        if self.date_ordered is not None and not DATETIME_RE.match(self.date_ordered):
            raise ValueError(f"Activity.DateOrdered: must match dd/mm/yyyy HH:MM, got '{self.date_ordered}'")


@dataclass
class Contract:
    package_name: Optional[str] = None


@dataclass
class Claim:
    id: str
    payer_id: str
    provider_id: str
    emirates_id_number: str
    gross: float
    patient_share: float
    net: float
    encounters: List[Encounter] = field(default_factory=list)
    diagnoses: List[Diagnosis] = field(default_factory=list)
    activities: List[Activity] = field(default_factory=list)
    id_payer: Optional[str] = None
    member_id: Optional[str] = None
    vat: Optional[float] = None
    resubmission: Optional[Resubmission] = None
    contract: Optional[Contract] = None

    def __post_init__(self):
        if not self.id.strip():
            raise ValueError("Claim.ID: minLength=1 violated")
        if not self.payer_id.strip():
            raise ValueError("Claim.PayerID: minLength=1 violated")
        if not self.emirates_id_number.strip():
            raise ValueError("Claim.EmiratesIDNumber: minLength=1 violated")


@dataclass
class ClaimSubmission:
    header: Header
    claims: List[Claim] = field(default_factory=list)

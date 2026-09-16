"""
RemittanceAdvice XSD model.
CommonTypes constraints enforced in __post_init__ — violations raise immediately.
Hierarchy (high → low):
  RemittanceAdvice
    └── Header            (common_models)
    └── Claim (1..*)
          ├── Encounter (0..*)
          └── Activity (1..*)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from utils.validator.common_models import Header, DATETIME_RE, ACTIVITY_TYPES


@dataclass
class Encounter:
    facility_id: Optional[str] = None


@dataclass
class Activity:
    start: str          # dd/mm/yyyy HH:MM
    type: int
    code: str
    quantity: float
    net: float
    payment_amount: float
    id: Optional[str] = None
    list_price: Optional[float] = None
    ordering_clinician: Optional[str] = None
    clinician: Optional[str] = None
    prior_authorization_id: Optional[str] = None
    gross: Optional[float] = None
    patient_share: Optional[float] = None
    denial_code: Optional[str] = None

    def __post_init__(self):
        if not DATETIME_RE.match(self.start):
            raise ValueError(f"Activity.Start: must match dd/mm/yyyy HH:MM, got '{self.start}'")
        if self.type not in ACTIVITY_TYPES:
            raise ValueError(f"Activity.Type: '{self.type}' is not an allowed value")
        if not self.code.strip():
            raise ValueError("Activity.Code: minLength=1 violated")
        if self.id is not None and len(self.id) > 30:
            raise ValueError(f"Activity.ID: maxLength=30 violated, got {len(self.id)}")


@dataclass
class Claim:
    id: str
    id_payer: str
    payment_reference: str
    provider_id: Optional[str] = None
    denial_code: Optional[str] = None
    date_settlement: Optional[str] = None   # dd/mm/yyyy HH:MM
    encounters: List[Encounter] = field(default_factory=list)
    activities: List[Activity] = field(default_factory=list)    # 1..*

    def __post_init__(self):
        if not self.id.strip():
            raise ValueError("Claim.ID: minLength=1 violated")
        if not self.payment_reference.strip():
            raise ValueError("Claim.PaymentReference: minLength=1 violated")
        if self.date_settlement is not None and not DATETIME_RE.match(self.date_settlement):
            raise ValueError(f"Claim.DateSettlement: must match dd/mm/yyyy HH:MM, got '{self.date_settlement}'")


@dataclass
class RemittanceAdvice:
    header: Header
    claims: List[Claim] = field(default_factory=list)   # 1..*

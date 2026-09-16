"""
PriorAuthorization XSD model.
CommonTypes constraints enforced in __post_init__ — violations raise immediately.
Hierarchy (high → low):
  PriorAuthorization
    └── Header                 (common_models)
    └── Authorization (1)
          └── Activity (0..*)
                └── Observation (0..*)  (common_models)
                      Note: Value and ValueType are required in this transaction.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from utils.validator.common_models import Header, Observation, DATETIME_RE, ACTIVITY_TYPES


@dataclass
class AuthorizationActivity:
    id: str             # required, max 30 chars
    type: int
    code: str
    net: float
    payment_amount: float
    quantity: Optional[float] = None
    list_price: Optional[float] = None
    patient_share: Optional[float] = None
    denial_code: Optional[str] = None
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


@dataclass
class Authorization:
    id: str
    start: str          # dd/mm/yyyy HH:MM
    end: str            # dd/mm/yyyy HH:MM
    result: Optional[str] = None
    id_payer: Optional[str] = None
    denial_code: Optional[str] = None
    limit: Optional[float] = None
    comments: Optional[str] = None
    activities: List[AuthorizationActivity] = field(default_factory=list)

    def __post_init__(self):
        if not self.id.strip():
            raise ValueError("Authorization.ID: minLength=1 violated")
        if not DATETIME_RE.match(self.start):
            raise ValueError(f"Authorization.Start: must match dd/mm/yyyy HH:MM, got '{self.start}'")
        if not DATETIME_RE.match(self.end):
            raise ValueError(f"Authorization.End: must match dd/mm/yyyy HH:MM, got '{self.end}'")


@dataclass
class PriorAuthorization:
    header: Header
    authorization: Authorization

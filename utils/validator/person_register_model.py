"""
PersonRegister XSD model.
CommonTypes constraints enforced in __post_init__ — violations raise immediately.
Hierarchy (high → low):
  PersonRegister
    └── Header           (common_models)
    └── Person (1..*)
          └── Member (0..1)
                └── MemberContract (0..*)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from utils.validator.common_models import Header, DATE_RE

_PERSON_GENDER_VALUES = frozenset({0, 1, 9})
_MEMBER_RELATION_VALUES = frozenset({"Principal", "Spouse", "Parent", "Child", "Other"})
_POLICY_HOLDER_VALUES = frozenset({1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 99})
_CONTRACT_STATUS_VALUES = frozenset({
    "New", "Restarted", "Renewed", "Corrected", "Corrected Date",
    "Updated EmiratesIDNumber", "Cancelled", "Gap Enrollment",
    "Recon", "Newborn", "WarZone", "Visitor",
    "Newborn-correction", "Newborn-cancellation",
})


@dataclass
class MemberContract:
    package_name: str
    start_date: str         # dd/mm/yyyy
    renewal_date: str       # dd/mm/yyyy
    expiry_date: str        # dd/mm/yyyy
    gross_premium: float
    policy_holder: int      # 1=Government | 2=Gov related | 4=Private<1000 | ... | 99=Others
    payer_id: Optional[str] = None
    tpa_id: Optional[str] = None
    company_id: Optional[str] = None
    collected_premium: Optional[float] = None
    vat: Optional[float] = None
    vat_percent: Optional[float] = None
    status: Optional[str] = None

    def __post_init__(self):
        if not DATE_RE.match(self.start_date):
            raise ValueError(f"Contract.StartDate: must match dd/mm/yyyy, got '{self.start_date}'")
        if not DATE_RE.match(self.renewal_date):
            raise ValueError(f"Contract.RenewalDate: must match dd/mm/yyyy, got '{self.renewal_date}'")
        if not DATE_RE.match(self.expiry_date):
            raise ValueError(f"Contract.ExpiryDate: must match dd/mm/yyyy, got '{self.expiry_date}'")
        if self.policy_holder not in _POLICY_HOLDER_VALUES:
            raise ValueError(f"Contract.PolicyHolder: '{self.policy_holder}' is not an allowed value")
        if self.status is not None and self.status not in _CONTRACT_STATUS_VALUES:
            raise ValueError(f"Contract.Status: '{self.status}' is not an allowed value")


@dataclass
class Member:
    id: str
    relation: Optional[str] = None
    relation_to: Optional[str] = None
    relation_to_emirates_id_number: Optional[str] = None
    relation_to_unified_number: Optional[str] = None
    contracts: List[MemberContract] = field(default_factory=list)

    def __post_init__(self):
        if not self.id.strip():
            raise ValueError("Member.ID: minLength=1 violated")
        if self.relation is not None and self.relation not in _MEMBER_RELATION_VALUES:
            raise ValueError(f"Member.Relation: '{self.relation}' is not an allowed value")


@dataclass
class Person:
    birth_date: str         # dd/mm/yyyy
    gender: int             # 1=male | 0=female | 9=unknown
    nationality: str
    city: str
    emirates_id_number: str
    unified_number: Optional[int] = None
    first_name: Optional[str] = None
    first_name_en: Optional[str] = None
    middle_name_en: Optional[str] = None
    last_name_en: Optional[str] = None
    first_name_ar: Optional[str] = None
    middle_name_ar: Optional[str] = None
    last_name_ar: Optional[str] = None
    contact_number: Optional[str] = None
    nationality_code: Optional[int] = None
    city_code: Optional[int] = None
    country_of_residence: Optional[str] = None
    emirate_of_residence: Optional[str] = None
    passport_number: Optional[str] = None
    sponsor_number: Optional[str] = None
    sponsor_name_en: Optional[str] = None
    sponsor_name_ar: Optional[str] = None
    special_nationality: Optional[str] = None
    privileges: Optional[str] = None
    coc_reference_number: Optional[str] = None
    birth_certificate_number: Optional[str] = None
    member: Optional[Member] = None

    def __post_init__(self):
        if not DATE_RE.match(self.birth_date):
            raise ValueError(f"Person.BirthDate: must match dd/mm/yyyy, got '{self.birth_date}'")
        if self.gender not in _PERSON_GENDER_VALUES:
            raise ValueError(f"Person.Gender: '{self.gender}' is not an allowed value (0=female, 1=male, 9=unknown)")
        if not self.nationality.strip():
            raise ValueError("Person.Nationality: minLength=1 violated")
        if not self.city.strip():
            raise ValueError("Person.City: minLength=1 violated")
        if not self.emirates_id_number.strip():
            raise ValueError("Person.EmiratesIDNumber: minLength=1 violated")


@dataclass
class PersonRegister:
    header: Header
    persons: List[Person] = field(default_factory=list)

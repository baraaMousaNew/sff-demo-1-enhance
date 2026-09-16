"""
Parses an XML string into the appropriate transaction dataclass model.

CommonTypes __post_init__ validation fires automatically during construction,
so any structural/content violation raises ValueError immediately.
"""

from xml.etree import ElementTree as ET

from utils.validator import claim_submission_model as cs
from utils.validator import person_register_model as pr
from utils.validator import prior_authorization_model as pa
from utils.validator import prior_request_model as pq
from utils.validator import remittance_advice_model as ra
from utils.validator.common_models import Header, DxInfo, Observation, Resubmission


_PARSERS = {}   # populated below


class XMLParser:

    def parse(self, xml_text: str):
        """
        Parse xml_text and return the appropriate transaction model.

        Raises:
            ValueError: if the root tag is unknown, a required field is missing,
                        or a CommonTypes constraint is violated.
            ET.ParseError: if the XML is not well-formed.
        """
        root = ET.fromstring(xml_text)
        tag = _tag(root)
        parser = _PARSERS.get(tag)
        if not parser:
            raise ValueError(f"Unknown transaction type: '{tag}'")
        return parser(root)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _tag(el: ET.Element) -> str:
    return el.tag.split("}")[1] if "}" in el.tag else el.tag


def _text(el: ET.Element, tag: str, default=None):
    child = el.find(tag)
    if child is None or not (child.text or "").strip():
        return default
    return child.text.strip()


def _int(el: ET.Element, tag: str, default=None):
    val = _text(el, tag)
    return int(val) if val is not None else default


def _float(el: ET.Element, tag: str, default=None):
    val = _text(el, tag)
    return float(val) if val is not None else default


# ── Common sub-elements ───────────────────────────────────────────────────────

def _parse_header(el: ET.Element) -> Header:
    return Header(
        sender_id=_text(el, "SenderID", ""),
        receiver_id=_text(el, "ReceiverID", ""),
        transaction_date=_text(el, "TransactionDate", ""),
        record_count=_int(el, "RecordCount", 0),
        disposition_flag=_text(el, "DispositionFlag", ""),
    )


def _parse_dx_info(el: ET.Element) -> DxInfo:
    return DxInfo(
        type=_text(el, "Type", ""),
        code=_text(el, "Code", ""),
    )


def _parse_observation(el: ET.Element) -> Observation:
    return Observation(
        type=_text(el, "Type", ""),
        code=_text(el, "Code", ""),
        value=_text(el, "Value"),
        value_type=_text(el, "ValueType"),
    )


def _parse_resubmission(el) -> Resubmission | None:
    if el is None:
        return None
    attachment_el = el.find("Attachment")
    attachment = attachment_el.text.encode() if attachment_el is not None and attachment_el.text else None
    return Resubmission(
        type=_text(el, "Type", ""),
        comment=_text(el, "Comment", ""),
        attachment=attachment,
    )


# ── ClaimSubmission ───────────────────────────────────────────────────────────

def _parse_claim_submission(root: ET.Element) -> cs.ClaimSubmission:
    header_el = root.find("Header")
    return cs.ClaimSubmission(
        header=_parse_header(header_el) if header_el is not None else _parse_header(root),
        claims=[_parse_cs_claim(c) for c in root.findall("Claim")],
    )


def _parse_cs_claim(el: ET.Element) -> cs.Claim:
    return cs.Claim(
        id=_text(el, "ID", ""),
        id_payer=_text(el, "IDPayer"),
        member_id=_text(el, "MemberID"),
        payer_id=_text(el, "PayerID", ""),
        provider_id=_text(el, "ProviderID", ""),
        emirates_id_number=_text(el, "EmiratesIDNumber", ""),
        gross=_float(el, "Gross", 0.0),
        patient_share=_float(el, "PatientShare", 0.0),
        net=_float(el, "Net", 0.0),
        vat=_float(el, "VAT"),
        encounters=[_parse_cs_encounter(e) for e in el.findall("Encounter")],
        diagnoses=[_parse_cs_diagnosis(d) for d in el.findall("Diagnosis")],
        activities=[_parse_cs_activity(a) for a in el.findall("Activity")],
        resubmission=_parse_resubmission(el.find("Resubmission")),
        contract=_parse_cs_contract(el.find("Contract")),
    )


def _parse_cs_encounter(el: ET.Element) -> cs.Encounter:
    return cs.Encounter(
        facility_id=_text(el, "FacilityID", ""),
        type=_int(el, "Type", 0),
        patient_id=_text(el, "PatientID", ""),
        start=_text(el, "Start", ""),
        eligibility_id_payer=_text(el, "EligibilityIDPayer"),
        end=_text(el, "End"),
        start_type=_int(el, "StartType"),
        end_type=_int(el, "EndType"),
        transfer_source=_text(el, "TransferSource"),
        transfer_destination=_text(el, "TransferDestination"),
    )


def _parse_cs_diagnosis(el: ET.Element) -> cs.Diagnosis:
    return cs.Diagnosis(
        type=_text(el, "Type", ""),
        code=_text(el, "Code", ""),
        dx_info=[_parse_dx_info(d) for d in el.findall("DxInfo")],
    )


def _parse_cs_activity(el: ET.Element) -> cs.Activity:
    return cs.Activity(
        id=_text(el, "ID"),
        start=_text(el, "Start", ""),
        type=_int(el, "Type", 0),
        code=_text(el, "Code", ""),
        quantity=_float(el, "Quantity", 0.0),
        net=_float(el, "Net", 0.0),
        ordering_clinician=_text(el, "OrderingClinician"),
        clinician=_text(el, "Clinician"),
        prior_authorization_id=_text(el, "PriorAuthorizationID"),
        vat=_float(el, "VAT"),
        vat_percent=_float(el, "VATPercent"),
        date_ordered=_text(el, "DateOrdered"),
        observations=[_parse_observation(o) for o in el.findall("Observation")],
    )


def _parse_cs_contract(el) -> cs.Contract | None:
    if el is None:
        return None
    return cs.Contract(package_name=_text(el, "PackageName"))


# ── PersonRegister ────────────────────────────────────────────────────────────

def _parse_person_register(root: ET.Element) -> pr.PersonRegister:
    header_el = root.find("Header")
    return pr.PersonRegister(
        header=_parse_header(header_el) if header_el is not None else _parse_header(root),
        persons=[_parse_person(p) for p in root.findall("Person")],
    )


def _parse_person(el: ET.Element) -> pr.Person:
    member_el = el.find("Member")
    return pr.Person(
        birth_date=_text(el, "BirthDate", ""),
        gender=_int(el, "Gender", 0),
        nationality=_text(el, "Nationality", ""),
        city=_text(el, "City", ""),
        emirates_id_number=_text(el, "EmiratesIDNumber", ""),
        unified_number=_int(el, "UnifiedNumber"),
        first_name=_text(el, "FirstName"),
        first_name_en=_text(el, "FirstNameEn"),
        middle_name_en=_text(el, "MiddleNameEn"),
        last_name_en=_text(el, "LastNameEn"),
        first_name_ar=_text(el, "FirstNameAr"),
        middle_name_ar=_text(el, "MiddleNameAr"),
        last_name_ar=_text(el, "LastNameAr"),
        contact_number=_text(el, "ContactNumber"),
        nationality_code=_int(el, "NationalityCode"),
        city_code=_int(el, "CityCode"),
        country_of_residence=_text(el, "CountryOfResidence"),
        emirate_of_residence=_text(el, "EmirateOfResidence"),
        passport_number=_text(el, "PassportNumber"),
        sponsor_number=_text(el, "SponsorNumber"),
        sponsor_name_en=_text(el, "SponsorNameEn"),
        sponsor_name_ar=_text(el, "SponsorNameAr"),
        special_nationality=_text(el, "SpecialNationality"),
        privileges=_text(el, "Privileges"),
        coc_reference_number=_text(el, "CocReferenceNumber"),
        birth_certificate_number=_text(el, "BirthCertificateNumber"),
        member=_parse_member(member_el) if member_el is not None else None,
    )


def _parse_member(el: ET.Element) -> pr.Member:
    return pr.Member(
        id=_text(el, "ID", ""),
        relation=_text(el, "Relation"),
        relation_to=_text(el, "RelationTo"),
        relation_to_emirates_id_number=_text(el, "RelationToEmiratesIDNumber"),
        relation_to_unified_number=_text(el, "RelationToUnifiedNumber"),
        contracts=[_parse_member_contract(c) for c in el.findall("MemberContract")],
    )


def _parse_member_contract(el: ET.Element) -> pr.MemberContract:
    return pr.MemberContract(
        package_name=_text(el, "PackageName", ""),
        start_date=_text(el, "StartDate", ""),
        renewal_date=_text(el, "RenewalDate", ""),
        expiry_date=_text(el, "ExpiryDate", ""),
        gross_premium=_float(el, "GrossPremium", 0.0),
        policy_holder=_int(el, "PolicyHolder", 1),
        payer_id=_text(el, "PayerID"),
        tpa_id=_text(el, "TPAID"),
        company_id=_text(el, "CompanyID"),
        collected_premium=_float(el, "CollectedPremium"),
        vat=_float(el, "VAT"),
        vat_percent=_float(el, "VATPercent"),
        status=_text(el, "Status"),
    )


# ── PriorAuthorization ────────────────────────────────────────────────────────

def _parse_prior_authorization(root: ET.Element) -> pa.PriorAuthorization:
    header_el = root.find("Header")
    auth_el = root.find("Authorization")
    return pa.PriorAuthorization(
        header=_parse_header(header_el) if header_el is not None else _parse_header(root),
        authorization=_parse_pa_authorization(auth_el) if auth_el is not None else _parse_pa_authorization(root),
    )


def _parse_pa_authorization(el: ET.Element) -> pa.Authorization:
    return pa.Authorization(
        id=_text(el, "ID", ""),
        start=_text(el, "Start", ""),
        end=_text(el, "End", ""),
        result=_text(el, "Result"),
        id_payer=_text(el, "IDPayer"),
        denial_code=_text(el, "DenialCode"),
        limit=_float(el, "Limit"),
        comments=_text(el, "Comments"),
        activities=[_parse_pa_activity(a) for a in el.findall("Activity")],
    )


def _parse_pa_activity(el: ET.Element) -> pa.AuthorizationActivity:
    return pa.AuthorizationActivity(
        id=_text(el, "ID", ""),
        type=_int(el, "Type", 0),
        code=_text(el, "Code", ""),
        net=_float(el, "Net", 0.0),
        payment_amount=_float(el, "PaymentAmount", 0.0),
        quantity=_float(el, "Quantity"),
        list_price=_float(el, "ListPrice"),
        patient_share=_float(el, "PatientShare"),
        denial_code=_text(el, "DenialCode"),
        observations=[_parse_observation(o) for o in el.findall("Observation")],
    )


# ── PriorRequest ──────────────────────────────────────────────────────────────

def _parse_prior_request(root: ET.Element) -> pq.PriorRequest:
    header_el = root.find("Header")
    auth_el = root.find("Authorization")
    return pq.PriorRequest(
        header=_parse_header(header_el) if header_el is not None else _parse_header(root),
        authorization=_parse_pq_authorization(auth_el) if auth_el is not None else _parse_pq_authorization(root),
    )


def _parse_pq_authorization(el: ET.Element) -> pq.Authorization:
    enc_el = el.find("Encounter")
    return pq.Authorization(
        type=_text(el, "Type", ""),
        id=_text(el, "ID", ""),
        member_id=_text(el, "MemberID", ""),
        payer_id=_text(el, "PayerID", ""),
        emirates_id_number=_text(el, "EmiratesIDNumber", ""),
        id_payer=_text(el, "IDPayer"),
        date_ordered=_text(el, "DateOrdered"),
        encounter=_parse_pq_encounter(enc_el) if enc_el is not None else None,
        diagnoses=[_parse_pq_diagnosis(d) for d in el.findall("Diagnosis")],
        activities=[_parse_pq_activity(a) for a in el.findall("Activity")],
        resubmission=_parse_resubmission(el.find("Resubmission")),
    )


def _parse_pq_encounter(el: ET.Element) -> pq.Encounter:
    return pq.Encounter(
        facility_id=_text(el, "FacilityID", ""),
        type=_int(el, "Type"),
        start=_text(el, "Start"),
        end=_text(el, "End"),
    )


def _parse_pq_diagnosis(el: ET.Element) -> pq.Diagnosis:
    return pq.Diagnosis(
        type=_text(el, "Type", ""),
        code=_text(el, "Code", ""),
        dx_info=[_parse_dx_info(d) for d in el.findall("DxInfo")],
    )


def _parse_pq_activity(el: ET.Element) -> pq.Activity:
    return pq.Activity(
        id=_text(el, "ID", ""),
        start=_text(el, "Start"),
        type=_int(el, "Type", 0),
        code=_text(el, "Code", ""),
        net=_float(el, "Net", 0.0),
        quantity=_float(el, "Quantity"),
        ordering_clinician=_text(el, "OrderingClinician"),
        clinician=_text(el, "Clinician"),
        observations=[_parse_observation(o) for o in el.findall("Observation")],
    )


# ── RemittanceAdvice ──────────────────────────────────────────────────────────

def _parse_remittance_advice(root: ET.Element) -> ra.RemittanceAdvice:
    header_el = root.find("Header")
    return ra.RemittanceAdvice(
        header=_parse_header(header_el) if header_el is not None else _parse_header(root),
        claims=[_parse_ra_claim(c) for c in root.findall("Claim")],
    )


def _parse_ra_claim(el: ET.Element) -> ra.Claim:
    return ra.Claim(
        id=_text(el, "ID", ""),
        id_payer=_text(el, "IDPayer", ""),
        payment_reference=_text(el, "PaymentReference", ""),
        provider_id=_text(el, "ProviderID"),
        denial_code=_text(el, "DenialCode"),
        date_settlement=_text(el, "DateSettlement"),
        encounters=[_parse_ra_encounter(e) for e in el.findall("Encounter")],
        activities=[_parse_ra_activity(a) for a in el.findall("Activity")],
    )


def _parse_ra_encounter(el: ET.Element) -> ra.Encounter:
    return ra.Encounter(facility_id=_text(el, "FacilityID"))


def _parse_ra_activity(el: ET.Element) -> ra.Activity:
    return ra.Activity(
        start=_text(el, "Start", ""),
        type=_int(el, "Type", 0),
        code=_text(el, "Code", ""),
        quantity=_float(el, "Quantity", 0.0),
        net=_float(el, "Net", 0.0),
        payment_amount=_float(el, "PaymentAmount", 0.0),
        id=_text(el, "ID"),
        list_price=_float(el, "ListPrice"),
        ordering_clinician=_text(el, "OrderingClinician"),
        clinician=_text(el, "Clinician"),
        prior_authorization_id=_text(el, "PriorAuthorizationID"),
        gross=_float(el, "Gross"),
        patient_share=_float(el, "PatientShare"),
        denial_code=_text(el, "DenialCode"),
    )


# ── Parser registry ───────────────────────────────────────────────────────────

_PARSERS = {
    "Claim.Submission":     _parse_claim_submission,
    "Person.Register":      _parse_person_register,
    "Prior.Authorization":  _parse_prior_authorization,
    "Prior.Request":        _parse_prior_request,
    "Remittance.Advice":    _parse_remittance_advice,
}

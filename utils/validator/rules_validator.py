"""
Business rules validator.

Each transaction type has its own validator class that collects ALL errors/warnings
(never raises). Rules that require a DB resource wrap the resource access in a
try/except so that unfinished TODO SQL queries don't abort the validation run.

Usage:
    results = RulesValidator().validate(model, resource_provider)
"""

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_DOWN

from utils.validator.validation_result import ValidationResult
from utils.validator.disabled_rules import DISABLED_RULES
from utils.validator import claim_submission_model as cs
from utils.validator import person_register_model as pr
from utils.validator import prior_authorization_model as pa
from utils.validator import prior_request_model as pq
from utils.validator import remittance_advice_model as ra

# ── Hardcoded constants ────────────────────────────────────────────────────────

_SELF_PAY_PAYER_IDS = frozenset({
    "SelfPay", "ProFormaPayer", "MedicalTourismSelfPay", "MedicalTourismOther", "CSR",
})
_DUMMY_EMIRATES_IDS = frozenset({
    "000-0000-0000000-0", "111-1111-1111111-1",
    "222-2222-2222222-2", "999-9999-9999999-9",
})
_THIQA_PACKAGES = frozenset({
    "Thiqa 1", "Thiqa 2", "Thiqa 3", "Thiqa 4",
    "101", "102", "103", "104", "105", "106", "107", "108", "109", "110",
    "107A", "107B",
})
_HAAD_RECEIVER_ID = "HAAD"
_SHADOW_FLAGS = frozenset({
    "PTE_SHADOW_NOT_FOR_PAYMENT_SUBMIT", "PTE_SHADOW_NOT_FOR_PAYMENT_VALIDATE_ONLY",
    "SHADOW_NOT_FOR_PAYMENT_SUBMIT", "SHADOW_NOT_FOR_PAYMENT_VALIDATE_ONLY",
})

_RULE_21_CUTOFF    = datetime(2010, 10, 1)
_RULE_153_CUTOFF   = datetime(2010, 3, 25)

_VALID_OBSERVATION_TYPES = frozenset({
    "CPT", "HL7v3 Native", "LOINC", "SNOMED CT", "Text",
    "File", "Flags", "Universal Dental", "Episode",
})
_VALID_DX_INFO_TYPES = frozenset({
    "POA", "Year of Onset", "Birth Weight", "ICD10-GM", "ICD10-CM", "KCD",
})


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except (ValueError, TypeError):
        return None


def _parse_datetime(dt_str: str):
    try:
        dt = datetime.strptime(dt_str, "%d/%m/%Y %H:%M")
        return dt.replace(hour=0, minute=0, second=0)
    except (ValueError, TypeError):
        return None


def _round_half_down(value: float, places: int) -> float:
    d = Decimal(str(value))
    q = Decimal("0." + "0" * places)
    return float(d.quantize(q, rounding=ROUND_HALF_DOWN))


def _is_valid_emirates_id(eid: str) -> bool:
    """Luhn checksum for UAE Emirates ID (XXX-XXXX-XXXXXXX-X, 18 chars with hyphens)."""
    s = eid.replace(" ", "")
    if len(s) != 18:
        return False
    parts = s.split("-")
    if len(parts) != 4 or len(parts[0]) != 3 or len(parts[1]) != 4 or len(parts[2]) != 7 or len(parts[3]) != 1:
        return False
    digits = "".join(parts)
    if not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(digits):
        n = int(ch)
        if (len(digits) - 1 - i) % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _first_enc_start(claim: cs.Claim):
    """Return the earliest encounter start datetime for a claim (or None)."""
    starts = [_parse_datetime(e.start) for e in claim.encounters if e.start]
    starts = [s for s in starts if s is not None]
    return min(starts) if starts else None


# ── Public dispatcher ──────────────────────────────────────────────────────────

class RulesValidator:
    _VALIDATORS = {}

    def validate(self, model, resources) -> list[ValidationResult]:
        validator_cls = self._VALIDATORS.get(type(model))
        if not validator_cls:
            return [ValidationResult(
                rule_id="0", transaction=type(model).__name__, type="ERROR",
                message=f"No rules validator registered for {type(model).__name__}",
            )]
        return validator_cls().validate(model, resources)


# ── Base class ─────────────────────────────────────────────────────────────────

class _BaseValidator:
    TRANSACTION: str = ""

    def validate(self, model, resources) -> list[ValidationResult]:
        disabled = DISABLED_RULES.get(self.TRANSACTION, frozenset())
        results = []
        for rule_fn in self._rules():
            if rule_fn.__name__[6:] in disabled:  # strip "_rule_" prefix (6 chars)
                continue
            try:
                for r in rule_fn(model, resources):
                    if not r.trace:
                        # Auto-trace: description from "Fires when:" comment + full message.
                        # Lets every row expand; rules with hand-written traces override this.
                        desc = self._RULE_DESCRIPTIONS.get(r.rule_id, "")
                        steps = (f"Rule check: {desc}",) if desc else ()
                        steps += (f"Violation: {r.message}",)
                        r = ValidationResult(r.rule_id, r.transaction, r.type,
                                             r.message, r.is_active, steps)
                    results.append(r)
            except Exception:
                pass
        return results

    _RULE_DESCRIPTIONS: dict[str, str] = {}

    def _rules(self):
        return []

    def _err(self, rule_id, message, trace: tuple[str, ...] = ()) -> ValidationResult:
        return ValidationResult(rule_id=str(rule_id), transaction=self.TRANSACTION, type="ERROR", message=message, trace=trace)

    def _warn(self, rule_id, message, trace: tuple[str, ...] = ()) -> ValidationResult:
        return ValidationResult(rule_id=str(rule_id), transaction=self.TRANSACTION, type="WARNING", message=message, trace=trace)

    def _inactive_err(self, rule_id, message, trace: tuple[str, ...] = ()) -> ValidationResult:
        return ValidationResult(rule_id=str(rule_id), transaction=self.TRANSACTION, type="ERROR", message=message, is_active=False, trace=trace)

    def _inactive_warn(self, rule_id, message) -> ValidationResult:
        return ValidationResult(rule_id=str(rule_id), transaction=self.TRANSACTION, type="WARNING", message=message, is_active=False)


# ── ClaimSubmission rules ──────────────────────────────────────────────────────

class _ClaimSubmissionValidator(_BaseValidator):
    TRANSACTION = "Claim.Submission"

    _RULE_DESCRIPTIONS = {
        "9":   "Header.RecordCount does not match the actual number of Claim elements",
        "10":  "Any Claim.PayerID is missing or blank",
        "11":  "ReceiverID is a HAAD payer and sender is a provider, but Claim.PayerID ≠ ReceiverID",
        "12":  "ReceiverID is 'HAAD', sender is a provider, and PayerID is not a self-pay value",
        "13":  "Sender is a HAAD payer and Claim.PayerID ≠ SenderID",
        "15":  "ReceiverID is a TPA and Claim.PayerID is not a valid insurer license",
        "16":  "Any Claim.ProviderID is missing or blank",
        "17":  "Sender is a provider and Claim.ProviderID ≠ SenderID",
        "18":  "ProviderID is present but not a recognised HAAD/DHA/MOH facility license",
        "19":  "EmiratesIDNumber is non-dummy and fails Luhn/format check",
        "25":  "Claim.Gross < (Net + PatientShare) rounded to 3 decimal places",
        "27":  "Claim.Net does not equal the sum of Activity.Net values (>0.01 tolerance)",
        "28":  "A Claim does not have exactly one Principal diagnosis",
        "29":  ">5% of qualifying activities (from 2009-12-01) use service code '12'",
        "30":  "Header.DispositionFlag is not in the allowed set for Claim.Submission",
        "31":  "ProviderID and Encounter.FacilityID have mismatched '@' prefix or license validity (from 2009-05-01)",
        "32":  "Any Encounter.FacilityID is missing or blank",
        "33":  "(INACTIVE) Encounter.Start ≤ 2010-06-04, SenderID in HAAD/DHA/MOH providers, FacilityID ≠ SenderID",
        "35":  "(INACTIVE) Encounter.Type is None",
        "36":  "Encounter.Type=7 (National Screening) is sent to the wrong receiver for the sender type",
        "37":  "Encounter.Type=7 sender is HAAD-licensed provider but receiver is not D001, or vice versa",
        "38":  "Inpatient Encounter (Type=3 or 4) has no Encounter.End",
        "40":  "Encounter.End exists and is before Encounter.Start",
        "41":  "Inpatient Encounter (Type=3 or 4) has no Encounter.EndType",
        "42":  "Encounter.StartType=3 or 8 and TransferSource is missing or invalid",
        "43":  "Encounter.EndType=4 or 7 and TransferDestination is missing or invalid",
        "44":  "(INACTIVE) Activity.Observation.Type is not in the allowed list",
        "45":  "Observation.Type='LOINC' but code is not in LOINC master data",
        "46":  "Observation.Value is empty for non-exempt observation types",
        "47":  "Observation.ValueType is empty for non-exempt observation types",
        "48":  "(INACTIVE) Observation.Type=LOINC and value is not numeric",
        "51":  "(INACTIVE) Diagnosis.Type is not in valid set",
        "52":  "(INACTIVE) Diagnosis.Code not in ICD9/ICD10 registry",
        "54":  "SenderID is not a recognised provider, payer, TPA, or SEHA license",
        "57":  "ReceiverID is not a recognised provider, payer, TPA, or HAAD",
        "59":  "Sender is a payer/TPA but ReceiverID is not 'HAAD'",
        "61":  "Header.TransactionDate does not match today's date",
        "62":  "Any Activity.Type is outside the allowed set {3,4,5,6,8,9}",
        "63":  "SenderID is not null and any Activity.Code is null/empty/whitespace",
        "64":  "(INACTIVE) Activity.Start ≥ 2014-09-01, sender not in exclusion list, Activity.Code not in ICD9 registry",
        "65":  "Activity.Type=3 (CPT) and code is not a valid CPT code on the activity date",
        "66":  "Activity.Type=4 (HCPCS) and code is not a valid HCPCS code on the activity date",
        "67":  "Activity.Type=5 (Trade Drug) and code is not a valid Trade Drug on the activity date",
        "68":  "Activity.Type=6 (Dental) and code is not a valid USCLS code on the activity date",
        "69":  "Activity.Type=8 (Service) and code is not a valid Service code on the activity date",
        "70":  "Activity.Type=9 (DRG) and code is not a valid DRG code on the activity date",
        "71":  "Activity before 01/06/2014 has no Clinician value",
        "73":  "Both ProviderID and Clinician are present but one uses '@' and the other has a license",
        "74":  "FacilityID and Clinician are present but one uses '@' while the other has a license",
        "75":  "Activity.Quantity ≤ 0 (not applicable to National Screening encounters)",
        "81":  "Activity.Start is outside the [Encounter.Start, Encounter.End] window",
        "87":  "Sender is a payer/TPA (from 2010-10-01) and any qualifying Claim.IDPayer is empty",
        "88":  "Dental activity (Type=6) with a tooth-requiring code has no Universal Dental observation",
        "90":  "Universal Dental observation code is not a valid tooth number (from 2010-10-01)",
        "91":  "Non-dental activity (Type≠6) has a Universal Dental observation (from 2010-10-01)",
        "93":  "Same (Claim.ID, ProviderID) pair appears more than once in the transaction",
        "94":  "(INACTIVE) Claim.ID+ProviderID combo repeated for qualifying activities from 2017-09-23",
        "95":  "Sender is a provider and Claim.IDPayer is non-empty without a valid resubmission type",
        "97":  "(INACTIVE) Resubmission.Type=legacy activity with Type≠5 from 2010-06-07",
        "98":  "Clinician is a pharmacist and activity date is 2010-10-01 to 2013-12-03",
        "110": "Activity.ID is duplicated within a claim (for activities from 2010-06-07)",
        "112": "Correction/internal-complaint resubmission has no matching Remittance Advice in the DB",
        "118": "The same Claim.ID was already submitted by this sender",
        "119": "MemberID is not registered for the stated payer",
        "120": "Encounter.Start is after TransactionDate (effective from 2011-06-15)",
        "127": "Service codes 15–20 used in outpatient encounter types (from 2016-06-01)",
        "130": "Some Activities have Activity.ID and others do not within the same claim",
        "142": "DRG activity (Type=9) is used for an encounter on or before 31/07/2010",
        "143": "Encounter.End is after TransactionDate (from 2011-06-15)",
        "144": "Encounter.Start (with no End) is more than one year before TransactionDate for non-resubmitted claims",
        "145": "Duplicate Diagnosis codes exist in a Claim",
        "146": "Activity.Quantity ≥ 2001 or has more than 4 decimal places (from 2014-06-01)",
        "147": "Activity.Net < 0 for activities from 2014-10-02",
        "149": "Claim.Net < 0 (from 2011-06-15)",
        "150": "Claim.PatientShare < 0 (from 2011-06-15)",
        "152": "Claim.MemberID is empty (from 2010-11-28)",
        "187": "Activity.Start is after TransactionDate (from 2011-06-15)",
        "193": "Encounter.StartType=7 (Continuing) used by a facility other than MF3048 before 2011-09-26",
        "194": "Encounter.EndType=6 (Not discharged) used by a facility other than MF3048 before 2011-09-26",
        "200": "Any Activity.ID is missing or blank",
        "201": "Resubmission Activity IDs don't match the original claim's Activity IDs",
        "203": "OrderingClinician is missing for activities from 2014-06-01, or present before that date",
        "205": "OrderingClinician and ProviderID have mismatched '@' prefix or license validity",
        "206": "OrderingClinician and FacilityID have mismatched '@' prefix or license validity",
        "207": "OrderingClinician is a pharmacist (from 2014-09-01)",
        "238": "DxInfo is present on a claim with encounter before 01/12/2014",
        "243": "DxInfo.Type='POA' is used on a non-inpatient encounter (from 2014-12-01)",
        "244": "DxInfo.Type='POA' has an invalid code — must be Y, N, U, W, or 1 (from 2014-12-01)",
        "245": "A Diagnosis has more than one DxInfo entry with type='POA'",
        "282": "Clinician does not have a valid DoH HPL license on the activity date (from 2018-06-01)",
        "283": "Clinician is on the insurance exclusion list on the activity date (from 2018-06-01)",
        "286": "Activity.Clinician is missing for activities from 01/09/2018",
        "303": "Header.RecordCount exceeds 500",
    }

    def _rules(self):
        return [
            self._rule_9,   self._rule_10,  self._rule_11,  self._rule_12,  self._rule_13,
            self._rule_14,  self._rule_15,  self._rule_16,  self._rule_17,  self._rule_18,
            self._rule_19,  self._rule_22,  self._rule_23,  self._rule_24,  self._rule_25,
            self._rule_26,  self._rule_27,  self._rule_28,  self._rule_29,  self._rule_30,
            self._rule_31,  self._rule_32,  self._rule_33,  self._rule_35,  self._rule_36,
            self._rule_37,  self._rule_38,  self._rule_39,  self._rule_40,  self._rule_41,
            self._rule_42,  self._rule_43,  self._rule_44,  self._rule_45,  self._rule_46,
            self._rule_47,  self._rule_48,  self._rule_51,  self._rule_52,  self._rule_54,
            self._rule_57,  self._rule_59,  self._rule_61,  self._rule_62,  self._rule_63,
            self._rule_64,  self._rule_65,  self._rule_66,  self._rule_67,  self._rule_68,
            self._rule_69,  self._rule_70,  self._rule_71,  self._rule_73,  self._rule_74,
            self._rule_75,  self._rule_76,  self._rule_81,  self._rule_87,  self._rule_88,
            self._rule_89,  self._rule_90,  self._rule_91,  self._rule_93,  self._rule_94,
            self._rule_95,  self._rule_97,  self._rule_98,  self._rule_110, self._rule_112,
            self._rule_113, self._rule_118, self._rule_119, self._rule_120, self._rule_127,
            self._rule_130, self._rule_138, self._rule_139, self._rule_142, self._rule_143,
            self._rule_144, self._rule_145, self._rule_146, self._rule_147, self._rule_149,
            self._rule_150, self._rule_152, self._rule_155, self._rule_187, self._rule_193,
            self._rule_194, self._rule_200, self._rule_201, self._rule_203, self._rule_205,
            self._rule_206, self._rule_207, self._rule_233, self._rule_234, self._rule_238,
            self._rule_239, self._rule_243, self._rule_244, self._rule_245, self._rule_247,
            self._rule_248, self._rule_281, self._rule_282, self._rule_283, self._rule_286,
            self._rule_287, self._rule_288, self._rule_289, self._rule_290, self._rule_291,
            self._rule_292_1, self._rule_292_2, self._rule_292_3, self._rule_292_4,
            self._rule_292_5, self._rule_292_6,
            self._rule_295, self._rule_296, self._rule_297, self._rule_298, self._rule_299,
            self._rule_300, self._rule_301, self._rule_302, self._rule_303, self._rule_304,
            self._rule_305, self._rule_306, self._rule_307, self._rule_308, self._rule_309,
            self._rule_313, self._rule_314, self._rule_315, self._rule_316, self._rule_317,
            self._rule_318, self._rule_319, self._rule_320, self._rule_321, self._rule_322,
            self._rule_323, self._rule_324, self._rule_325, self._rule_326, self._rule_327,
            self._rule_341, self._rule_342, self._rule_343, self._rule_344, self._rule_345,
            self._rule_356, self._rule_357, self._rule_358, self._rule_359, self._rule_360,
            self._rule_363, self._rule_364, self._rule_365, self._rule_366, self._rule_369,
            self._rule_370, self._rule_374, self._rule_377, self._rule_378, self._rule_380,
            self._rule_381, self._rule_384, self._rule_385, self._rule_386, self._rule_387,
        ]

    # ── Claim-level header checks ──────────────────────────────────────────────

    # Fires when: Header.RecordCount does not match the actual number of Claim elements
    def _rule_9(self, model: cs.ClaimSubmission, res) -> list:
        actual = len(model.claims)
        if model.header.record_count != actual:
            return [self._err(9, f"Header.RecordCount is {model.header.record_count} but {actual} Claim element(s) found",
                trace=(
                    f"Header.RecordCount: {model.header.record_count}",
                    f"Actual Claim elements found: {actual}",
                    f"Mismatch → VIOLATION",
                ))]
        return []

    # Fires when: any Claim.PayerID is missing or blank
    def _rule_10(self, model: cs.ClaimSubmission, res) -> list:
        return [self._err(10, f"Claim '{c.id}': PayerID must have a value",
                trace=(f"Claim.ID: '{c.id}'", f"Claim.PayerID: '{c.payer_id}' → empty → VIOLATION"))
                for c in model.claims if not c.payer_id or not c.payer_id.strip()]

    # Fires when: ReceiverID is a HAAD payer and sender is a provider, but Claim.PayerID ≠ ReceiverID
    def _rule_11(self, model: cs.ClaimSubmission, res) -> list:
        receiver, sender = model.header.receiver_id, model.header.sender_id
        if not res.is_haad_payer(receiver) or not res.is_any_provider(sender):
            return []
        errors = []
        for c in model.claims:
            if c.payer_id != receiver:
                trace = (
                    f"Condition 1 — ReceiverID: '{receiver}' → is a HAAD payer ✓",
                    f"Condition 2 — SenderID: '{sender}' → is a provider ✓",
                    f"Condition 3 — Claim.PayerID: '{c.payer_id}' ≠ ReceiverID '{receiver}' → VIOLATION",
                )
                errors.append(self._err(11, f"Claim '{c.id}': PayerID '{c.payer_id}' must equal Header.ReceiverID '{receiver}'", trace=trace))
        return errors

    # Fires when: ReceiverID is 'HAAD', sender is a provider, and PayerID is not a self-pay value
    def _rule_12(self, model: cs.ClaimSubmission, res) -> list:
        if model.header.receiver_id != _HAAD_RECEIVER_ID:
            return []
        sender = model.header.sender_id
        if not res.is_any_provider(sender):
            return []
        errors = []
        for c in model.claims:
            if c.payer_id not in _SELF_PAY_PAYER_IDS:
                trace = (
                    f"Condition 1 — ReceiverID: '{model.header.receiver_id}' = 'HAAD' ✓",
                    f"Condition 2 — SenderID: '{sender}' → is a provider ✓",
                    f"Condition 3 — Claim.PayerID: '{c.payer_id}' → not in self-pay values → VIOLATION",
                )
                errors.append(self._err(12, f"Claim '{c.id}': PayerID '{c.payer_id}' is not valid when ReceiverID is 'HAAD'", trace=trace))
        return errors

    # Fires when: sender is a HAAD payer and Claim.PayerID ≠ SenderID
    def _rule_13(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        if not res.is_haad_payer(sender):
            return []
        errors = []
        for c in model.claims:
            if c.payer_id != sender:
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → is a HAAD payer ✓",
                    f"Condition 2 — Claim.PayerID: '{c.payer_id}' ≠ SenderID '{sender}' → VIOLATION",
                )
                errors.append(self._err(13, f"Claim '{c.id}': PayerID '{c.payer_id}' must equal Header.SenderID '{sender}'", trace=trace))
        return errors

    # Fires when: ReceiverID is a TPA and Claim.PayerID is not a valid insurer license
    def _rule_15(self, model: cs.ClaimSubmission, res) -> list:
        receiver = model.header.receiver_id
        if not res.is_haad_tpa(receiver):
            return []
        errors = []
        for c in model.claims:
            pid = c.payer_id
            if not pid or pid.startswith("@"):
                continue
            if not res.is_active_insurer_or_other(pid):
                trace = (
                    f"Condition 1 — ReceiverID: '{receiver}' → is a HAAD TPA ✓",
                    f"Condition 2 — Claim.PayerID: '{pid}' → not '@'-prefixed → license check applies",
                    f"Condition 3 — Insurer license lookup: '{pid}' → NOT a valid active insurer → VIOLATION",
                )
                errors.append(self._err(15, f"Claim '{c.id}': PayerID '{pid}' is not a valid insurer license number", trace=trace))
        return errors

    # Fires when: any Claim.ProviderID is missing or blank
    def _rule_16(self, model: cs.ClaimSubmission, res) -> list:
        return [self._err(16, f"Claim '{c.id}': ProviderID must have value",
                trace=(f"Claim.ID: '{c.id}'", f"Claim.ProviderID: '{c.provider_id}' → empty → VIOLATION"))
                for c in model.claims if not c.provider_id or not c.provider_id.strip()]

    # Fires when: sender is a provider and Claim.ProviderID ≠ SenderID
    def _rule_17(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        if not res.is_any_provider(sender):
            return []
        errors = []
        for c in model.claims:
            if c.provider_id != sender:
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → is a provider ✓",
                    f"Condition 2 — Claim.ProviderID: '{c.provider_id}' ≠ SenderID '{sender}' → VIOLATION",
                )
                errors.append(self._err(17, f"Claim '{c.id}': ProviderID '{c.provider_id}' must equal Header.SenderID '{sender}'", trace=trace))
        return errors

    # Fires when: ProviderID is present but not a recognised HAAD/DHA/MOH facility license
    def _rule_18(self, model: cs.ClaimSubmission, res) -> list:
        if not model.header.sender_id:
            return []
        errors = []
        for c in model.claims:
            pid = c.provider_id
            if not pid or pid.startswith("@"):
                continue
            haad_ok = res.is_any_provider(pid)
            dha_moh_ok = res.is_dha_moh_provider(pid)
            if not haad_ok and not dha_moh_ok:
                trace = (
                    f"Condition 1 — Claim.ProviderID: '{pid}' → not '@'-prefixed → license check applies",
                    f"Condition 2 — HAAD provider lookup: '{pid}' → NOT FOUND",
                    f"Condition 3 — DHA/MOH provider lookup: '{pid}' → NOT FOUND → VIOLATION",
                    f"Note: license IDs are case-sensitive. Verify exact casing in the provider registry.",
                )
                errors.append(self._err(18, f"Claim '{c.id}': ProviderID '{pid}' does not match a known HAAD/DHA/MOH facility license", trace=trace))
        return errors

    # Fires when: EmiratesIDNumber is non-dummy and fails Luhn/format check
    def _rule_19(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            eid = c.emirates_id_number
            if eid in _DUMMY_EMIRATES_IDS:
                continue
            if "-" not in eid:
                continue
            if not _is_valid_emirates_id(eid):
                errors.append(self._err(19, f"Claim '{c.id}': EmiratesIDNumber '{eid}' contains incorrect value",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"EmiratesIDNumber: '{eid}'",
                        f"Luhn checksum / format validation → FAILED → VIOLATION",
                        f"Expected format: XXX-XXXX-XXXXXXX-X (18 chars with hyphens)",
                    )))
        return errors

    # ── Financial checks ───────────────────────────────────────────────────────

    # Fires when: Claim.Gross < (Net + PatientShare) rounded to 3 decimal places
    def _rule_25(self, model: cs.ClaimSubmission, res) -> list:
        if model.header.record_count is None:
            return []
        errors = []
        for c in model.claims:
            threshold = _round_half_down(c.net + c.patient_share, 3)
            if c.gross < threshold:
                errors.append(self._err(25, f"Claim '{c.id}': Gross ({c.gross}) must be >= Net + PatientShare rounded = {threshold}",
                    trace=(
                        f"Claim.Gross: {c.gross}",
                        f"Claim.Net: {c.net}",
                        f"Claim.PatientShare: {c.patient_share}",
                        f"Net + PatientShare (rounded 3dp): {threshold}",
                        f"{c.gross} < {threshold} → VIOLATION",
                    )))
        return errors

    # Fires when: Claim.Net does not equal the sum of Activity.Net values (>0.01 tolerance)
    def _rule_27(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            act_sum = sum(a.net for a in c.activities)
            if abs(c.net - act_sum) > 0.01:
                errors.append(self._err(27, f"Claim '{c.id}': Net ({c.net}) != sum of Activity.Net values ({act_sum:.4f})",
                    trace=(
                        f"Claim.Net: {c.net}",
                        f"Sum of Activity.Net values: {act_sum:.4f}",
                        f"Difference: {abs(c.net - act_sum):.4f} > 0.01 tolerance → VIOLATION",
                    )))
        return errors

    # Fires when: a Claim does not have exactly one Principal diagnosis
    def _rule_28(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            count = sum(1 for d in c.diagnoses if d.type == "Principal")
            if count != 1:
                all_types = [d.type for d in c.diagnoses]
                errors.append(self._err(28, f"Claim '{c.id}': must have exactly one Principal diagnosis (found {count})",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Diagnosis types: {all_types}",
                        f"Principal diagnosis count: {count} (expected 1) → VIOLATION",
                    )))
        return errors

    # Fires when: >5% of qualifying activities (from 2009-12-01) use service code '12'
    def _rule_29(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2009, 12, 1):
            return []
        errors = []
        for c in model.claims:
            qualifying = [a for a in c.activities
                          if _parse_datetime(a.start) is not None
                          and _parse_datetime(a.start) >= datetime(2009, 12, 1)]
            total = len(qualifying)
            if total == 0:
                continue
            code12 = sum(1 for a in qualifying if a.type == 8 and a.code == "12")
            if code12 > 0 and (code12 / total) * 100 > 5:
                errors.append(self._err(29, f"Claim '{c.id}': {code12}/{total} activities are service code 12 ({(code12/total)*100:.1f}% > 5%)",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Qualifying activities (start ≥ 01/12/2009): {total}",
                        f"Activities with service code 12: {code12}",
                        f"Percentage: {(code12/total)*100:.1f}% > 5% threshold → VIOLATION",
                    )))
        return errors

    # ── Provider / encounter facility cross-checks ────────────────────────────

    # Fires when: ProviderID and Encounter.FacilityID have mismatched '@' prefix or license validity (from 2009-05-01, not in exclusion list 1)
    def _rule_31(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2009, 5, 1):
            return []
        sender = model.header.sender_id
        if res.in_exclusion_list_1(sender):
            return []
        errors = []
        for c in model.claims:
            pid = c.provider_id or ""
            for enc in c.encounters:
                fid = enc.facility_id or ""
                if not pid and not fid:
                    continue
                pid_at = pid.startswith("@")
                fid_at = fid.startswith("@")
                pid_valid = pid_at or res.is_any_provider(pid)
                fid_valid = fid_at or res.is_any_provider(fid)
                if pid and fid:
                    if (pid_at and not fid_at) or (fid_at and not pid_at):
                        trace = (
                            f"Condition 1 — SenderID: '{sender}' → not in exclusion list ✓",
                            f"Condition 2 — ProviderID: '{pid}' → '@'-prefix: {pid_at}",
                            f"Condition 3 — FacilityID: '{fid}' → '@'-prefix: {fid_at}",
                            f"Condition 4 — '@' prefix mismatch: one has '@', the other does not → VIOLATION",
                        )
                        errors.append(self._err(31, f"Claim '{c.id}': ProviderID and Encounter.FacilityID must both use '@' or both have valid licenses", trace=trace))
                    elif pid_valid and not fid_valid:
                        trace = (
                            f"Condition 1 — SenderID: '{sender}' → not in exclusion list ✓",
                            f"Condition 2 — ProviderID: '{pid}' → valid HAAD license ✓",
                            f"Condition 3 — FacilityID: '{fid}' → NOT a valid HAAD provider → VIOLATION",
                        )
                        errors.append(self._err(31, f"Claim '{c.id}': Encounter FacilityID '{fid}' must have a valid HAAD license", trace=trace))
                    elif fid_valid and not pid_valid:
                        trace = (
                            f"Condition 1 — SenderID: '{sender}' → not in exclusion list ✓",
                            f"Condition 2 — FacilityID: '{fid}' → valid HAAD license ✓",
                            f"Condition 3 — ProviderID: '{pid}' → NOT a valid HAAD provider → VIOLATION",
                        )
                        errors.append(self._err(31, f"Claim '{c.id}': ProviderID '{pid}' must have a valid HAAD license", trace=trace))
                    elif not pid_valid and not fid_valid:
                        trace = (
                            f"Condition 1 — SenderID: '{sender}' → not in exclusion list ✓",
                            f"Condition 2 — ProviderID: '{pid}' → NOT a valid HAAD provider",
                            f"Condition 3 — FacilityID: '{fid}' → NOT a valid HAAD provider → VIOLATION (both invalid)",
                        )
                        errors.append(self._err(31, f"Claim '{c.id}': Both ProviderID '{pid}' and Encounter FacilityID '{fid}' must have valid HAAD licenses or use '@'", trace=trace))
        return errors

    # Fires when: any Encounter.FacilityID is missing or blank
    def _rule_32(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if not enc.facility_id or not enc.facility_id.strip():
                    errors.append(self._err(32, f"Claim '{c.id}': Encounter FacilityID must have value",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Encounter.FacilityID: '{enc.facility_id}' → empty → VIOLATION",
                        )))
        return errors

    # Fires when: Encounter.Type=7 (National Screening) is sent to the wrong receiver for the sender type
    def _rule_36(self, model: cs.ClaimSubmission, res) -> list:
        receiver = model.header.receiver_id
        sender = model.header.sender_id
        if not receiver:
            return []
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.type != 7:
                    continue
                if receiver == "D001" and not res.is_haad_provider(sender):
                    trace = (
                        f"Condition 1 — Encounter.Type: 7 (National Screening) ✓",
                        f"Condition 2 — ReceiverID: '{receiver}' = 'D001' ✓",
                        f"Condition 3 — SenderID: '{sender}' → is HAAD provider: False → VIOLATION",
                    )
                    errors.append(self._err(36, f"Claim '{c.id}': Only HAAD-licensed provider or payer D001 may send National Screening claim to D001 (sender='{sender}')", trace=trace))
                elif receiver == _HAAD_RECEIVER_ID and sender != "D001":
                    trace = (
                        f"Condition 1 — Encounter.Type: 7 (National Screening) ✓",
                        f"Condition 2 — ReceiverID: '{receiver}' = 'HAAD' ✓",
                        f"Condition 3 — SenderID: '{sender}' ≠ 'D001' → only D001 may send to HAAD → VIOLATION",
                    )
                    errors.append(self._err(36, f"Claim '{c.id}': Only payer D001 may send National Screening claim to HAAD (sender='{sender}')", trace=trace))
        return errors

    # Fires when: Encounter.Type=7 sender is HAAD-licensed provider but receiver is not D001, or D001 but receiver is not HAAD
    def _rule_37(self, model: cs.ClaimSubmission, res) -> list:
        receiver = model.header.receiver_id
        sender = model.header.sender_id
        if not receiver:
            return []
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.type != 7:
                    continue
                if res.is_haad_provider(sender) and receiver != "D001":
                    trace = (
                        f"Condition 1 — Encounter.Type: 7 (National Screening) ✓",
                        f"Condition 2 — SenderID: '{sender}' → is a HAAD provider ✓",
                        f"Condition 3 — ReceiverID: '{receiver}' ≠ 'D001' → HAAD providers must send to D001 → VIOLATION",
                    )
                    errors.append(self._err(37, f"Claim '{c.id}': HAAD-licensed provider must send National Screening claim to D001 (receiverID='{receiver}')", trace=trace))
                elif sender == "D001" and receiver != _HAAD_RECEIVER_ID:
                    trace = (
                        f"Condition 1 — Encounter.Type: 7 (National Screening) ✓",
                        f"Condition 2 — SenderID: '{sender}' = 'D001' ✓",
                        f"Condition 3 — ReceiverID: '{receiver}' ≠ 'HAAD' → D001 must send to HAAD → VIOLATION",
                    )
                    errors.append(self._err(37, f"Claim '{c.id}': Payer D001 must send National Screening claim to HAAD (receiverID='{receiver}')", trace=trace))
        return errors

    # ── Encounter date checks ──────────────────────────────────────────────────

    # Fires when: inpatient Encounter (Type=3 or 4) has no Encounter.End
    def _rule_38(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.type in (3, 4) and not enc.end:
                    errors.append(self._err(38, f"Claim '{c.id}': Encounter.End must have value for inpatient (Encounter.Type={enc.type})",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Encounter.Type: {enc.type} (inpatient) → requires Encounter.End",
                            f"Encounter.End: '{enc.end}' → empty → VIOLATION",
                        )))
        return errors

    # Fires when: Encounter.End exists and is before Encounter.Start
    def _rule_40(self, model: cs.ClaimSubmission, res) -> list:
        if model.header.record_count is None:
            return []
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.end is None:
                    continue
                s = _parse_datetime(enc.start)
                e = _parse_datetime(enc.end)
                if s and e and e < s:
                    errors.append(self._err(40, f"Claim '{c.id}': Encounter.End ({enc.end}) must be >= Encounter.Start ({enc.start})",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Encounter.Start: '{enc.start}'",
                            f"Encounter.End: '{enc.end}'",
                            f"End < Start → VIOLATION",
                        )))
        return errors

    # Fires when: inpatient Encounter (Type=3 or 4) has no Encounter.EndType
    def _rule_41(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.type in (3, 4) and enc.end_type is None:
                    errors.append(self._err(41, f"Claim '{c.id}': Encounter.EndType must have value for inpatient (Encounter.Type={enc.type})",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Encounter.Type: {enc.type} (inpatient) → requires Encounter.EndType",
                            f"Encounter.EndType: None → VIOLATION",
                        )))
        return errors

    # Fires when: Encounter.StartType=3 or 8 and TransferSource is missing or invalid
    def _rule_42(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        in_excl = res.in_exclusion_list_2(sender)
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.start_type not in (3, 8):
                    continue
                ts = enc.transfer_source
                if in_excl:
                    if not ts or not ts.strip() or (not ts.startswith("@") and not res.is_any_provider(ts)):
                        ts_ok = bool(ts and ts.strip() and (ts.startswith("@") or res.is_any_provider(ts)))
                        trace = (
                            f"Condition 1 — SenderID: '{sender}' → in exclusion list 2 → strict mode",
                            f"Condition 2 — Encounter.StartType: {enc.start_type} → requires TransferSource",
                            f"Condition 3 — TransferSource: '{ts}' → valid: {ts_ok} → VIOLATION",
                        )
                        errors.append(self._err(42, f"Claim '{c.id}': Encounter.TransferSource must be valid when StartType is {enc.start_type}", trace=trace))
                else:
                    if ts and not ts.startswith("@") and not res.is_any_provider(ts):
                        trace = (
                            f"Condition 1 — Encounter.StartType: {enc.start_type} → requires TransferSource check",
                            f"Condition 2 — TransferSource: '{ts}' → not '@'-prefixed → license check applies",
                            f"Condition 3 — HAAD provider lookup: '{ts}' → NOT FOUND → VIOLATION",
                        )
                        errors.append(self._err(42, f"Claim '{c.id}': Encounter.TransferSource '{ts}' must have a valid HAAD license when StartType is {enc.start_type}", trace=trace))
        return errors

    # Fires when: Encounter.EndType=4 or 7 and TransferDestination is missing or invalid
    def _rule_43(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        in_excl = res.in_exclusion_list_2(sender)
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.end_type not in (4, 7):
                    continue
                td = enc.transfer_destination
                if in_excl:
                    if not td or not td.strip() or (not td.startswith("@") and not res.is_any_provider(td)):
                        td_ok = bool(td and td.strip() and (td.startswith("@") or res.is_any_provider(td)))
                        trace = (
                            f"Condition 1 — SenderID: '{sender}' → in exclusion list 2 → strict mode",
                            f"Condition 2 — Encounter.EndType: {enc.end_type} → requires TransferDestination",
                            f"Condition 3 — TransferDestination: '{td}' → valid: {td_ok} → VIOLATION",
                        )
                        errors.append(self._err(43, f"Claim '{c.id}': Encounter.TransferDestination must be valid when EndType is {enc.end_type}", trace=trace))
                else:
                    if td and not td.startswith("@") and not res.is_any_provider(td):
                        trace = (
                            f"Condition 1 — Encounter.EndType: {enc.end_type} → requires TransferDestination check",
                            f"Condition 2 — TransferDestination: '{td}' → not '@'-prefixed → license check applies",
                            f"Condition 3 — HAAD provider lookup: '{td}' → NOT FOUND → VIOLATION",
                        )
                        errors.append(self._err(43, f"Claim '{c.id}': Encounter.TransferDestination '{td}' must have a valid HAAD license when EndType is {enc.end_type}", trace=trace))
        return errors

    # ── Observation checks ─────────────────────────────────────────────────────

    # Fires when: Observation.Type='LOINC' but code is not in LOINC master data
    def _rule_45(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for act in c.activities:
                for obs in act.observations:
                    if obs.type == "LOINC" and not res.is_loinc_code(obs.code):
                        trace = (
                            f"Condition 1 — Observation.Type: 'LOINC' ✓",
                            f"Condition 2 — LOINC code lookup: '{obs.code}' → NOT FOUND in LOINC master data → VIOLATION",
                            f"Note: LOINC codes are case-sensitive. Verify exact value.",
                        )
                        errors.append(self._err(45, f"Claim '{c.id}', Activity '{act.id or act.code}': Observation.Code '{obs.code}' does not match LOINC codes", trace=trace))
        return errors

    # Fires when: Observation.Value is empty for non-exempt observation types
    def _rule_46(self, model: cs.ClaimSubmission, res) -> list:
        _exempt = {"Universal Dental", "Episode", "Flags"}
        errors = []
        for c in model.claims:
            for act in c.activities:
                for obs in act.observations:
                    if obs.type not in _exempt and not obs.value:
                        errors.append(self._err(46, f"Claim '{c.id}', Activity '{act.id or act.code}': Observation.Value may not be empty for type '{obs.type}'",
                            trace=(
                                f"Activity: '{act.id or act.code}'",
                                f"Observation.Type: '{obs.type}' → not exempt → Observation.Value required",
                                f"Observation.Value: '{obs.value}' → empty → VIOLATION",
                            )))
        return errors

    # Fires when: Observation.ValueType is empty for non-exempt observation types
    def _rule_47(self, model: cs.ClaimSubmission, res) -> list:
        _exempt = {"Universal Dental", "Episode", "Flags"}
        errors = []
        for c in model.claims:
            for act in c.activities:
                for obs in act.observations:
                    if obs.type not in _exempt and not obs.value_type:
                        errors.append(self._err(47, f"Claim '{c.id}', Activity '{act.id or act.code}': Observation.ValueType may not be empty for type '{obs.type}'",
                            trace=(
                                f"Activity: '{act.id or act.code}'",
                                f"Observation.Type: '{obs.type}' → not exempt → Observation.ValueType required",
                                f"Observation.ValueType: '{obs.value_type}' → empty → VIOLATION",
                            )))
        return errors

    # ── Transaction date / header checks ──────────────────────────────────────

    # Fires when: Header.TransactionDate does not match today's date
    def _rule_61(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None:
            return []
        today = datetime.now().date()
        if tx.date() != today:
            return [self._err(61, f"TransactionDate {model.header.transaction_date} must match current date {today.strftime('%d/%m/%Y')}",
                trace=(
                    f"Header.TransactionDate: '{model.header.transaction_date}' → parsed as {tx.date()}",
                    f"Today's date: {today.strftime('%d/%m/%Y')}",
                    f"Dates do not match → VIOLATION",
                ))]
        return []

    # Fires when: any Activity.Type is outside allowed set {3,4,5,6,8,9}
    def _rule_62(self, model: cs.ClaimSubmission, res) -> list:
        _valid = frozenset({3, 4, 5, 6, 8, 9})
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.type not in _valid:
                    errors.append(self._err(62, f"Claim '{c.id}': Activity.Type {act.type} is not valid (must be 3/4/5/6/8/9)",
                        trace=(
                            f"Activity: '{act.id or act.code}'",
                            f"Activity.Type: {act.type}",
                            f"Allowed types: {{3, 4, 5, 6, 8, 9}}",
                            f"Type {act.type} not in allowed set → VIOLATION",
                        )))
        return errors

    # Fires when: Header.RecordCount exceeds 500
    def _rule_303(self, model: cs.ClaimSubmission, res) -> list:
        if model.header.record_count > 500:
            return [self._err(303, f"RecordCount {model.header.record_count} exceeds maximum of 500",
                trace=(
                    f"Header.RecordCount: {model.header.record_count}",
                    f"Maximum allowed: 500",
                    f"{model.header.record_count} > 500 → VIOLATION",
                ))]
        return []

    # ── Activity code validity (tariff date-aware) ────────────────────────────

    # Fires when: Activity.Type=3 (CPT) and code is not a valid CPT code on the activity date (not in exclusion list 1)
    def _rule_65(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        if res.in_exclusion_list_1(sender):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.type != 3:
                    continue
                s = _parse_datetime(act.start)
                s_str = s.strftime("%d/%m/%Y") if s else "unparseable"
                if s is None or not res.is_cpt_code_valid_on_date(act.code, s):
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list ✓",
                        f"Condition 2 — Activity.Type: 3 (CPT) ✓",
                        f"Condition 3 — CPT code lookup: '{act.code}' on {s_str} → NOT FOUND or inactive → VIOLATION",
                        f"Note: codes are case-sensitive. Verify exact casing and effective date in the tariff.",
                    )
                    errors.append(self._err(65, f"Claim '{c.id}', Activity '{act.id or act.code}': '{act.code}' is not a valid CPT code on {act.start}", trace=trace))
        return errors

    # Fires when: Activity.Type=4 (HCPCS) and code is not a valid HCPCS code on the activity date (not in exclusion list 1)
    def _rule_66(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        if res.in_exclusion_list_1(sender):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.type != 4:
                    continue
                s = _parse_datetime(act.start)
                s_str = s.strftime("%d/%m/%Y") if s else "unparseable"
                if s is None or not res.is_hcpcs_code_valid_on_date(act.code, s):
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list ✓",
                        f"Condition 2 — Activity.Type: 4 (HCPCS) ✓",
                        f"Condition 3 — HCPCS code lookup: '{act.code}' on {s_str} → NOT FOUND or inactive → VIOLATION",
                        f"Note: codes are case-sensitive. Verify exact casing and effective date in the tariff.",
                    )
                    errors.append(self._err(66, f"Claim '{c.id}', Activity '{act.id or act.code}': '{act.code}' is not a valid HCPCS code on {act.start}", trace=trace))
        return errors

    # Fires when: Activity.Type=5 (Trade Drug) and code is not a valid Trade Drug on the activity date (exempt: payer→HAAD)
    def _rule_67(self, model: cs.ClaimSubmission, res) -> list:
        sender, receiver = model.header.sender_id, model.header.receiver_id
        if res.in_exclusion_list_1(sender):
            return []
        if res.is_haad_payer(sender) and receiver == _HAAD_RECEIVER_ID:
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.type != 5:
                    continue
                s = _parse_datetime(act.start)
                s_str = s.strftime("%d/%m/%Y") if s else "unparseable"
                if s is None or not res.is_trade_drug_valid_on_date(act.code, s):
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list, not payer→HAAD ✓",
                        f"Condition 2 — Activity.Type: 5 (Trade Drug) ✓",
                        f"Condition 3 — Trade Drug lookup: '{act.code}' on {s_str} → NOT FOUND or inactive → VIOLATION",
                        f"Note: drug codes are case-sensitive. Verify exact code and effective date.",
                    )
                    errors.append(self._err(67, f"Claim '{c.id}', Activity '{act.id or act.code}': '{act.code}' is not a valid Trade Drug code on {act.start}", trace=trace))
        return errors

    # Fires when: Activity.Type=6 (Dental) and code is not a valid USCLS code on the activity date
    def _rule_68(self, model: cs.ClaimSubmission, res) -> list:
        sender, receiver = model.header.sender_id, model.header.receiver_id
        if res.in_exclusion_list_1(sender):
            return []
        if res.is_haad_payer(sender) and receiver == _HAAD_RECEIVER_ID:
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.type != 6:
                    continue
                s = _parse_datetime(act.start)
                s_str = s.strftime("%d/%m/%Y") if s else "unparseable"
                if s is None or not res.is_dental_code_valid_on_date(act.code, s):
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list, not payer→HAAD ✓",
                        f"Condition 2 — Activity.Type: 6 (Dental/USCLS) ✓",
                        f"Condition 3 — Dental code lookup: '{act.code}' on {s_str} → NOT FOUND or inactive → VIOLATION",
                        f"Note: codes are case-sensitive. Verify exact casing and effective date in the tariff.",
                    )
                    errors.append(self._err(68, f"Claim '{c.id}', Activity '{act.id or act.code}': '{act.code}' is not a valid Dental (USCLS) code on {act.start}", trace=trace))
        return errors

    # Fires when: Activity.Type=8 (Service) and code is not a valid Service code on the activity date
    def _rule_69(self, model: cs.ClaimSubmission, res) -> list:
        sender, receiver = model.header.sender_id, model.header.receiver_id
        if res.in_exclusion_list_1(sender):
            return []
        if res.is_haad_payer(sender) and receiver == _HAAD_RECEIVER_ID:
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.type != 8:
                    continue
                s = _parse_datetime(act.start)
                s_str = s.strftime("%d/%m/%Y") if s else "unparseable"
                if s is None or not res.is_service_code_valid_on_date(act.code, s):
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list, not payer→HAAD ✓",
                        f"Condition 2 — Activity.Type: 8 (Service) ✓",
                        f"Condition 3 — Service code lookup: '{act.code}' on {s_str} → NOT FOUND or inactive → VIOLATION",
                        f"Note: codes are case-sensitive. Verify exact casing and effective date in the tariff.",
                    )
                    errors.append(self._err(69, f"Claim '{c.id}', Activity '{act.id or act.code}': '{act.code}' is not a valid Service code on {act.start}", trace=trace))
        return errors

    # Fires when: Activity.Type=9 (DRG) and code is not a valid DRG code on the activity date
    def _rule_70(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        if res.in_exclusion_list_1(sender):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.type != 9:
                    continue
                s = _parse_datetime(act.start)
                s_str = s.strftime("%d/%m/%Y") if s else "unparseable"
                if s is None or not res.is_drg_code_valid_on_date(act.code, s):
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list ✓",
                        f"Condition 2 — Activity.Type: 9 (DRG) ✓",
                        f"Condition 3 — DRG code lookup: '{act.code}' on {s_str} → NOT FOUND or inactive → VIOLATION",
                        f"Note: codes are case-sensitive. Verify exact casing and effective date in the tariff.",
                    )
                    errors.append(self._err(70, f"Claim '{c.id}', Activity '{act.id or act.code}': '{act.code}' is not a valid DRG code on {act.start}", trace=trace))
        return errors

    # ── Clinician checks ───────────────────────────────────────────────────────

    # Fires when: Activity before 01/06/2014 has no Clinician value
    def _rule_71(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None or s >= datetime(2014, 6, 1):
                    continue
                if not act.clinician or not act.clinician.strip():
                    errors.append(self._err(71, f"Claim '{c.id}', Activity '{act.id or act.code}': Clinician must have value for activities before 01/06/2014",
                        trace=(
                            f"Activity: '{act.id or act.code}', Start: '{act.start}'",
                            f"Activity.Start < 01/06/2014 → Clinician required",
                            f"Activity.Clinician: '{act.clinician}' → empty → VIOLATION",
                        )))
        return errors

    # Fires when: both ProviderID and Clinician are present but one uses '@' and the other has a license (from 2009-05-01)
    def _rule_73(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2009, 5, 1):
            return []
        sender = model.header.sender_id
        if res.in_exclusion_list_1(sender):
            return []
        errors = []
        for c in model.claims:
            pid = c.provider_id or ""
            for act in c.activities:
                cln = act.clinician or ""
                if not pid or not cln:
                    continue
                pid_at = pid.startswith("@")
                cln_at = cln.startswith("@")
                pid_valid = pid_at or res.is_any_provider(pid)
                cln_valid = cln_at or res.is_active_clinician(cln)
                if (pid_at and not cln_at) or (pid_valid and not cln_valid):
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list ✓",
                        f"Condition 2 — ProviderID: '{pid}' → '@'-prefix: {pid_at}, valid: {pid_valid}",
                        f"Condition 3 — Clinician: '{cln}' → '@'-prefix: {cln_at}, active clinician: {cln_valid}",
                        f"Condition 4 — '@' / license mismatch between ProviderID and Clinician → VIOLATION",
                    )
                    errors.append(self._err(73, f"Claim '{c.id}', Activity '{act.id or act.code}': Clinician and ProviderID must both have valid licenses or use '@'", trace=trace))
        return errors

    # Fires when: FacilityID and Clinician are present but one uses '@' while the other has a license (from 2009-05-01)
    def _rule_74(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2009, 5, 1):
            return []
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                fid = enc.facility_id or ""
                for act in c.activities:
                    cln = act.clinician or ""
                    s = _parse_datetime(act.start)
                    if s is None or s < datetime(2009, 5, 1):
                        continue
                    if not fid or not cln:
                        continue
                    fid_at = fid.startswith("@")
                    cln_at = cln.startswith("@")
                    fid_valid = fid_at or res.is_any_provider(fid)
                    cln_valid = cln_at or res.is_active_clinician(cln)
                    if (fid_at and not cln_at) or (fid_valid and not cln_valid):
                        trace = (
                            f"Condition 1 — FacilityID: '{fid}' → '@'-prefix: {fid_at}, valid provider: {fid_valid}",
                            f"Condition 2 — Clinician: '{cln}' → '@'-prefix: {cln_at}, active clinician: {cln_valid}",
                            f"Condition 3 — '@' / license mismatch between FacilityID and Clinician → VIOLATION",
                        )
                        errors.append(self._err(74, f"Claim '{c.id}', Activity '{act.id or act.code}': Clinician and FacilityID must both have valid licenses or use '@'", trace=trace))
                        break  # one error per encounter per activity is enough
        return errors

    # Fires when: Activity.Quantity <= 0 (not applicable to National Screening encounters)
    def _rule_75(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            enc_types = {e.type for e in c.encounters}
            if 7 in enc_types:
                continue  # National Screening — quantity rules don't apply
            for act in c.activities:
                if act.quantity <= 0:
                    errors.append(self._err(75, f"Claim '{c.id}', Activity '{act.id or act.code}': Quantity must be > 0 (got {act.quantity})",
                        trace=(
                            f"Activity: '{act.id or act.code}'",
                            f"Activity.Quantity: {act.quantity}",
                            f"Quantity ≤ 0 → VIOLATION",
                        )))
        return errors

    # Fires when: Activity.Start is outside the [Encounter.Start, Encounter.End] window
    def _rule_81(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if not c.encounters:
                continue
            enc_starts = [_parse_datetime(e.start) for e in c.encounters]
            enc_starts = [s for s in enc_starts if s is not None]
            enc_ends = [_parse_datetime(e.end) for e in c.encounters if e.end]
            enc_ends = [e for e in enc_ends if e is not None]
            if not enc_starts:
                continue
            lowest_start = min(enc_starts)
            highest_end = max(enc_ends) if len(enc_ends) == len(c.encounters) else None
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None:
                    continue
                if highest_end is not None:
                    if s < lowest_start or s > highest_end:
                        errors.append(self._err(81, f"Claim '{c.id}', Activity '{act.id or act.code}': Start {act.start} must be between Encounter Start {lowest_start.strftime('%d/%m/%Y %H:%M')} and End {highest_end.strftime('%d/%m/%Y %H:%M')}",
                            trace=(
                                f"Activity: '{act.id or act.code}', Start: '{act.start}'",
                                f"Encounter window: [{lowest_start.strftime('%d/%m/%Y %H:%M')}, {highest_end.strftime('%d/%m/%Y %H:%M')}]",
                                f"Activity.Start outside window → VIOLATION",
                            )))
                elif s < lowest_start:
                    errors.append(self._err(81, f"Claim '{c.id}', Activity '{act.id or act.code}': Start {act.start} must be >= Encounter Start {lowest_start.strftime('%d/%m/%Y %H:%M')}",
                        trace=(
                            f"Activity: '{act.id or act.code}', Start: '{act.start}'",
                            f"Earliest Encounter.Start: {lowest_start.strftime('%d/%m/%Y %H:%M')}",
                            f"Activity.Start < Encounter.Start → VIOLATION",
                        )))
        return errors

    # ── IDPayer rules ──────────────────────────────────────────────────────────

    # Fires when: sender is a payer/TPA (from 2010-10-01) and any qualifying Claim.IDPayer is empty
    def _rule_87(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        sender = model.header.sender_id
        is_payer = res.is_haad_payer(sender)
        is_tpa = res.is_haad_tpa(sender)
        if not is_payer and not is_tpa:
            return []
        errors = []
        for c in model.claims:
            acts = [a for a in c.activities if _parse_datetime(a.start) is not None and _parse_datetime(a.start) >= datetime(2010, 5, 13)]
            if acts and (not c.id_payer or not c.id_payer.strip()):
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → is HAAD payer: {is_payer}, is TPA: {is_tpa} → payer/TPA role ✓",
                    f"Condition 2 — Has qualifying activities (start ≥ 13/05/2010): {len(acts)} ✓",
                    f"Condition 3 — Claim.IDPayer: '{c.id_payer}' → empty → VIOLATION",
                )
                errors.append(self._err(87, f"Claim '{c.id}': IDPayer may not be empty for transactions sent by payer", trace=trace))
        return errors

    # Fires when: sender is a provider and Claim.IDPayer is non-empty (unless Resubmission.Type is correction or internal complaint)
    def _rule_95(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        sender = model.header.sender_id
        if not res.is_any_provider(sender):
            return []
        errors = []
        for c in model.claims:
            resub = c.resubmission
            if resub and resub.type in ("correction", "internal complaint"):
                continue
            if c.id_payer and c.id_payer.strip():
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → is a provider ✓",
                    f"Condition 2 — No correction/internal-complaint resubmission ✓",
                    f"Condition 3 — Claim.IDPayer: '{c.id_payer}' → not empty → providers must not set IDPayer → VIOLATION",
                )
                errors.append(self._err(95, f"Claim '{c.id}': IDPayer must be empty when SenderID is a provider (unless Resubmission.Type is correction or internal complaint)", trace=trace))
        return errors

    # ── Dental / tooth observation checks ─────────────────────────────────────

    # Fires when: dental activity (Type=6) with a tooth-requiring code has no Universal Dental observation (for senders in exclusion list 2, from 2010-03-01)
    def _rule_88(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        sender = model.header.sender_id
        if not res.in_exclusion_list_2(sender):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.type != 6:
                    continue
                s = _parse_datetime(act.start)
                if s is None or s < datetime(2010, 3, 1):
                    continue
                dental_valid = res.is_valid_dental_code(act.code)
                if not dental_valid:
                    continue
                tooth_req = res.is_dental_tariff_tooth_required(act.code)
                if not tooth_req:
                    continue
                has_ud = any(o.type == "Universal Dental" for o in act.observations)
                if not has_ud:
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → in exclusion list 2 ✓",
                        f"Condition 2 — Activity.Type: 6 (Dental), start ≥ 01/03/2010 ✓",
                        f"Condition 3 — Dental code: '{act.code}' → valid: {dental_valid}, tooth required: {tooth_req} ✓",
                        f"Condition 4 — Universal Dental observation present: {has_ud} → missing → VIOLATION",
                    )
                    errors.append(self._err(88, f"Claim '{c.id}', Activity '{act.id or act.code}': must have a Universal Dental observation for tooth-requiring code '{act.code}'", trace=trace))
        return errors

    # Fires when: Universal Dental observation code is not a valid tooth number (from 2010-10-01)
    def _rule_90(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                for obs in act.observations:
                    if obs.type == "Universal Dental" and not res.is_valid_tooth_code(obs.code):
                        trace = (
                            f"Condition 1 — Observation.Type: 'Universal Dental' ✓",
                            f"Condition 2 — Tooth code lookup: '{obs.code}' → NOT a valid Universal Tooth Numbering code → VIOLATION",
                        )
                        errors.append(self._err(90, f"Claim '{c.id}', Activity '{act.id or act.code}': Observation code '{obs.code}' is not a valid Universal Tooth Numbering code", trace=trace))
        return errors

    # Fires when: non-dental activity (Type≠6) has a Universal Dental observation (from 2010-10-01)
    def _rule_91(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.type == 6:
                    continue
                for obs in act.observations:
                    if obs.type == "Universal Dental":
                        errors.append(self._err(91, f"Claim '{c.id}', Activity '{act.id or act.code}': only dental activities (type 6) may have Universal Dental observations (type={act.type})",
                            trace=(
                                f"Activity: '{act.id or act.code}'",
                                f"Activity.Type: {act.type} (not dental/type 6)",
                                f"Observation.Type: 'Universal Dental' → only allowed for type 6 → VIOLATION",
                            )))
                        break
        return errors

    # ── Duplicate / uniqueness checks ─────────────────────────────────────────

    # Fires when: same (Claim.ID, ProviderID) pair appears more than once in the transaction (for activities from 2017-09-23)
    def _rule_93(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 11, 14):
            return []
        seen = set()
        errors = []
        for c in model.claims:
            if not c.provider_id:
                continue
            act_starts = [_parse_datetime(a.start) for a in c.activities if a.start]
            act_starts = [s for s in act_starts if s is not None]
            if not act_starts or min(act_starts) < datetime(2017, 9, 23):
                continue
            key = (c.id, c.provider_id)
            if key in seen:
                errors.append(self._err(93, f"Claim '{c.id}' + ProviderID '{c.provider_id}' is submitted more than once in this transaction",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Claim.ProviderID: '{c.provider_id}'",
                        f"This (Claim.ID, ProviderID) combination has appeared before in this transaction → VIOLATION",
                    )))
            else:
                seen.add(key)
        return errors

    # Fires when: Activity.ID is duplicated within a claim (for activities from 2010-06-07)
    def _rule_110(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 6, 7):
            return []
        errors = []
        for c in model.claims:
            seen = set()
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None or s < datetime(2010, 6, 7):
                    continue
                if act.id is None:
                    continue
                if act.id in seen:
                    errors.append(self._err(110, f"Claim '{c.id}': Activity.ID '{act.id}' is duplicated within the claim",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Activity.ID: '{act.id}'",
                            f"This Activity.ID has appeared before in the same claim → VIOLATION",
                        )))
                else:
                    seen.add(act.id)
        return errors

    # ── Resubmission / historical claim checks ────────────────────────────────

    # Fires when: correction/internal-complaint resubmission has no matching Remittance Advice in the DB
    def _rule_112(self, model: cs.ClaimSubmission, res) -> list:
        receiver = model.header.receiver_id
        if receiver in ("HAAD", "D003"):
            return []
        errors = []
        for c in model.claims:
            resub = c.resubmission
            if resub is None or resub.type not in ("correction", "internal complaint"):
                continue
            if not res.has_remittance_for_claim(receiver, c.id, c.id_payer or ""):
                errors.append(self._err(112, f"Claim '{c.id}': no matching Remittance Advice found for correction/internal complaint resubmission",
                    trace=(
                        f"Claim.ID: '{c.id}', Resubmission.Type: '{resub.type}'",
                        f"Looked up Remittance.Advice for ReceiverID: '{receiver}', Claim.ID: '{c.id}', IDPayer: '{c.id_payer or ''}'",
                        f"Result: NOT FOUND → VIOLATION",
                    )))
        return errors

    # Fires when: the same Claim.ID was already submitted by this sender
    def _rule_118(self, model: cs.ClaimSubmission, res) -> list:
        receiver = model.header.receiver_id
        if receiver in ("HAAD", "D003"):
            return []
        sender = model.header.sender_id
        errors = []
        for c in model.claims:
            if res.has_submitted_claim(sender, c.id):
                errors.append(self._err(118, f"Claim '{c.id}': already submitted by sender '{sender}'",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Sender: '{sender}'",
                        f"DB lookup: Claim.ID '{c.id}' already exists for sender '{sender}' → VIOLATION",
                    )))
        return errors

    # Fires when: MemberID is not registered for the stated payer (for activities from 2030-01-05, not IPC provider)
    def _rule_119(self, model: cs.ClaimSubmission, res) -> list:
        fes = {c.id: _first_enc_start(c) for c in model.claims}
        receiver = model.header.receiver_id
        sender = model.header.sender_id
        if receiver == _HAAD_RECEIVER_ID or res.is_ipc_provider(sender):
            return []
        errors = []
        for c in model.claims:
            fe = fes.get(c.id)
            if fe is None or fe < datetime(2030, 1, 5):
                continue
            pid = c.payer_id
            if pid.startswith("@"):
                continue
            if pid.endswith("_Shadow"):
                pid = pid[:-7]
            member_id = c.member_id or ""
            if not member_id:
                continue
            if not res.is_member_registered_for_payer(member_id, pid):
                trace = (
                    f"Condition 1 — ReceiverID: '{receiver}' ≠ HAAD, SenderID not IPC provider ✓",
                    f"Condition 2 — Encounter.Start ≥ 05/01/2030, PayerID not '@'-prefixed ✓",
                    f"Condition 3 — MemberID: '{member_id}' → not registered for payer '{pid}' → VIOLATION",
                )
                errors.append(self._err(119, f"Claim '{c.id}': MemberID '{member_id}' does not belong to payer '{pid}'", trace=trace))
        return errors

    # ── Date ordering / timeline checks ───────────────────────────────────────

    # Fires when: Encounter.Start is after TransactionDate (from 2011-06-15)
    def _rule_120(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        tx_str = tx.strftime("%d/%m/%Y") if tx else "unparseable"
        if tx is None:
            return []
        if tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                s = _parse_datetime(enc.start)
                if s is not None and s > tx:
                    s_str = s.strftime("%d/%m/%Y")
                    trace = (
                        f"TransactionDate: {tx_str}",
                        f"Rule applies (effective from 15/06/2011)",
                        f"Claim '{c.id}' → Encounter.Start '{enc.start}' parsed as {s_str}",
                        f"{s_str} > {tx_str} → date is after TransactionDate → VIOLATION",
                    )
                    errors.append(self._err(120,
                        f"Claim '{c.id}': Encounter.Start {enc.start} must be before TransactionDate {model.header.transaction_date}",
                        trace=trace))
        return errors

    # Fires when: service codes 15–20 are used in outpatient encounter types for activities from 2016-06-01 (except specific exceptions)
    def _rule_127(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        if model.header.sender_id == "MF2457":
            return []
        _exceptions = frozenset({"17-24","17-21","17-22","17-27-3","17-26-1","17-23","20-01"})
        _enc_types = frozenset({1, 2, 7, 8, 9})
        errors = []
        for c in model.claims:
            enc_types = {e.type for e in c.encounters}
            if not enc_types.intersection(_enc_types):
                continue
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None or s < datetime(2016, 6, 1):
                    continue
                if act.code in _exceptions:
                    continue
                try:
                    first_seg = int(act.code.split("-")[0])
                except (ValueError, IndexError):
                    continue
                if 15 <= first_seg <= 20:
                    errors.append(self._err(127, f"Claim '{c.id}', Activity '{act.id or act.code}': service codes 15–20 are not allowed for outpatient encounters",
                        trace=(
                            f"Activity: '{act.id or act.code}', Code: '{act.code}', Start: '{act.start}'",
                            f"Encounter types in claim: {sorted({e.type for e in c.encounters})}",
                            f"Code prefix '{first_seg}' is in range 15–20 in outpatient encounter → VIOLATION",
                        )))
        return errors

    # Fires when: some Activities have Activity.ID and others do not within the same claim
    def _rule_130(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            ids_present = [a.id for a in c.activities if a.id is not None]
            ids_absent = [a for a in c.activities if a.id is None]
            if ids_present and ids_absent:
                errors.append(self._err(130, f"Claim '{c.id}': Activity.ID must be present in all or none of the activities",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Activities with ID: {len(ids_present)} (IDs: {ids_present[:5]}{'…' if len(ids_present) > 5 else ''})",
                        f"Activities without ID: {len(ids_absent)}",
                        f"Mixed presence of Activity.ID → VIOLATION",
                    )))
        return errors

    # Fires when: DRG activity (Type=9) is used for an encounter on or before 31/07/2010
    def _rule_142(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                s = _parse_datetime(enc.start)
                if s is None:
                    continue
                for act in c.activities:
                    if act.type == 9 and s <= datetime(2010, 7, 31):
                        errors.append(self._err(142, f"Claim '{c.id}': DRG activity (type 9) may only be used for encounters after 31/07/2010 (Encounter.Start={enc.start})",
                            trace=(
                                f"Claim.ID: '{c.id}'",
                                f"Encounter.Start: '{enc.start}'",
                                f"Activity.Type: 9 (DRG)",
                                f"DRG only allowed for encounters after 31/07/2010 → VIOLATION",
                            )))
                        break
        return errors

    # Fires when: Encounter.End is after TransactionDate (from 2011-06-15)
    def _rule_143(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.end is None:
                    continue
                e = _parse_datetime(enc.end)
                if e is not None and e > tx:
                    errors.append(self._err(143, f"Claim '{c.id}': Encounter.End {enc.end} must be <= TransactionDate {model.header.transaction_date}",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Encounter.End: '{enc.end}'",
                            f"TransactionDate: '{model.header.transaction_date}'",
                            f"End > TransactionDate → VIOLATION",
                        )))
        return errors

    # Fires when: Encounter.Start (with no End) is more than one year before TransactionDate for non-resubmitted claims
    def _rule_144(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            if c.resubmission is not None:
                continue
            for enc in c.encounters:
                if enc.end is not None:
                    continue
                s = _parse_datetime(enc.start)
                if s is not None and s < tx - timedelta(days=365):
                    errors.append(self._err(144, f"Claim '{c.id}': Encounter.Start {enc.start} must be within one year before TransactionDate {model.header.transaction_date}",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Encounter.Start: '{enc.start}'",
                            f"TransactionDate: '{model.header.transaction_date}'",
                            f"Encounter.Start is more than 365 days before TransactionDate → VIOLATION",
                        )))
        return errors

    # Fires when: duplicate Diagnosis codes exist in a Claim
    def _rule_145(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            codes = [d.code for d in c.diagnoses]
            seen: set = set()
            dupes: set = set()
            for code in codes:
                if code in seen:
                    dupes.add(code)
                seen.add(code)
            if dupes:
                errors.append(self._err(145, f"Claim '{c.id}': duplicate Diagnosis codes found",
                    trace=(
                        f"All diagnosis codes: {', '.join(codes)}",
                        f"Duplicated codes: {', '.join(sorted(dupes))}",
                    )))
        return errors

    # Fires when: Activity.Quantity >= 2001 or has more than 4 decimal places (for activities from 2014-06-01)
    def _rule_146(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None or s < datetime(2014, 6, 1):
                    continue
                if model.header.sender_id == "D099":
                    continue
                if act.quantity >= 2001:
                    errors.append(self._err(146, f"Claim '{c.id}', Activity '{act.id or act.code}': Quantity {act.quantity} must be < 2001",
                        trace=(
                            f"Activity: '{act.id or act.code}', Start: '{act.start}'",
                            f"Activity.Quantity: {act.quantity}",
                            f"Quantity ≥ 2001 → VIOLATION",
                        )))
                elif "." in str(act.quantity):
                    dec_part = str(act.quantity).split(".")[1]
                    if len(dec_part) > 4:
                        errors.append(self._err(146, f"Claim '{c.id}', Activity '{act.id or act.code}': Quantity {act.quantity} has more than 4 decimal places",
                            trace=(
                                f"Activity: '{act.id or act.code}', Start: '{act.start}'",
                                f"Activity.Quantity: {act.quantity}",
                                f"Decimal part: '{dec_part}' ({len(dec_part)} digits) > 4 decimal places → VIOLATION",
                            )))
        return errors

    # Fires when: Activity.Net < 0 for activities from 2014-10-02
    def _rule_147(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None or s < datetime(2014, 10, 2):
                    continue
                if act.net < 0:
                    errors.append(self._err(147, f"Claim '{c.id}', Activity '{act.id or act.code}': Net {act.net} must be >= 0",
                        trace=(
                            f"Activity: '{act.id or act.code}', Start: '{act.start}'",
                            f"Activity.Net: {act.net}",
                            f"Net < 0 → VIOLATION",
                        )))
        return errors

    # Fires when: Claim.Net < 0 (from 2011-06-15)
    def _rule_149(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            if _round_half_down(c.net, 4) < 0:
                errors.append(self._err(149, f"Claim '{c.id}': Net {c.net} must be >= 0",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Claim.Net: {c.net}",
                        f"Net < 0 → VIOLATION",
                    )))
        return errors

    # Fires when: Claim.PatientShare < 0 (from 2011-06-15)
    def _rule_150(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        return [self._err(150, f"Claim '{c.id}': PatientShare {c.patient_share} must be >= 0",
                trace=(f"Claim.ID: '{c.id}'", f"Claim.PatientShare: {c.patient_share}", f"PatientShare < 0 → VIOLATION"))
                for c in model.claims if c.patient_share < 0]

    # Fires when: Claim.MemberID is empty (from 2010-11-28)
    def _rule_152(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 11, 28):
            return []
        return [self._err(152, f"Claim '{c.id}': MemberID must have value",
                trace=(f"Claim.ID: '{c.id}'", f"Claim.MemberID: '{c.member_id}' → empty → VIOLATION"))
                for c in model.claims if not c.member_id or not c.member_id.strip()]

    # Fires when: Activity.Start is after TransactionDate (from 2011-06-15)
    def _rule_187(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is not None and s > tx:
                    errors.append(self._err(187, f"Claim '{c.id}', Activity '{act.id or act.code}': Start {act.start} may not be after TransactionDate {model.header.transaction_date}",
                        trace=(
                            f"Activity: '{act.id or act.code}'",
                            f"Activity.Start: '{act.start}'",
                            f"TransactionDate: '{model.header.transaction_date}'",
                            f"Activity.Start > TransactionDate → VIOLATION",
                        )))
        return errors

    # Fires when: Encounter.StartType=7 (Continuing) used by a facility other than MF3048 before 2011-09-26
    def _rule_193(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                s = _parse_datetime(enc.start)
                if s is None or s > datetime(2011, 9, 26):
                    continue
                if enc.start_type == 7 and enc.facility_id != "MF3048":
                    errors.append(self._err(193, f"Claim '{c.id}': Encounter.StartType=7 (Continuing) only allowed for facility MF3048 (got '{enc.facility_id}')",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Encounter.StartType: 7 (Continuing)",
                            f"Encounter.FacilityID: '{enc.facility_id}' ≠ 'MF3048' → VIOLATION",
                        )))
        return errors

    # Fires when: Encounter.EndType=6 (Not discharged) used by a facility other than MF3048 before 2011-09-26
    def _rule_194(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                s = _parse_datetime(enc.start)
                if s is None or s > datetime(2011, 9, 26):
                    continue
                if enc.end_type == 6 and enc.facility_id != "MF3048":
                    errors.append(self._err(194, f"Claim '{c.id}': Encounter.EndType=6 (Not discharged) only allowed for facility MF3048 (got '{enc.facility_id}')",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Encounter.EndType: 6 (Not discharged)",
                            f"Encounter.FacilityID: '{enc.facility_id}' ≠ 'MF3048' → VIOLATION",
                        )))
        return errors

    # Fires when: any Activity.ID is missing or blank
    def _rule_200(self, model: cs.ClaimSubmission, res) -> list:
        if not model.header.sender_id:
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                if not act.id or not act.id.strip():
                    errors.append(self._err(200, f"Claim '{c.id}': Activity.ID is mandatory and must have a value",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Activity.Code: '{act.code}', Activity.Type: {act.type}",
                            f"Activity.ID: '{act.id}' → empty → VIOLATION",
                        )))
        return errors

    # Fires when: resubmission Activity IDs don't match the original claim's Activity IDs (for encounters from 2020-01-12)
    def _rule_201(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            resub = c.resubmission
            if resub is None:
                continue
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2020, 1, 12):
                continue
            prev = res.get_previous_claim_fields(model.header.sender_id, c.id)
            if prev is None:
                continue
            prev_act_ids = set(prev.get("activity_ids", []) or [])
            cur_act_ids = {a.id for a in c.activities if a.id}
            if resub.type == "internal complaint":
                if cur_act_ids != prev_act_ids:
                    errors.append(self._err(201, f"Claim '{c.id}': internal complaint resubmission must have same Activity IDs as original",
                        trace=(
                            f"Claim.ID: '{c.id}', Resubmission.Type: 'internal complaint'",
                            f"Original Activity IDs: {sorted(prev_act_ids)}",
                            f"Current Activity IDs: {sorted(cur_act_ids)}",
                            f"IDs do not match → VIOLATION",
                        )))
            else:
                common = cur_act_ids & prev_act_ids
                if common:
                    errors.append(self._err(201, f"Claim '{c.id}': resubmission type '{resub.type}' must not reuse Activity IDs from original (reused: {sorted(common)})",
                        trace=(
                            f"Claim.ID: '{c.id}', Resubmission.Type: '{resub.type}'",
                            f"Original Activity IDs: {sorted(prev_act_ids)}",
                            f"Current Activity IDs: {sorted(cur_act_ids)}",
                            f"Reused IDs: {sorted(common)} → VIOLATION",
                        )))
        return errors

    # ── Ordering clinician ─────────────────────────────────────────────────────

    # Fires when: OrderingClinician is missing for activities from 2014-06-01, or present for activities before that date
    def _rule_203(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None:
                    continue
                if s >= datetime(2014, 6, 1):
                    if not act.ordering_clinician or not act.ordering_clinician.strip():
                        errors.append(self._err(203, f"Claim '{c.id}', Activity '{act.id or act.code}': OrderingClinician is required for activities from 01/06/2014",
                            trace=(
                                f"Activity: '{act.id or act.code}', Start: '{act.start}'",
                                f"Activity.Start ≥ 01/06/2014 → OrderingClinician required",
                                f"Activity.OrderingClinician: '{act.ordering_clinician}' → empty → VIOLATION",
                            )))
                else:
                    if act.ordering_clinician and act.ordering_clinician.strip():
                        errors.append(self._err(203, f"Claim '{c.id}', Activity '{act.id or act.code}': OrderingClinician may not have value before 01/06/2014",
                            trace=(
                                f"Activity: '{act.id or act.code}', Start: '{act.start}'",
                                f"Activity.Start < 01/06/2014 → OrderingClinician must be empty",
                                f"Activity.OrderingClinician: '{act.ordering_clinician}' → has value → VIOLATION",
                            )))
        return errors

    # Fires when: OrderingClinician and ProviderID have mismatched '@' prefix or license validity (from 2014-06-01)
    def _rule_205(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        if res.in_exclusion_list_1(sender):
            return []
        errors = []
        for c in model.claims:
            pid = c.provider_id or ""
            fe = _first_enc_start(c)
            for act in c.activities:
                s = _parse_datetime(act.start)
                oc = act.ordering_clinician or ""
                if not oc or not pid:
                    continue
                if s is None or (s < datetime(2014, 6, 1) and (fe is None or fe < datetime(2014, 6, 1))):
                    continue
                pid_at = pid.startswith("@")
                oc_at = oc.startswith("@")
                pid_valid = pid_at or res.is_any_provider(pid)
                oc_valid = oc_at or res.is_active_clinician(oc)
                if (pid_at and not oc_at) or (not pid_at and oc_at) or (pid_valid and not oc_valid):
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list ✓",
                        f"Condition 2 — ProviderID: '{pid}' → '@'-prefix: {pid_at}, valid: {pid_valid}",
                        f"Condition 3 — OrderingClinician: '{oc}' → '@'-prefix: {oc_at}, active clinician: {oc_valid}",
                        f"Condition 4 — '@' / license mismatch between ProviderID and OrderingClinician → VIOLATION",
                    )
                    errors.append(self._err(205, f"Claim '{c.id}', Activity '{act.id or act.code}': OrderingClinician and ProviderID must both have valid licenses or use '@'", trace=trace))
        return errors

    # Fires when: OrderingClinician and FacilityID have mismatched '@' prefix or license validity (from 2014-06-01)
    def _rule_206(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            for enc in c.encounters:
                fid = enc.facility_id or ""
                for act in c.activities:
                    s = _parse_datetime(act.start)
                    oc = act.ordering_clinician or ""
                    if not oc or not fid:
                        continue
                    if s is None or (s < datetime(2014, 6, 1) and (fe is None or fe < datetime(2014, 6, 1))):
                        continue
                    fid_at = fid.startswith("@")
                    oc_at = oc.startswith("@")
                    fid_valid = fid_at or res.is_any_provider(fid)
                    oc_valid = oc_at or res.is_active_clinician(oc)
                    if (fid_at and not oc_at) or (not fid_at and oc_at) or (fid_valid and not oc_valid):
                        trace = (
                            f"Condition 1 — FacilityID: '{fid}' → '@'-prefix: {fid_at}, valid: {fid_valid}",
                            f"Condition 2 — OrderingClinician: '{oc}' → '@'-prefix: {oc_at}, active clinician: {oc_valid}",
                            f"Condition 3 — '@' / license mismatch between FacilityID and OrderingClinician → VIOLATION",
                        )
                        errors.append(self._err(206, f"Claim '{c.id}', Activity '{act.id or act.code}': OrderingClinician and FacilityID must both have valid licenses or use '@'", trace=trace))
                    break  # one error per encounter is enough
        return errors

    # Fires when: OrderingClinician is a pharmacist (from 2014-09-01)
    def _rule_207(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 9, 1):
            return []
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2014, 9, 1):
                continue
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None or s < datetime(2014, 9, 1):
                    continue
                oc = act.ordering_clinician or ""
                if not oc:
                    continue
                is_clinician = res.is_active_clinician(oc)
                is_pharm = res.is_clinician_pharmacist(oc)
                if is_clinician and is_pharm:
                    trace = (
                        f"Condition 1 — OrderingClinician: '{oc}' → is active clinician: {is_clinician} ✓",
                        f"Condition 2 — is pharmacist: {is_pharm} → pharmacists not allowed as OrderingClinician → VIOLATION",
                    )
                    errors.append(self._err(207, f"Claim '{c.id}', Activity '{act.id or act.code}': OrderingClinician '{oc}' must not be a pharmacist", trace=trace))
        return errors

    # Fires when: Clinician is a pharmacist and activity date is 2010-10-01 to 2013-12-03
    def _rule_98(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or not (datetime(2010, 10, 1) <= tx < datetime(2013, 12, 3)):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None or not (datetime(2010, 10, 1) <= s < datetime(2013, 12, 3)):
                    continue
                cln = act.clinician or ""
                if not cln:
                    continue
                is_clinician = res.is_active_clinician(cln)
                is_pharm = res.is_clinician_pharmacist(cln)
                if is_clinician and is_pharm:
                    trace = (
                        f"Condition 1 — Activity.Start: '{act.start}' → in 01/10/2010–03/12/2013 window ✓",
                        f"Condition 2 — Clinician: '{cln}' → is active clinician: {is_clinician} ✓",
                        f"Condition 3 — is pharmacist: {is_pharm} → pharmacists not allowed during this period → VIOLATION",
                    )
                    errors.append(self._err(98, f"Claim '{c.id}', Activity '{act.id or act.code}': Clinician '{cln}' must not be a pharmacist", trace=trace))
        return errors

    # ── Clinician license tracking (Rules 282, 283) ───────────────────────────

    # Fires when: Clinician does not have a valid DoH HPL license on the activity date (for activities from 2016-01-01, tx from 2018-06-01)
    def _rule_282(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2018, 6, 1):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None or s < datetime(2016, 1, 1):
                    continue
                cln = act.clinician or ""
                if not cln:
                    continue
                if res.is_clinician_invalid_hpl_on_date(cln, s):
                    s_str = s.strftime("%d/%m/%Y")
                    trace = (
                        f"Condition 1 — Activity.Start: '{act.start}' → ≥ 01/01/2016 ✓",
                        f"Condition 2 — Clinician: '{cln}' → DoH HPL license invalid or expired on {s_str} → VIOLATION",
                        f"Note: clinician IDs are case-sensitive. Verify exact value and license dates in registry.",
                    )
                    errors.append(self._err(282, f"Claim '{c.id}', Activity '{act.id or act.code}': Clinician '{cln}' must have a valid DoH license on {act.start}", trace=trace))
        return errors

    # Fires when: Clinician is on the insurance exclusion list on the activity date (for non-self-pay, from 2018-06-01)
    def _rule_283(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2018, 6, 1):
            return []
        errors = []
        for c in model.claims:
            if c.payer_id in _SELF_PAY_PAYER_IDS:
                continue
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None or s < datetime(2016, 1, 1):
                    continue
                cln = act.clinician or ""
                if not cln:
                    continue
                if res.is_clinician_excluded_hsf_on_date(cln, s):
                    s_str = s.strftime("%d/%m/%Y")
                    trace = (
                        f"Condition 1 — Claim.PayerID: '{c.payer_id}' → not self-pay ✓",
                        f"Condition 2 — Activity.Start: '{act.start}' → ≥ 01/01/2016 ✓",
                        f"Condition 3 — Clinician: '{cln}' → on HSF insurance exclusion list on {s_str} → VIOLATION",
                    )
                    errors.append(self._err(283, f"Claim '{c.id}', Activity '{act.id or act.code}': Clinician '{cln}' is on the insurance exclusion list on {act.start}", trace=trace))
        return errors

    # Fires when: Activity.Clinician is missing for activities from 01/09/2018 (sender not in exclusion list 2)
    def _rule_286(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        if res.in_exclusion_list_2(sender):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None or s < datetime(2018, 9, 1):
                    continue
                if not act.clinician or not act.clinician.strip():
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list 2 ✓",
                        f"Condition 2 — Activity.Start: '{act.start}' → ≥ 01/09/2018 ✓",
                        f"Condition 3 — Activity.Clinician: '{act.clinician}' → empty → VIOLATION",
                    )
                    errors.append(self._err(286, f"Claim '{c.id}', Activity '{act.id or act.code}': Activity.Clinician must be present for activities from 01/09/2018", trace=trace))
        return errors

    # ── Diagnosis / DxInfo checks ──────────────────────────────────────────────

    # Fires when: DxInfo is present on a claim with encounter before 01/12/2014
    def _rule_238(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe >= datetime(2014, 12, 1):
                continue
            for diag in c.diagnoses:
                if diag.dx_info:
                    errors.append(self._err(238, f"Claim '{c.id}': DxInfo may only be used for encounters on or after 01/12/2014 (Encounter.Start={fe.strftime('%d/%m/%Y %H:%M')})",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Earliest Encounter.Start: {fe.strftime('%d/%m/%Y %H:%M')} < 01/12/2014",
                            f"DxInfo present on diagnosis → not allowed before 01/12/2014 → VIOLATION",
                        )))
                    break
        return errors

    # Fires when: DxInfo.Type='POA' is used on a non-inpatient encounter (from 2014-12-01)
    def _rule_243(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 12, 1):
            return []
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2014, 12, 1):
                continue
            enc_types = {e.type for e in c.encounters}
            inpatient = bool(enc_types.intersection({3, 4}))
            for diag in c.diagnoses:
                for dxi in diag.dx_info:
                    if dxi.type == "POA" and not inpatient:
                        errors.append(self._err(243, f"Claim '{c.id}': DxInfo.Type='POA' is only allowed for inpatient (Encounter.Type=3 or 4)",
                            trace=(
                                f"Claim.ID: '{c.id}'",
                                f"Encounter types: {sorted(enc_types)}",
                                f"Inpatient (type 3 or 4): {inpatient} → POA DxInfo requires inpatient → VIOLATION",
                            )))
                        break
        return errors

    # Fires when: DxInfo.Type='POA' has an invalid code (not Y/N/U/W/1) (from 2014-12-01)
    def _rule_244(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 12, 1):
            return []
        _valid_poa_codes = frozenset({"Y", "N", "U", "W", "1"})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2014, 12, 1):
                continue
            for diag in c.diagnoses:
                for dxi in diag.dx_info:
                    if dxi.type == "POA" and dxi.code not in _valid_poa_codes:
                        errors.append(self._err(244, f"Claim '{c.id}': DxInfo.Code '{dxi.code}' is not valid for POA (must be Y/N/U/W/1)",
                            trace=(
                                f"Claim.ID: '{c.id}'",
                                f"Diagnosis.Code: '{diag.code}'",
                                f"DxInfo.Type: 'POA', DxInfo.Code: '{dxi.code}'",
                                f"Allowed POA codes: Y, N, U, W, 1 → '{dxi.code}' not valid → VIOLATION",
                            )))
        return errors

    # Fires when: a Diagnosis has more than one DxInfo entry with type='POA'
    def _rule_245(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for diag in c.diagnoses:
                poa_count = sum(1 for dxi in diag.dx_info if dxi.type == "POA")
                if poa_count > 1:
                    errors.append(self._err(245, f"Claim '{c.id}': Diagnosis '{diag.code}' has {poa_count} DxInfo entries with type POA (max 1 allowed)",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Diagnosis.Code: '{diag.code}'",
                            f"DxInfo entries with type='POA': {poa_count} (max allowed: 1) → VIOLATION",
                        )))
        return errors

    # Fires when: Encounter.EligibilityIDPayer is set for an encounter before 01/12/2014
    def _rule_247(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if not enc.eligibility_id_payer:
                    continue
                s = _parse_datetime(enc.start)
                if s is not None and s < datetime(2014, 12, 1):
                    errors.append(self._err(247, f"Claim '{c.id}': Encounter.EligibilityIDPayer must not be set for encounters before 01/12/2014",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Encounter.Start: '{enc.start}' < 01/12/2014",
                            f"Encounter.EligibilityIDPayer: '{enc.eligibility_id_payer}' → must be empty before 01/12/2014 → VIOLATION",
                        )))
        return errors

    # Fires when: Diagnosis.Type='ReasonForVisit' used before 01/12/2014
    def _rule_248(self, model: cs.ClaimSubmission, res) -> list:
        if not model.header.sender_id:
            return []
        errors = []
        for c in model.claims:
            for diag in c.diagnoses:
                if diag.type != "ReasonForVisit":
                    continue
                fe = _first_enc_start(c)
                if fe is not None and fe < datetime(2014, 12, 1):
                    errors.append(self._err(248, f"Claim '{c.id}': Diagnosis.Type='ReasonForVisit' may only be used for encounters on or after 01/12/2014",
                        trace=(
                            f"Claim.ID: '{c.id}'",
                            f"Diagnosis.Type: 'ReasonForVisit'",
                            f"Earliest Encounter.Start: {fe.strftime('%d/%m/%Y') if fe else 'N/A'} < 01/12/2014 → VIOLATION",
                        )))
        return errors

    # Fires when: Activity.VATPercent is present but outside 0–100
    def _rule_281(self, model: cs.ClaimSubmission, res) -> list:
        if not model.header.sender_id:
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                vp = act.vat_percent
                if vp is not None and not (0 <= vp <= 100):
                    errors.append(self._err(281, f"Claim '{c.id}', Activity '{act.id or act.code}': VATPercent {vp} must be between 0 and 100",
                        trace=(
                            f"Activity: '{act.id or act.code}'",
                            f"Activity.VATPercent: {vp}",
                            f"Allowed range: 0–100 → {vp} out of range → VIOLATION",
                        )))
        return errors

    # Fires when: inpatient Principal/Secondary diagnosis lacks DxInfo.Type='POA' (from 2018-09-01, not in exclusion list 6)
    def _rule_287(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        if res.in_exclusion_list_6(sender):
            return []
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2018, 9, 1):
                continue
            enc_types = {e.type for e in c.encounters}
            if not enc_types.intersection({3, 4}):
                continue
            for diag in c.diagnoses:
                if diag.type not in ("Principal", "Secondary"):
                    continue
                has_poa = any(dxi.type == "POA" for dxi in diag.dx_info)
                if not has_poa:
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list 6 ✓",
                        f"Condition 2 — Encounter.Start ≥ 01/09/2018, inpatient encounter type ✓",
                        f"Condition 3 — Diagnosis: '{diag.code}' (type: {diag.type}) → has DxInfo.Type='POA': {has_poa} → VIOLATION",
                    )
                    errors.append(self._err(287, f"Claim '{c.id}': Diagnosis '{diag.code}' must have DxInfo.Type='POA' for inpatient encounters from 01/09/2018", trace=trace))
        return errors

    # Fires when: chronic outpatient Principal diagnosis requires Year of Onset DxInfo but it is absent (MF-prefix sender, from 2021-09-07)
    def _rule_288(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        if not sender.startswith("MF"):
            return []
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2021, 9, 7):
                continue
            enc_types = {e.type for e in c.encounters}
            if not enc_types.intersection({1, 2}):
                continue
            for diag in c.diagnoses:
                if diag.type != "Principal":
                    continue
                yoo_required = res.is_yearofonset_required(diag.code)
                if not yoo_required:
                    continue
                has_yoo = any(
                    dxi.type == "Year of Onset" and dxi.code.isdigit() and len(dxi.code) == 4
                    for dxi in diag.dx_info
                )
                if not has_yoo:
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → MF-prefix ✓",
                        f"Condition 2 — Encounter.Start ≥ 07/09/2021, outpatient encounter type ✓",
                        f"Condition 3 — Diagnosis: '{diag.code}' → Year of Onset required: {yoo_required} ✓",
                        f"Condition 4 — DxInfo with Type='Year of Onset' and 4-digit year: {has_yoo} → missing → VIOLATION",
                    )
                    errors.append(self._err(288, f"Claim '{c.id}': Diagnosis '{diag.code}' requires a DxInfo with Type='Year of Onset' and a 4-digit year code", trace=trace))
        return errors

    # Fires when: Z38 Principal diagnosis has Birth Weight DxInfo with non-4-digit code (from 2019-11-14)
    def _rule_290(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2019, 11, 14):
                continue
            for diag in c.diagnoses:
                if diag.type != "Principal":
                    continue
                if not diag.code.upper().startswith("Z38"):
                    continue
                for dxi in diag.dx_info:
                    if dxi.type == "Birth Weight" and dxi.code:
                        if not (dxi.code.isdigit() and len(dxi.code) == 4):
                            errors.append(self._err(290, f"Claim '{c.id}': Diagnosis '{diag.code}' DxInfo Birth Weight code '{dxi.code}' must be a 4-digit whole number",
                                trace=(
                                    f"Claim.ID: '{c.id}'",
                                    f"Diagnosis.Code: '{diag.code}' (starts with Z38)",
                                    f"DxInfo.Type: 'Birth Weight', DxInfo.Code: '{dxi.code}'",
                                    f"Code must be a 4-digit whole number → '{dxi.code}' is not → VIOLATION",
                                )))
        return errors

    # Fires when: Contract.PackageName is not a valid benefit package for the stated PayerID (from 2020-01-12, not to HAAD)
    def _rule_291(self, model: cs.ClaimSubmission, res) -> list:
        if model.header.receiver_id == _HAAD_RECEIVER_ID:
            return []
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2020, 1, 12):
                continue
            if c.contract is None or not c.contract.package_name:
                continue
            pkg = c.contract.package_name
            if not res.is_valid_benefit_package_for_payer(pkg, c.payer_id):
                trace = (
                    f"Condition 1 — Encounter.Start ≥ 12/01/2020, ReceiverID ≠ HAAD ✓",
                    f"Condition 2 — Contract.PackageName: '{pkg}' → not a valid benefit package for payer '{c.payer_id}' → VIOLATION",
                    f"Note: package names are case-sensitive. Verify exact value in the payer's benefit package list.",
                )
                errors.append(self._err(291, f"Claim '{c.id}': Contract.PackageName '{pkg}' is not a valid benefit package for payer '{c.payer_id}'", trace=trace))
        return errors

    # ── Internal complaint resubmission consistency (Rules 292_1–292_6) ───────

    def _check_292_precondition(self, model, claim) -> "dict | None":
        """Return previous claim dict if the 292 preconditions are met, else None."""
        resub = claim.resubmission
        if resub is None or resub.type.lower() != "internal complaint":
            return None
        fe = _first_enc_start(claim)
        if fe is None or fe < datetime(2020, 1, 12):
            return None
        return resub  # caller must fetch from res

    # Fires when: internal complaint resubmission (from 2020-01-12) has no previous claim in the DB
    def _rule_292_1(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if self._check_292_precondition(model, c) is None:
                continue
            prev = res.get_previous_claim_fields(model.header.sender_id, c.id)
            if prev is None:
                errors.append(self._err("292_1", f"Claim '{c.id}': no previous claim found for internal complaint resubmission",
                    trace=(
                        f"Claim.ID: '{c.id}', Resubmission.Type: 'internal complaint'",
                        f"DB lookup: no previous claim found for sender '{model.header.sender_id}', Claim.ID '{c.id}' → VIOLATION",
                    )))
        return errors

    # Fires when: internal complaint resubmission Claim.MemberID doesn't match original
    def _rule_292_2(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if self._check_292_precondition(model, c) is None:
                continue
            prev = res.get_previous_claim_fields(model.header.sender_id, c.id)
            if prev and prev.get("MEMBER_ID", "").strip() != (c.member_id or "").strip():
                errors.append(self._err("292_2", f"Claim '{c.id}': MemberID must match original claim in internal complaint resubmission",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Original Claim.MemberID: '{prev.get('MEMBER_ID', '')}'",
                        f"Current Claim.MemberID: '{c.member_id}' → mismatch → VIOLATION",
                    )))
        return errors

    # Fires when: internal complaint resubmission Claim.PayerID doesn't match original
    def _rule_292_3(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if self._check_292_precondition(model, c) is None:
                continue
            prev = res.get_previous_claim_fields(model.header.sender_id, c.id)
            if prev and prev.get("PAYER_ID", "") != c.payer_id:
                errors.append(self._err("292_3", f"Claim '{c.id}': PayerID must match original claim in internal complaint resubmission",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Original Claim.PayerID: '{prev.get('PAYER_ID', '')}'",
                        f"Current Claim.PayerID: '{c.payer_id}' → mismatch → VIOLATION",
                    )))
        return errors

    # Fires when: internal complaint resubmission Claim.ProviderID doesn't match original
    def _rule_292_4(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if self._check_292_precondition(model, c) is None:
                continue
            prev = res.get_previous_claim_fields(model.header.sender_id, c.id)
            if prev and prev.get("PROVIDER_ID", "") != c.provider_id:
                errors.append(self._err("292_4", f"Claim '{c.id}': ProviderID must match original claim in internal complaint resubmission",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Original Claim.ProviderID: '{prev.get('PROVIDER_ID', '')}'",
                        f"Current Claim.ProviderID: '{c.provider_id}' → mismatch → VIOLATION",
                    )))
        return errors

    # Fires when: internal complaint resubmission EmiratesIDNumber doesn't match original
    def _rule_292_5(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if self._check_292_precondition(model, c) is None:
                continue
            prev = res.get_previous_claim_fields(model.header.sender_id, c.id)
            if prev is None:
                continue
            prev_eid = prev.get("EMIRATES_ID", "")
            cur_eid = c.emirates_id_number
            if prev_eid != cur_eid and prev_eid != cur_eid.replace("-", ""):
                errors.append(self._err("292_5", f"Claim '{c.id}': EmiratesIDNumber must match original claim in internal complaint resubmission",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Original EmiratesIDNumber: '{prev_eid}'",
                        f"Current EmiratesIDNumber: '{cur_eid}' → mismatch → VIOLATION",
                    )))
        return errors

    # Fires when: internal complaint resubmission Contract.PackageName doesn't match original
    def _rule_292_6(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if self._check_292_precondition(model, c) is None:
                continue
            prev = res.get_previous_claim_fields(model.header.sender_id, c.id)
            if prev is None:
                continue
            prev_pkg = (prev.get("PACKAGE_NAME") or "").strip()
            cur_pkg = (c.contract.package_name if c.contract else None) or ""
            cur_pkg = cur_pkg.strip()
            if prev_pkg != cur_pkg:
                errors.append(self._err("292_6", f"Claim '{c.id}': Contract.PackageName must match original claim in internal complaint resubmission",
                    trace=(
                        f"Claim.ID: '{c.id}'",
                        f"Original Contract.PackageName: '{prev_pkg}'",
                        f"Current Contract.PackageName: '{cur_pkg}' → mismatch → VIOLATION",
                    )))
        return errors

    # ── Encounter-type / service-code restrictions ────────────────────────────

    # Fires when: non-resubmitted claim has a duplicate activity combination already submitted by this provider
    def _rule_233(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if c.resubmission is not None:
                continue
            for diag in c.diagnoses:
                if diag.type == "Principal" and (diag.code.upper().startswith("Z38") or diag.code in _DUMMY_EMIRATES_IDS):
                    break
            else:
                # No Z38 diagnosis: check for duplicate activities cross-claim
                for act in c.activities:
                    dup_id = res.find_duplicate_claim_id(
                        c.provider_id, c.member_id or "", c.payer_id,
                        model.header.receiver_id,
                        _parse_datetime(act.start), act.type, act.code,
                        act.quantity, act.ordering_clinician or "")
                    if dup_id and dup_id != c.id:
                        errors.append(self._err(233, f"Claim '{c.id}': duplicate activity combination already exists with Claim.ID '{dup_id}'",
                            trace=(
                                f"Claim.ID: '{c.id}'",
                                f"Activity: '{act.id or act.code}', Type: {act.type}, Start: '{act.start}'",
                                f"Duplicate found in Claim.ID: '{dup_id}' → VIOLATION",
                            )))
                        break
        return errors

    # Fires when: SelfPay/Tourism payer Claim.MemberID doesn't match the expected FacilityID#PatientID pattern (from 2014-09-01)
    def _rule_234(self, model: cs.ClaimSubmission, res) -> list:
        _tourism = frozenset({"SelfPay", "ProFormaPayer", "MedicalTourismSelfPay", "MedicalTourismOther"})
        errors = []
        for c in model.claims:
            if c.payer_id not in _tourism:
                continue
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2014, 9, 1):
                continue
            for enc in c.encounters:
                expected = f"{enc.facility_id}#{enc.patient_id}"
                if c.member_id != expected:
                    errors.append(self._err(234, f"Claim '{c.id}': MemberID must be '{expected}' for SelfPay patient (got '{c.member_id}')",
                        trace=(
                            f"Claim.ID: '{c.id}', PayerID: '{c.payer_id}' (SelfPay)",
                            f"Encounter.FacilityID: '{enc.facility_id}', Encounter.PatientID: '{enc.patient_id}'",
                            f"Expected MemberID: '{expected}'",
                            f"Current MemberID: '{c.member_id}' → mismatch → VIOLATION",
                        )))
                    break
        return errors

    def _enc_type_code_check(self, model, required_enc_type, codes, cutoff, rule_id):
        """Helper: code only allowed when at least one encounter has required_enc_type."""
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < cutoff:
                continue
            enc_types = {e.type for e in c.encounters}
            for act in c.activities:
                if act.code not in codes:
                    continue
                if isinstance(required_enc_type, (set, frozenset)):
                    if not enc_types.intersection(required_enc_type):
                        errors.append(self._err(rule_id, f"Claim '{c.id}', Activity '{act.id or act.code}': code '{act.code}' can only be used with Encounter.Type in {sorted(required_enc_type)}",
                            trace=(
                                f"Activity: '{act.id or act.code}', Code: '{act.code}'",
                                f"Claim encounter types: {sorted(enc_types)}",
                                f"Required encounter type(s): {sorted(required_enc_type)}",
                                f"No matching encounter type found → VIOLATION",
                            )))
                else:
                    if required_enc_type not in enc_types:
                        errors.append(self._err(rule_id, f"Claim '{c.id}', Activity '{act.id or act.code}': code '{act.code}' can only be used with Encounter.Type={required_enc_type}",
                            trace=(
                                f"Activity: '{act.id or act.code}', Code: '{act.code}'",
                                f"Claim encounter types: {sorted(enc_types)}",
                                f"Required encounter type: {required_enc_type}",
                                f"Encounter.Type={required_enc_type} not found → VIOLATION",
                            )))
        return errors

    # Fires when: service codes 17-30/17-31 are used without Encounter.Type=3 (from 2020-04-16)
    def _rule_296(self, m, r): return self._enc_type_code_check(m, 3, {"17-30","17-31"}, datetime(2020, 4, 16), 296)
    # Fires when: service codes 17-27-1/17-27-2 are used without Encounter.Type=12 (from 2020-05-01)
    def _rule_297(self, m, r): return self._enc_type_code_check(m, 12, {"17-27-1","17-27-2"}, datetime(2020, 5, 1), 297)
    # Fires when: service code 70 is used without Encounter.Type=1 (from 2020-04-01)
    def _rule_298(self, m, r): return self._enc_type_code_check(m, 1, {"70"}, datetime(2020, 4, 1), 298)
    # Fires when: service codes 52-01 to 52-09 are used without Encounter.Type=7 (from 2021-01-14)
    def _rule_299(self, m, r): return self._enc_type_code_check(m, 7, {"52-01","52-02","52-03","52-04","52-05","52-06","52-07","52-08","52-09"}, datetime(2021, 1, 14), 299)
    # Fires when: service code 17-27-3 is used without Encounter.Type=1 (from 2020-07-01)
    def _rule_300(self, m, r): return self._enc_type_code_check(m, 1, {"17-27-3"}, datetime(2020, 7, 1), 300)
    # Fires when: service code 01-10 is used without Encounter.Type=1 (from 2021-02-15)
    def _rule_302(self, m, r): return self._enc_type_code_check(m, 1, {"01-10"}, datetime(2021, 2, 15), 302)
    # Fires when: service code 96 is used without Encounter.Type=1 (from 2021-06-01)
    def _rule_304(self, m, r): return self._enc_type_code_check(m, 1, {"96"}, datetime(2021, 6, 1), 304)
    # Fires when: service codes 97-01/97-02 are used without Encounter.Type=12 (from 2021-01-01)
    def _rule_309(self, m, r): return self._enc_type_code_check(m, 12, {"97-01","97-02"}, datetime(2021, 1, 1), 309)
    # Fires when: service code 17-26-5 is used without Encounter.Type=12 (from 2021-09-15)
    def _rule_313(self, m, r): return self._enc_type_code_check(m, 12, {"17-26-5"}, datetime(2021, 9, 15), 313)
    # Fires when: service codes 70-01 to 70-11 are used without Encounter.Type=1 (from 2022-02-01)
    def _rule_314(self, m, r): return self._enc_type_code_check(m, 1, {"70-01","70-02","70-03","70-04","70-05","70-06","70-07","70-08","70-09","70-10","70-11"}, datetime(2022, 2, 1), 314)
    # Fires when: service codes 52-10/52-11/52-12 are used without Encounter.Type=7 (from 2022-07-01)
    def _rule_322(self, m, r): return self._enc_type_code_check(m, 7, {"52-10","52-11","52-12"}, datetime(2022, 7, 1), 322)
    # Fires when: service codes 08-01 to 08-09 are used without Encounter.Type=1 (from 2022-07-18)
    def _rule_324(self, m, r): return self._enc_type_code_check(m, 1, {"08-01","08-02","08-03","08-04","08-05","08-06","08-07","08-08","08-09"}, datetime(2022, 7, 18), 324)
    # Fires when: service code A0428 is used without Encounter.Type=41 (from 2023-01-08)
    def _rule_344(self, m, r): return self._enc_type_code_check(m, 41, {"A0428"}, datetime(2023, 1, 8), 344)
    # Fires when: service codes 01-11-01 to 01-11-04 are used without Encounter.Type=1 (from 2022-11-01)
    def _rule_345(self, m, r): return self._enc_type_code_check(m, 1, {"01-11-01","01-11-02","01-11-03","01-11-04"}, datetime(2022, 11, 1), 345)
    # Fires when: service codes 52-21 to 52-33 are used without Encounter.Type=7 (from 2023-06-30)
    def _rule_357(self, m, r): return self._enc_type_code_check(m, 7, {"52-21","52-22","52-23","52-24","52-25","52-26","52-27","52-28","52-29","52-30","52-31","52-32","52-33"}, datetime(2023, 6, 30), 357)
    # Fires when: service codes 54-01 to 54-04 are used without Encounter.Type=1 (from 2023-09-28)
    def _rule_358(self, m, r): return self._enc_type_code_check(m, 1, {"54-01","54-02","54-03","54-04"}, datetime(2023, 9, 28), 358)
    # Fires when: service codes 22-02/22-03/22-06/22-07 used without Encounter.Type=3 (from 2022-06-01)
    def _rule_359(self, m, r): return self._enc_type_code_check(m, 3, {"22-02","22-03","22-06","22-07"}, datetime(2022, 6, 1), 359)
    # Fires when: service codes 22-01/22-04/22-05/22-08 used without Encounter.Type=1 (from 2022-06-01)
    def _rule_364(self, m, r): return self._enc_type_code_check(m, 1, {"22-01","22-04","22-05","22-08"}, datetime(2022, 6, 1), 364)

    # Fires when: a Diagnosis code is not a valid ICD-10 code on the encounter date (from 2016-09-15, not in exclusion list 7)
    def _rule_305(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe <= datetime(2016, 9, 15):
                continue
            if res.in_exclusion_list_7(sender):
                continue
            for diag in c.diagnoses:
                if not res.is_icd10_code_valid_on_date(diag.code, fe):
                    fe_str = fe.strftime("%d/%m/%Y")
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list 7 ✓",
                        f"Condition 2 — Encounter.Start: {fe_str} → after 15/09/2016 ✓",
                        f"Condition 3 — ICD-10 lookup: '{diag.code}' on {fe_str} → NOT FOUND or inactive → VIOLATION",
                        f"Note: ICD-10 codes are case-sensitive. Verify exact casing and effective date.",
                    )
                    errors.append(self._err(305, f"Claim '{c.id}': Diagnosis '{diag.code}' is not a valid ICD-10 code on {fe.strftime('%d/%m/%Y')}", trace=trace))
        return errors

    # ── Shadow / PTE disposition checks ───────────────────────────────────────

    # Fires when: shadow service code (89-93, 80-01 to 80-03) is used without shadow DispositionFlag and inpatient Encounter (from 2022-05-01)
    def _rule_306(self, model: cs.ClaimSubmission, res) -> list:
        _shadow_codes = frozenset({"89","90","91","92","93","80-01","80-02","80-03"})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 5, 1):
                continue
            disp = model.header.disposition_flag
            is_shadow = disp in _SHADOW_FLAGS
            enc_types = {e.type for e in c.encounters}
            inpatient = bool(enc_types.intersection({3, 4}))
            for act in c.activities:
                if act.code in _shadow_codes and (not is_shadow or not inpatient):
                    errors.append(self._err(306, f"Claim '{c.id}', Activity '{act.id or act.code}': code '{act.code}' requires shadow DispositionFlag and Encounter.Type=3 or 4",
                        trace=(
                            f"Activity code: '{act.code}' → in shadow codes set ✓",
                            f"DispositionFlag: '{disp}' → shadow flag: {is_shadow}",
                            f"Encounter types: {sorted(enc_types)} → inpatient (3 or 4): {inpatient}",
                            f"Condition failed: shadow={is_shadow}, inpatient={inpatient} → VIOLATION",
                        )))
        return errors

    # Fires when: service codes 91/92 are present in a non-inpatient encounter and the DRG Activity.Net is not 0 (from 2022-05-01)
    def _rule_307(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 5, 1):
                continue
            enc_types = {e.type for e in c.encounters}
            if enc_types.intersection({3, 4, 5, 6}):
                continue
            codes_91_92 = any(a.code in {"91","92"} for a in c.activities)
            if not codes_91_92:
                continue
            for act in c.activities:
                if act.type == 9 and act.net != 0:
                    errors.append(self._err(307, f"Claim '{c.id}', Activity '{act.id or act.code}': DRG Activity.Net must be 0 when service codes 91 or 92 are present",
                        trace=(
                            f"Encounter types: {sorted(enc_types)} → non-inpatient (not 3/4/5/6) ✓",
                            f"Service codes 91 or 92 present ✓",
                            f"DRG Activity (type=9) code: '{act.code}', Net: {act.net} ≠ 0 → VIOLATION",
                        )))
        return errors

    # Fires when: service codes 89-93 are present but no DRG activity (type=9) is present (from 2022-05-01)
    def _rule_308(self, model: cs.ClaimSubmission, res) -> list:
        _triggers = frozenset({"89","90","91","92","93"})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 5, 1):
                continue
            has_trigger = any(a.code in _triggers for a in c.activities)
            if not has_trigger:
                continue
            has_drg = any(a.type == 9 for a in c.activities)
            if not has_drg:
                trigger_codes = [a.code for a in c.activities if a.code in _triggers]
                errors.append(self._err(308, f"Claim '{c.id}': DRG activity (type 9) must be present when service codes 89-93 are present",
                    trace=(
                        f"Service codes present from 89-93 set: {trigger_codes}",
                        f"DRG activity (type=9) present: {has_drg} → missing → VIOLATION",
                    )))
        return errors

    # Fires when: service code 80-03 is present but no CPT/HCPCS code from the Under-Supply list exists (from 2022-05-01)
    def _rule_316(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 5, 1):
                continue
            has_80_03 = any(a.code == "80-03" for a in c.activities)
            if not has_80_03:
                continue
            has_undersupply = any(res.is_undersupply_code(a.code) for a in c.activities)
            if not has_undersupply:
                trace = (
                    f"Condition 1 — Encounter.Start ≥ 01/05/2022 ✓",
                    f"Condition 2 — Service code '80-03' present ✓",
                    f"Condition 3 — Under-Supply CPT/HCPCS code present: {has_undersupply} → missing → VIOLATION",
                )
                errors.append(self._err(316, f"Claim '{c.id}': when service code 80-03 is present, at least one CPT/HCPCS code from the Under-Supply list must be present", trace=trace))
        return errors

    # Fires when: DispositionFlag is a shadow flag but SenderID is not a valid shadow provider (from 2022-05-01)
    def _rule_317(self, model: cs.ClaimSubmission, res) -> list:
        disp = model.header.disposition_flag
        if disp not in _SHADOW_FLAGS:
            return []
        sender = model.header.sender_id
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 5, 1):
                continue
            if not res.is_shadow_provider(sender):
                trace = (
                    f"Condition 1 — DispositionFlag: '{disp}' → shadow flag ✓",
                    f"Condition 2 — SenderID: '{sender}' → NOT a valid Shadow provider → VIOLATION",
                )
                return [self._err(317, f"Header.SenderID '{sender}' must be a valid Shadow provider for shadow DispositionFlag", trace=trace)]
        return errors

    # Fires when: DispositionFlag is a shadow flag but ReceiverID is not a valid shadow payer (from 2022-05-01)
    def _rule_318(self, model: cs.ClaimSubmission, res) -> list:
        disp = model.header.disposition_flag
        if disp not in _SHADOW_FLAGS:
            return []
        receiver = model.header.receiver_id
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 5, 1):
                continue
            if not res.is_shadow_insurer(receiver):
                trace = (
                    f"Condition 1 — DispositionFlag: '{disp}' → shadow flag ✓",
                    f"Condition 2 — ReceiverID: '{receiver}' → NOT a valid Shadow payer → VIOLATION",
                )
                return [self._err(318, f"Header.ReceiverID '{receiver}' must be a valid Shadow payer for shadow DispositionFlag", trace=trace)]
        return errors

    # Fires when: shadow DispositionFlag is used but Encounter.Type is outside {1-6} (from 2022-05-01)
    def _rule_319(self, model: cs.ClaimSubmission, res) -> list:
        if model.header.disposition_flag not in _SHADOW_FLAGS:
            return []
        _allowed = frozenset({1, 2, 3, 4, 5, 6})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 5, 1):
                continue
            for enc in c.encounters:
                if enc.type not in _allowed:
                    errors.append(self._err(319, f"Claim '{c.id}': Encounter.Type {enc.type} is not allowed with shadow DispositionFlag (must be 1-6)",
                        trace=(
                            f"DispositionFlag: '{model.header.disposition_flag}' → shadow flag ✓",
                            f"Encounter.Type: {enc.type} → not in allowed set {{1,2,3,4,5,6}} → VIOLATION",
                        )))
        return errors

    # Fires when: shadow DispositionFlag is used but a Resubmission element is present (from 2022-05-01)
    def _rule_320(self, model: cs.ClaimSubmission, res) -> list:
        if model.header.disposition_flag not in _SHADOW_FLAGS:
            return []
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 5, 1):
                continue
            if c.resubmission is not None:
                errors.append(self._err(320, f"Claim '{c.id}': Resubmission must not be present with shadow DispositionFlag",
                    trace=(
                        f"DispositionFlag: '{model.header.disposition_flag}' → shadow flag ✓",
                        f"Resubmission: present (value: '{c.resubmission}') → VIOLATION",
                    )))
        return errors

    # Fires when: shadow DispositionFlag is used and service code '99' is present (from 2022-05-01)
    def _rule_321(self, model: cs.ClaimSubmission, res) -> list:
        if model.header.disposition_flag not in _SHADOW_FLAGS:
            return []
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 5, 1):
                continue
            for act in c.activities:
                if act.code == "99":
                    errors.append(self._err(321, f"Claim '{c.id}', Activity '{act.id or act.code}': service code '99' cannot be used with shadow DispositionFlag from 01/05/2022",
                        trace=(
                            f"DispositionFlag: '{model.header.disposition_flag}' → shadow flag ✓",
                            f"Activity code: '{act.code}' = '99' → forbidden with shadow flag → VIOLATION",
                        )))
        return errors

    # ── Contract / package / payer restrictions ───────────────────────────────

    # Fires when: ReceiverID=D002 or PayerID=E001 and Contract.PackageName is not valid for payer E001 (from 2022-12-15, not IPC provider)
    def _rule_323(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 12, 15):
                continue
            if model.header.receiver_id != "D002" and c.payer_id != "E001":
                continue
            if res.is_ipc_provider(sender):
                continue
            pkg = c.contract.package_name if c.contract else None
            if not pkg or not res.is_valid_benefit_package_for_payer(pkg, "E001"):
                trace = (
                    f"Condition 1 — ReceiverID='D002' or PayerID='E001', Encounter.Start ≥ 15/12/2022 ✓",
                    f"Condition 2 — SenderID: '{sender}' → not an IPC provider ✓",
                    f"Condition 3 — Contract.PackageName: '{pkg}' → not valid for payer 'E001' → VIOLATION",
                    f"Note: package names are case-sensitive. Verify exact value in the E001 benefit package list.",
                )
                errors.append(self._err(323, f"Claim '{c.id}': Contract.PackageName '{pkg}' is not in the approved package list for payer 'E001'", trace=trace))
        return errors

    # Fires when: service codes 08-01/08-04/08-07 are present but Activity.PriorAuthorizationID is missing (from 2022-07-18)
    def _rule_325(self, model: cs.ClaimSubmission, res) -> list:
        _pa_codes = frozenset({"08-01","08-04","08-07"})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 7, 18):
                continue
            for act in c.activities:
                if act.code in _pa_codes and not act.prior_authorization_id:
                    errors.append(self._err(325, f"Claim '{c.id}', Activity '{act.id or act.code}': PriorAuthorizationID must be present for code '{act.code}'",
                        trace=(
                            f"Activity code: '{act.code}' → requires PriorAuthorizationID ✓",
                            f"Activity.PriorAuthorizationID: '{act.prior_authorization_id}' → missing/empty → VIOLATION",
                        )))
        return errors

    # Fires when: a claim with 08-xx service codes has 08-xx Activity.Net<=0 or non-08-xx Activity.Net!=0 (from 2022-07-18)
    def _rule_326(self, model: cs.ClaimSubmission, res) -> list:
        _codes_08 = frozenset({"08-01","08-02","08-03","08-04","08-05","08-06","08-07","08-08","08-09"})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2022, 7, 18):
                continue
            has_08 = any(a.code in _codes_08 for a in c.activities)
            if not has_08:
                continue
            for act in c.activities:
                if act.code in _codes_08 and act.net <= 0:
                    errors.append(self._err(326, f"Claim '{c.id}', Activity '{act.id or act.code}': Net must be > 0 for code '{act.code}'",
                        trace=(
                            f"08-xx code present: '{act.code}' → Net must be > 0",
                            f"Activity.Net: {act.net} ≤ 0 → VIOLATION",
                        )))
                elif act.code not in _codes_08 and act.net != 0:
                    errors.append(self._err(326, f"Claim '{c.id}', Activity '{act.id or act.code}': Net must be 0 for activities other than 08-xx codes",
                        trace=(
                            f"Claim has 08-xx codes → non-08-xx activities must have Net=0",
                            f"Activity code: '{act.code}', Net: {act.net} ≠ 0 → VIOLATION",
                        )))
        return errors

    # Fires when: Encounter.Start is more than 4 years old (5 for IPC) for tx from 2022-09-15, not in exclusion list 9
    def _rule_327(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2022, 9, 15):
            return []
        sender = model.header.sender_id
        if res.in_exclusion_list_9(sender):
            return []
        is_ipc = res.is_ipc_provider(sender)
        max_years = 5 if is_ipc else 4
        cutoff = datetime.now() - timedelta(days=max_years * 365)
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                s = _parse_datetime(enc.start)
                if s is not None and s < cutoff:
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list 9, IPC: {is_ipc} → max {max_years} year window ✓",
                        f"Condition 2 — Encounter.Start: '{enc.start}' → older than {max_years} years ago (cutoff: {cutoff.strftime('%d/%m/%Y')}) → VIOLATION",
                    )
                    errors.append(self._err(327, f"Claim '{c.id}': Encounter.Start {enc.start} must be within {max_years} years", trace=trace))
        return errors

    # Fires when: EmiratesIDNumber is a dummy or invalid value for non-HAAD non-IPC non-@-payer claims (from 2030-01-05)
    def _rule_342(self, model: cs.ClaimSubmission, res) -> list:
        receiver = model.header.receiver_id
        sender = model.header.sender_id
        is_ipc = res.is_ipc_provider(sender)
        if receiver == _HAAD_RECEIVER_ID or is_ipc:
            return []
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2030, 1, 5):
                continue
            if c.payer_id.startswith("@"):
                continue
            eid = c.emirates_id_number
            if "-" not in eid:
                continue
            if eid in _DUMMY_EMIRATES_IDS or not _is_valid_emirates_id(eid):
                trace = (
                    f"Condition 1 — ReceiverID: '{receiver}' → not HAAD ✓",
                    f"Condition 2 — SenderID: '{sender}' → IPC provider lookup → NO → rule applies ✓",
                    f"Condition 3 — EmiratesIDNumber: '{eid}' → {'dummy value' if eid in _DUMMY_EMIRATES_IDS else 'fails format/Luhn check'} → VIOLATION",
                )
                errors.append(self._err(342, f"Claim '{c.id}': EmiratesIDNumber '{eid}' must be a valid Emirates ID or Unified Number", trace=trace))
        return errors

    # Fires when: Encounter.EndType 8-12 is used with Encounter.Type≠10, or Encounter.Type=10 has EndType outside {8-12} (from 2023-02-28)
    def _rule_343(self, model: cs.ClaimSubmission, res) -> list:
        _type10_end_types = frozenset({8, 9, 10, 11, 12})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2023, 2, 28):
                continue
            for enc in c.encounters:
                if enc.end_type is None:
                    continue
                if enc.type == 10 and enc.end_type not in _type10_end_types:
                    errors.append(self._err(343, f"Claim '{c.id}': Encounter.EndType {enc.end_type} is only valid for Encounter.Type=10",
                        trace=(
                            f"Encounter.Type: {enc.type} = 10 → EndType must be in {{8,9,10,11,12}}",
                            f"Encounter.EndType: {enc.end_type} → not in allowed set → VIOLATION",
                        )))
                elif enc.type != 10 and enc.end_type in _type10_end_types:
                    errors.append(self._err(343, f"Claim '{c.id}': Encounter.EndType {enc.end_type} (8-12) can only be used with Encounter.Type=10",
                        trace=(
                            f"Encounter.EndType: {enc.end_type} → in type-10-only set {{8-12}}",
                            f"Encounter.Type: {enc.type} ≠ 10 → EndType 8-12 not allowed here → VIOLATION",
                        )))
        return errors

    # Fires when: PayerID is A001 or E001 and MemberID starts with '0' (from 2023-07-14, not HAAD/IPC)
    def _rule_356(self, model: cs.ClaimSubmission, res) -> list:
        receiver = model.header.receiver_id
        sender = model.header.sender_id
        is_ipc = res.is_ipc_provider(sender)
        if receiver == _HAAD_RECEIVER_ID or is_ipc:
            return []
        _payers = frozenset({"A001","E001"})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2023, 7, 14):
                continue
            if c.payer_id not in _payers:
                continue
            if c.payer_id.startswith("@"):
                continue
            if c.member_id and c.member_id.startswith("0"):
                trace = (
                    f"Condition 1 — ReceiverID: '{receiver}' → not HAAD ✓",
                    f"Condition 2 — SenderID: '{sender}' → IPC provider lookup → NO → rule applies ✓",
                    f"Condition 3 — Claim.PayerID: '{c.payer_id}' → in (A001, E001) ✓",
                    f"Condition 4 — Claim.MemberID: '{c.member_id}' → starts with '0' → VIOLATION",
                )
                errors.append(self._err(356, f"Claim '{c.id}': MemberID must not start with '0' for payer '{c.payer_id}'", trace=trace))
        return errors

    # Fires when: PayerID is a Medical Tourism payer but the patient has a valid Emirates ID (receiver=HAAD, from 2023-11-20)
    def _rule_360(self, model: cs.ClaimSubmission, res) -> list:
        _tourism_payers = frozenset({"MedicalTourismSelfPay","MedicalTourismOther"})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2023, 11, 20):
                continue
            if model.header.receiver_id != _HAAD_RECEIVER_ID:
                continue
            if c.payer_id not in _tourism_payers:
                continue
            eid = c.emirates_id_number
            if "-" not in eid:
                continue
            if eid not in _DUMMY_EMIRATES_IDS and _is_valid_emirates_id(eid):
                errors.append(self._err(360, f"Claim '{c.id}': PayerID must not be '{c.payer_id}' when patient has a valid Emirates ID",
                    trace=(
                        f"ReceiverID: '{model.header.receiver_id}' = HAAD ✓",
                        f"PayerID: '{c.payer_id}' → Medical Tourism payer ✓",
                        f"EmiratesIDNumber: '{eid}' → valid Emirates ID (not dummy) → VIOLATION",
                    )))
        return errors

    # Fires when: HCPCS code S2900 with Net>0 is used by any sender other than MF2467
    def _rule_363(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.code.upper().strip() == "S2900" and act.net > 0 and model.header.sender_id != "MF2467":
                    errors.append(self._err(363, f"Claim '{c.id}', Activity '{act.id or act.code}': HCPCS code S2900 can only be used by sender MF2467",
                        trace=(
                            f"Activity code: '{act.code}' = S2900, Net: {act.net} > 0 ✓",
                            f"SenderID: '{model.header.sender_id}' ≠ 'MF2467' → VIOLATION",
                        )))
        return errors

    # Fires when: Contract.PackageName='110' is used but ReceiverID is not 'D002' (from 2024-08-22)
    def _rule_365(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2024, 8, 22):
                continue
            if c.contract and c.contract.package_name == "110" and model.header.receiver_id != "D002":
                errors.append(self._err(365, f"Claim '{c.id}': Header.ReceiverID must be 'D002' when PackageName is '110' (got '{model.header.receiver_id}')",
                    trace=(
                        f"Contract.PackageName: '{c.contract.package_name}' = '110' ✓",
                        f"Header.ReceiverID: '{model.header.receiver_id}' ≠ 'D002' → VIOLATION",
                    )))
        return errors

    # Fires when: Contract.PackageName='110' is used but Claim.PayerID is not 'E001' (from 2024-08-22)
    def _rule_366(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2024, 8, 22):
                continue
            if c.contract and c.contract.package_name == "110" and c.payer_id != "E001":
                errors.append(self._err(366, f"Claim '{c.id}': Claim.PayerID must be 'E001' when PackageName is '110' (got '{c.payer_id}')",
                    trace=(
                        f"Contract.PackageName: '{c.contract.package_name}' = '110' ✓",
                        f"Claim.PayerID: '{c.payer_id}' ≠ 'E001' → VIOLATION",
                    )))
        return errors

    # Fires when: non-inpatient encounter at non-orthopedic-DRG facility has a DRG activity with Net≠0 (from 2024-08-22)
    def _rule_369(self, model: cs.ClaimSubmission, res) -> list:
        _inpatient = frozenset({3, 4, 5, 6})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2024, 8, 22):
                continue
            enc_types = {e.type for e in c.encounters}
            if enc_types.intersection(_inpatient):
                continue
            for enc in c.encounters:
                is_ortho = res.is_orthopedic_drg_provider(enc.facility_id)
                if not is_ortho:
                    for act in c.activities:
                        if act.type == 9 and act.net != 0:
                            trace = (
                                f"Condition 1 — Non-inpatient encounter type (not 3/4/5/6) ✓",
                                f"Condition 2 — FacilityID: '{enc.facility_id}' → orthopedic DRG provider: {is_ortho} → not orthopedic ✓",
                                f"Condition 3 — DRG Activity (type=9) Net: {act.net} ≠ 0 → VIOLATION",
                            )
                            errors.append(self._err(369, f"Claim '{c.id}', Activity '{act.id or act.code}': DRG Activity.Net must be 0 for non-inpatient encounters", trace=trace))
                    break
        return errors

    # Fires when: Encounter.Type=5 or 6 at an orthopedic DRG pilot facility has an included DRG activity with Net<0
    def _rule_370(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None:
                continue
            enc_types = {e.type for e in c.encounters}
            if not enc_types.intersection({5, 6}):
                continue
            for enc in c.encounters:
                is_ortho = res.is_orthopedic_drg_provider(enc.facility_id)
                if not is_ortho:
                    continue
                for act in c.activities:
                    if act.type != 9:
                        continue
                    included = res.is_included_drg_activity_code(act.code)
                    excluded = res.is_excluded_drg_activity_code(act.code)
                    if not included or excluded:
                        continue
                    if act.net < 0:
                        trace = (
                            f"Condition 1 — Encounter.Type in {{5,6}}, FacilityID '{enc.facility_id}' → orthopedic DRG provider ✓",
                            f"Condition 2 — DRG code: '{act.code}' → included: {included}, excluded: {excluded} ✓",
                            f"Condition 3 — Activity.Net: {act.net} < 0 → VIOLATION",
                        )
                        errors.append(self._err(370, f"Claim '{c.id}', Activity '{act.id or act.code}': DRG Activity.Net must be >= 0 for pilot orthopedic DRG facility", trace=trace))
        return errors

    # Fires when: ReceiverID=D004 and Claim.PayerID is not 'A001' (from 2025-06-01)
    def _rule_374(self, model: cs.ClaimSubmission, res) -> list:
        if model.header.receiver_id != "D004":
            return []
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2025, 6, 1):
                continue
            if c.payer_id != "A001":
                errors.append(self._err(374, f"Claim '{c.id}': PayerID must be 'A001' when ReceiverID is 'D004' (got '{c.payer_id}')",
                    trace=(
                        f"Header.ReceiverID: '{model.header.receiver_id}' = 'D004' ✓",
                        f"Claim.PayerID: '{c.payer_id}' ≠ 'A001' → VIOLATION",
                    )))
        return errors

    # Fires when: Claim.PayerID is one of the forbidden government payer codes {D001-D004} (from 2025-06-01)
    def _rule_381(self, model: cs.ClaimSubmission, res) -> list:
        _forbidden = frozenset({"D001","D002","D003","D004"})
        errors = []
        for c in model.claims:
            fe = _first_enc_start(c)
            if fe is None or fe < datetime(2025, 6, 1):
                continue
            if c.payer_id in _forbidden:
                errors.append(self._err(381, f"Claim '{c.id}': PayerID must not be '{c.payer_id}'",
                    trace=(
                        f"Claim.PayerID: '{c.payer_id}' → in forbidden government payer set {{D001,D002,D003,D004}} → VIOLATION",
                    )))
        return errors

    # Fires when: service code 99-02 or 99-03 is present but no CAHMS DRG activity (type=9, Net>=0) exists
    def _rule_385(self, model: cs.ClaimSubmission, res) -> list:
        _triggers = frozenset({"99-02","99-03"})
        errors = []
        for c in model.claims:
            has_trigger = any(a.type == 8 and a.code.lower() in _triggers and a.net >= 0 for a in c.activities)
            if not has_trigger:
                continue
            has_cahms_drg = any(a.type == 9 and a.net >= 0 and res.is_drg_cahms_code(a.code) for a in c.activities)
            if not has_cahms_drg:
                trace = (
                    f"Condition 1 — Service code '99-02' or '99-03' present with Net≥0 ✓",
                    f"Condition 2 — CAHMS DRG activity (type=9, Net≥0, CAHMS code): {has_cahms_drg} → missing → VIOLATION",
                )
                errors.append(self._err(385, f"Claim '{c.id}': when service code 99-02/99-03 is present, a CAHMS DRG activity (type=9) with Net>=0 must also be present", trace=trace))
        return errors

    # ── Header-level rules (also cover "Header Validation" sheet rows) ─────────

    _CS_ALLOWED_FLAGS = frozenset({
        "PTE_SUBMIT", "PTE_VALIDATE_ONLY", "PTE_RESPONSE",
        "PTE_SHADOW_NOT_FOR_PAYMENT_SUBMIT", "PTE_SHADOW_NOT_FOR_PAYMENT_VALIDATE_ONLY",
        "SHADOW_NOT_FOR_PAYMENT_SUBMIT", "SHADOW_NOT_FOR_PAYMENT_VALIDATE_ONLY",
    })

    # Fires when: Header.DispositionFlag is not in the allowed set for Claim.Submission
    def _rule_30(self, model: cs.ClaimSubmission, res) -> list:
        flag = model.header.disposition_flag
        if flag not in self._CS_ALLOWED_FLAGS:
            return [self._err(30, f"DispositionFlag '{flag}' is not an allowed value for Claim.Submission",
                trace=(
                    f"Header.DispositionFlag: '{flag}'",
                    f"Allowed values: {sorted(self._CS_ALLOWED_FLAGS)}",
                    f"Not in allowed set → VIOLATION",
                ))]
        return []

    # Fires when: SenderID is not a recognised provider, payer, TPA, or SEHA license
    def _rule_54(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        is_provider = res.is_any_provider(sender)
        is_payer = res.is_haad_payer(sender)
        is_tpa = res.is_haad_tpa(sender)
        is_haad = sender == _HAAD_RECEIVER_ID
        if is_provider or is_payer or is_tpa or is_haad:
            return []
        trace = (
            f"Condition — SenderID: '{sender}'",
            f"  → is HAAD provider: {is_provider}",
            f"  → is HAAD payer: {is_payer}",
            f"  → is HAAD TPA: {is_tpa}",
            f"  → equals 'HAAD': {is_haad}",
            f"  → none matched → VIOLATION",
        )
        return [self._err(54, f"Header.SenderID '{sender}' is not a valid provider, payer, TPA, or SEHA license", trace=trace)]

    # Fires when: ReceiverID is not a recognised provider, payer, TPA, or HAAD
    def _rule_57(self, model: cs.ClaimSubmission, res) -> list:
        receiver = model.header.receiver_id
        is_provider = res.is_any_provider(receiver)
        is_payer = res.is_haad_payer(receiver)
        is_tpa = res.is_haad_tpa(receiver)
        is_haad = receiver == _HAAD_RECEIVER_ID
        if is_provider or is_payer or is_tpa or is_haad:
            return []
        trace = (
            f"Condition — ReceiverID: '{receiver}'",
            f"  → is HAAD provider: {is_provider}",
            f"  → is HAAD payer: {is_payer}",
            f"  → is HAAD TPA: {is_tpa}",
            f"  → equals 'HAAD': {is_haad}",
            f"  → none matched → VIOLATION",
        )
        return [self._err(57, f"Header.ReceiverID '{receiver}' is not a valid provider, payer, TPA, or HAAD", trace=trace)]

    # Fires when: sender is a payer/TPA but ReceiverID is not 'HAAD'
    def _rule_59(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        is_payer = res.is_haad_payer(sender)
        is_tpa = res.is_haad_tpa(sender)
        is_insurer = res.is_active_insurer_or_other(sender)
        if not (is_payer or is_tpa or is_insurer):
            return []
        receiver = model.header.receiver_id
        if receiver != _HAAD_RECEIVER_ID:
            trace = (
                f"Condition 1 — SenderID: '{sender}' → is payer: {is_payer}, is TPA: {is_tpa}, is insurer: {is_insurer} → payer/TPA role confirmed ✓",
                f"Condition 2 — ReceiverID: '{receiver}' ≠ 'HAAD' → payer/TPA must send only to HAAD → VIOLATION",
            )
            return [self._err(59, f"Claim.Submission sent by payer/TPA may only have HAAD as ReceiverID (got '{receiver}')", trace=trace)]
        return []

    # Fires when: SenderID equals ReceiverID for encounters from 2020-03-12
    def _rule_295(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        receiver = model.header.receiver_id
        if not sender:
            return []
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                s = _parse_datetime(enc.start)
                if s is not None and s >= datetime(2020, 3, 12) and sender == receiver:
                    errors.append(self._err(295, f"Header.SenderID must not equal Header.ReceiverID '{receiver}'",
                        trace=(
                            f"Encounter.Start: '{enc.start}' ≥ 12/03/2020 ✓",
                            f"SenderID: '{sender}' = ReceiverID: '{receiver}' → must differ → VIOLATION",
                        )))
                    return errors
        return errors

    # Fires when: (INACTIVE) TransactionDate before 2011-03-14, SenderID is SEHA, Claim.PayerID != HAAD
    def _rule_14(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx >= datetime(2011, 3, 14):
            return []
        if model.header.sender_id != "SEHA":
            return []
        errors = []
        for c in model.claims:
            if c.payer_id != "HAAD":
                errors.append(self._inactive_err(14, f"Claim '{c.id}': This is not a valid payerID for senderID SEHA",
                    trace=(
                        f"Claim.ID: '{c.id}', Claim.PayerID: '{c.payer_id}'",
                        f"SenderID is 'SEHA' → PayerID must be 'HAAD' → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Claim.PatientShare is None
    def _rule_22(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if c.patient_share is None:
                errors.append(self._inactive_err(22, f"Claim '{c.id}': Claim PatientShare must have value",
                    trace=(
                        f"Claim.ID: '{c.id}', Claim.PatientShare: None → must be present → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Claim.Net is None
    def _rule_23(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if c.net is None:
                errors.append(self._inactive_err(23, f"Claim '{c.id}': Claim Net must have value",
                    trace=(
                        f"Claim.ID: '{c.id}', Claim.Net: None → must be present → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Claim.Gross is None
    def _rule_24(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if c.gross is None:
                errors.append(self._inactive_err(24, f"Claim '{c.id}': Claim Gross must have value",
                    trace=(
                        f"Claim.ID: '{c.id}', Claim.Gross: None → must be present → VIOLATION",
                    )))
        return errors

    # Fires when: Claim.ID is null or empty
    def _rule_26(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if not c.id or not c.id.strip():
                errors.append(self._err(26, "Claim ID must have value",
                    trace=(
                        f"Claim.ID: '{c.id}' → empty or None → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Encounter.Start <= 2010-06-04, SenderID in HAAD/DHA/MOH providers, FacilityID != SenderID
    def _rule_33(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        if not res.is_any_provider(sender):
            return []
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                s = _parse_datetime(enc.start)
                if s is not None and s <= datetime(2010, 6, 4) and enc.facility_id != sender:
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → is a HAAD provider ✓",
                        f"Condition 2 — Encounter.Start: '{enc.start}' → ≤ 04/06/2010 ✓",
                        f"Condition 3 — FacilityID: '{enc.facility_id}' ≠ SenderID '{sender}' → VIOLATION",
                    )
                    errors.append(self._inactive_err(33, f"Claim '{c.id}': Sender ID '{sender}' is not in the allowed senders list for this e-claim transaction", trace=trace))
        return errors

    # Fires when: (INACTIVE) Encounter.Type is None
    def _rule_35(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.type is None:
                    errors.append(self._inactive_err(35, f"Claim '{c.id}': Encounter Type must have value",
                        trace=(
                            f"Claim.ID: '{c.id}', Encounter.Start: '{enc.start}'",
                            f"Encounter.Type is None → must have a value → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Encounter.Start is None or empty
    def _rule_39(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if not enc.start or not enc.start.strip():
                    errors.append(self._inactive_err(39, f"Claim '{c.id}': Encounter Start must have value",
                        trace=(
                            f"Claim.ID: '{c.id}', Encounter.Type: {enc.type}",
                            f"Encounter.Start: '{enc.start}' → empty or None → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Activity.Observation.Type is not in allowed list
    def _rule_44(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for act in c.activities:
                for obs in act.observations:
                    if obs.type not in _VALID_OBSERVATION_TYPES:
                        errors.append(self._inactive_err(44, f"Claim '{c.id}', Activity '{act.id}': Observation Type must have value",
                            trace=(
                                f"Claim.ID: '{c.id}', Activity.ID: '{act.id}'",
                                f"Observation.Type: '{obs.type}' → not in valid observation types → VIOLATION",
                            )))
        return errors

    # Fires when: (INACTIVE) Observation.Type=LOINC and value is not numeric (or < / > + numeric)
    def _rule_48(self, model: cs.ClaimSubmission, res) -> list:
        import re as _re
        _loinc_val_re = _re.compile(r'^[<>]?\d+(\.\d+)?$')
        errors = []
        for c in model.claims:
            for act in c.activities:
                for obs in act.observations:
                    if obs.type == "LOINC" and obs.value is not None:
                        if not _loinc_val_re.match(obs.value.strip()):
                            errors.append(self._inactive_err(48, f"Claim '{c.id}', Activity '{act.id}': Observation value for LOINC code must be numeric. Symbols '<' and '>' are allowed only on the first position",
                                trace=(
                                    f"Claim.ID: '{c.id}', Activity.ID: '{act.id}', Observation.Type: 'LOINC'",
                                    f"Observation.Value: '{obs.value}' → does not match numeric pattern → VIOLATION",
                                )))
        return errors

    # Fires when: (INACTIVE) Diagnosis.Type is not in valid set
    def _rule_51(self, model: cs.ClaimSubmission, res) -> list:
        _valid_dx = frozenset({"Principal", "Secondary", "Admitting", "ReasonForVisit"})
        errors = []
        for c in model.claims:
            for dx in c.diagnoses:
                if dx.type not in _valid_dx:
                    errors.append(self._inactive_err(51, f"Claim '{c.id}': Diagnosis Type must have a valid value",
                        trace=(
                            f"Claim.ID: '{c.id}', Diagnosis.Code: '{dx.code}', Diagnosis.Type: '{dx.type}'",
                            f"Valid types: {sorted(_valid_dx)}",
                            f"Type not in valid set → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Diagnosis.Code not in ICD9/ICD10 registry
    def _rule_52(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for dx in c.diagnoses:
                icd9_ok = res.is_valid_icd9_code(dx.code)
                icd10_ok = res.is_valid_icd10_code(dx.code)
                if not icd9_ok and not icd10_ok:
                    trace = (
                        f"Condition — Diagnosis.Code: '{dx.code}'",
                        f"  → ICD9 lookup: {icd9_ok}",
                        f"  → ICD10 lookup: {icd10_ok}",
                        f"  → neither found → VIOLATION",
                        f"Note: codes are case-sensitive. Verify exact casing and IsActive flag.",
                    )
                    errors.append(self._inactive_err(52, f"Claim '{c.id}': Diagnosis Code field contains invalid ICD9/ICD10 Code (note that codes are case sensitive)", trace=trace))
        return errors

    # Fires when: SenderID is not null and any Activity.Code is null/empty/whitespace
    def _rule_63(self, model: cs.ClaimSubmission, res) -> list:
        if not model.header.sender_id:
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                if not act.code or not act.code.strip():
                    errors.append(self._err(63, f"Claim '{c.id}', Activity '{act.id}': Activity Code may not be empty because it is a mandatory field; validation failed",
                        trace=(
                            f"Claim.ID: '{c.id}', Activity.ID: '{act.id}'",
                            f"Activity.Code: '{act.code}' → empty or whitespace → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Activity.Start >= 2014-09-01, sender not in exclusion list, Activity.Code not in ICD9 registry
    def _rule_64(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        in_excl = res.in_exclusion_list_1(sender)
        if in_excl:
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is None:
                    continue
                s_str = s.strftime("%d/%m/%Y")
                if s < datetime(2014, 9, 1):
                    continue
                icd9_ok = res.is_valid_icd9_code(act.code)
                if not icd9_ok:
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → not in exclusion list → rule applies",
                        f"Condition 2 — Activity.Start: '{act.start}' → parsed as {s_str} → ≥ 2014-09-01 ✓",
                        f"Condition 3 — ICD9 lookup: code = '{act.code}' → NOT FOUND in HIB_MDM.ICD09 (or IsActive ≠ 1) → VIOLATION",
                        f"Note: codes are case-sensitive. Verify exact casing and IsActive flag in the DB.",
                    )
                    errors.append(self._inactive_err(64,
                        f"Claim '{c.id}', Activity '{act.id}': Activity Code field contains invalid ICD9 Code. Note that codes are case sensitive",
                        trace=trace))
        return errors

    # Fires when: (INACTIVE) Activity.Net is None
    def _rule_76(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.net is None:
                    errors.append(self._inactive_err(76, f"Claim '{c.id}', Activity '{act.id}': Activity Net Can Not Be Null",
                        trace=(
                            f"Claim.ID: '{c.id}', Activity.ID: '{act.id}'",
                            f"Activity.Net is None → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2010-10-01 and Observation.Code not in tooth registry
    def _rule_89(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        errors = []
        for c in model.claims:
            for act in c.activities:
                for obs in act.observations:
                    if obs.type == "Universal Dental" and not res.is_valid_tooth_code(obs.code):
                        trace = (
                            f"Condition 1 — Observation.Type: 'Universal Dental' ✓",
                            f"Condition 2 — Tooth code lookup: '{obs.code}' → NOT a valid tooth number → VIOLATION",
                            f"Note: tooth codes are case-sensitive.",
                        )
                        errors.append(self._inactive_err(89, f"Claim '{c.id}', Activity '{act.id}': Observation code is not a valid code (note that codes are case sensitive)", trace=trace))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2010-10-01, ProviderID not null, no TKBK denial,
    #             min Activity.Start >= 2017-09-23, Claim.ID+ProviderID combo repeated in transaction
    def _rule_94(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        seen = set()
        errors = []
        for c in model.claims:
            if not c.provider_id:
                continue
            min_start = min((_parse_datetime(a.start) for a in c.activities if a.start), default=None)
            if min_start is None or min_start < datetime(2017, 9, 23):
                continue
            if any(getattr(a, 'denial_code', None) and getattr(a, 'denial_code', '').startswith("TKBK") for a in c.activities):
                continue
            key = (c.id, c.provider_id)
            if key in seen:
                errors.append(self._inactive_err(94, f"Claim '{c.id}': Combination of Claim.ID and Claim.ProviderID is reported more than once in your transaction. Claim.ID in combination with Claim.ProviderID must be unique within a transaction file",
                    trace=(
                        f"Claim.ID: '{c.id}', Claim.ProviderID: '{c.provider_id}'",
                        f"This (ClaimID, ProviderID) pair already seen earlier in this transaction → VIOLATION",
                    )))
            seen.add(key)
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2010-06-07, Activity.Start >= 2010-10-01, Resubmission.Type=legacy, Activity.Type != 5
    def _rule_97(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 6, 7):
            return []
        errors = []
        for c in model.claims:
            if not c.resubmission or c.resubmission.type != "legacy":
                continue
            for act in c.activities:
                s = _parse_datetime(act.start)
                if s is not None and s >= datetime(2010, 10, 1) and act.type != 5:
                    errors.append(self._inactive_err(97, f"Claim '{c.id}', Activity '{act.id}': Activity Type should be 5 if Resubmission Type is equal to Legacy",
                        trace=(
                            f"Claim.ID: '{c.id}', Resubmission.Type: 'legacy'",
                            f"Activity.ID: '{act.id}', Activity.Type: {act.type} → must be 5 for legacy resubmission → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Activity.Type=3 and Activity.Code contains '-'
    def _rule_113(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for act in c.activities:
                if act.type == 3 and '-' in act.code:
                    errors.append(self._inactive_err(113, f"Claim '{c.id}', Activity '{act.id}': Activity Code field must not contain modifier (Activity Type is 3 - CPT code). Note that codes are case sensitive",
                        trace=(
                            f"Claim.ID: '{c.id}', Activity.ID: '{act.id}', Activity.Type: 3 (CPT)",
                            f"Activity.Code: '{act.code}' → contains '-' modifier → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2011-06-15, Encounter.Type not in (3,4), Activity.Type=9
    def _rule_138(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            enc_types = {enc.type for enc in c.encounters}
            if enc_types & {3, 4}:
                continue
            for act in c.activities:
                if act.type == 9:
                    errors.append(self._inactive_err(138, f"Claim '{c.id}', Activity '{act.id}': Activity.Type = 9 (DRG Code) may be used only for inpatient Encounter.Type = 3 or 4",
                        trace=(
                            f"Claim.ID: '{c.id}', Activity.ID: '{act.id}', Activity.Type: 9 (DRG)",
                            f"Encounter types present: {sorted(enc_types)} → none are inpatient (3 or 4) → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2011-06-15, Activity.Type=9, Activity.Start != Encounter.Start
    def _rule_139(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            enc_start = _first_enc_start(c)
            if enc_start is None:
                continue
            for act in c.activities:
                if act.type != 9:
                    continue
                act_start = _parse_datetime(act.start)
                if act_start is not None and act_start != enc_start:
                    errors.append(self._inactive_err(139, f"Claim '{c.id}', Activity '{act.id}': Activity.Type = 9 (DRG Code) must have Activity.Start equal to Encounter.Start. Your Encounter.Start = {enc_start.strftime('%d/%m/%Y %H:%M')}",
                        trace=(
                            f"Claim.ID: '{c.id}', Activity.ID: '{act.id}', Activity.Type: 9 (DRG)",
                            f"Activity.Start: '{act.start}' → {act_start}",
                            f"Encounter.Start: {enc_start} → must be equal → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2011-06-15, Encounter.Type in outpatient types,
    #             Activity.Start > Encounter.Start + 24h
    def _rule_155(self, model: cs.ClaimSubmission, res) -> list:
        _outpatient_types = frozenset({1, 2, 5, 6, 7, 8, 9, 12, 13, 15, 41, 42})
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.type not in _outpatient_types:
                    continue
                enc_start = _parse_datetime(enc.start)
                if enc_start is None:
                    continue
                for act in c.activities:
                    act_start = _parse_datetime(act.start)
                    if act_start is not None and act_start > enc_start + timedelta(hours=24):
                        errors.append(self._inactive_err(155, f"Claim '{c.id}', Activity '{act.id}': Must be within 24 hours from Encounter start if Encounter Type is equal to Outpatient. Your Encounter Start is {enc.start}",
                            trace=(
                                f"Claim.ID: '{c.id}', Activity.ID: '{act.id}', Encounter.Type: {enc.type} (outpatient)",
                                f"Encounter.Start: '{enc.start}' → {enc_start}",
                                f"Activity.Start: '{act.start}' → {act_start}",
                                f"Activity.Start - Encounter.Start = {(act_start - enc_start).total_seconds()/3600:.1f}h > 24h → VIOLATION",
                            )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2014-12-01, Encounter.Start >= 2014-12-01, DxInfo.Type not POA or Year of Onset
    def _rule_239(self, model: cs.ClaimSubmission, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 12, 1):
            return []
        errors = []
        for c in model.claims:
            enc_start = _first_enc_start(c)
            if enc_start is None or enc_start < datetime(2014, 12, 1):
                continue
            for dx in c.diagnoses:
                for dxi in dx.dx_info:
                    if dxi.type not in ("POA", "Year of Onset"):
                        errors.append(self._inactive_err(239, f"Claim '{c.id}': DxInfo.Type must be 'POA' or 'Year of Onset' for Claim Submission Transaction",
                            trace=(
                                f"Claim.ID: '{c.id}', Diagnosis.Code: '{dx.code}', DxInfo.Type: '{dxi.type}'",
                                f"Valid types: {{'POA', 'Year of Onset'}}",
                                f"Type not in valid set → VIOLATION",
                            )))
        return errors

    # Fires when: DateOrdered is present but no activity in this or previous claims has Consultation code + DateOrdered + OrderingClinician
    def _rule_289(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            if not any(a.date_ordered for a in c.activities):
                continue
            has_consult = any(
                a.date_ordered and a.ordering_clinician and res.is_valid_cpt_code(a.code)
                for a in c.activities
            )
            if has_consult:
                continue
            member_id = c.member_id
            sender_id = model.header.sender_id
            if member_id and sender_id and res.claim_has_consultation_with_date_ordered(member_id, sender_id):
                continue
            errors.append(self._err(289, f"Claim '{c.id}': the combination of Activity.DateOrdered, Activity.OrderingClinician must be present in at least one activity with Activity.Code=Consultation in the same or a previously submitted Claim with the same Claim.MemberID",
                trace=(
                    f"Claim.ID: '{c.id}', Claim.MemberID: '{c.member_id}'",
                    f"Activities with DateOrdered: {[a.id for a in c.activities if a.date_ordered]}",
                    f"No activity has (Consultation code + DateOrdered + OrderingClinician) in this or prior claims → VIOLATION",
                )))
        return errors

    # Fires when: Encounter.Start >= 2016-01-01, MemberID not null, not SEHA sender, self-pay payer, member not registered for provider
    def _rule_301(self, model: cs.ClaimSubmission, res) -> list:
        sender = model.header.sender_id
        errors = []
        for c in model.claims:
            if c.payer_id not in _SELF_PAY_PAYER_IDS:
                continue
            if sender == "SEHA":
                continue
            if not c.member_id:
                continue
            enc_start = _first_enc_start(c)
            if enc_start is None or enc_start < datetime(2016, 1, 1):
                continue
            registered = res.is_member_registered_for_payer(c.member_id, c.provider_id)
            if not registered:
                trace = (
                    f"Condition 1 — Claim.PayerID: '{c.payer_id}' → self-pay payer ✓",
                    f"Condition 2 — SenderID: '{sender}' → not 'SEHA' → rule applies ✓",
                    f"Condition 3 — Encounter.Start: '{enc_start.strftime('%d/%m/%Y')}' → ≥ 2016-01-01 ✓",
                    f"Condition 4 — MemberID '{c.member_id}' + ProviderID '{c.provider_id}' → not found in Person.Register → VIOLATION",
                )
                errors.append(self._err(301, f"Member ID '{c.member_id}' does not belong to provider '{c.provider_id}'. If you are sure the member ID is correctly spelled, please upload member using Person.Register transaction", trace=trace))
        return errors

    # Fires when: (INACTIVE) Encounter.Start >= 2022-05-01, Activity.Code is 80-01 or 80-02, Quantity not in [0, 100]
    def _rule_315(self, model: cs.ClaimSubmission, res) -> list:
        _codes = frozenset({"80-01", "80-02"})
        errors = []
        for c in model.claims:
            enc_start = _first_enc_start(c)
            if enc_start is None or enc_start < datetime(2022, 5, 1):
                continue
            for act in c.activities:
                if act.code not in _codes:
                    continue
                if act.quantity is None or not (0 <= act.quantity <= 100):
                    errors.append(self._inactive_err(315, f"Claim '{c.id}', Activity '{act.id}': Activity Quantity must be between 0 and 100 If Service Codes 80-01 or 80-02 are present",
                        trace=(
                            f"Claim.ID: '{c.id}', Activity.ID: '{act.id}', Activity.Code: '{act.code}'",
                            f"Activity.Quantity: {act.quantity} → must be 0–100 for codes 80-01/80-02 → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Encounter.Start >= 2030-01-05, non-self-pay payer, not IPC provider, EID not in Person.Register
    def _rule_341(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            enc_start = _first_enc_start(c)
            if enc_start is None or enc_start < datetime(2030, 1, 5):
                continue
            if c.payer_id in _SELF_PAY_PAYER_IDS or c.payer_id.startswith("@"):
                continue
            if res.is_ipc_provider(c.provider_id):
                continue
            eid = c.emirates_id_number
            if eid and eid not in _DUMMY_EMIRATES_IDS:
                if not res.person_register_eid_exists(eid):
                    errors.append(self._inactive_err(341, f"Claim '{c.id}': Combination of Member ID and Emirates ID or Unified Number must be present in at least one Person.Register transaction",
                        trace=(
                            f"Claim.ID: '{c.id}', Claim.MemberID: '{c.member_id}'",
                            f"Claim.EmiratesIDNumber: '{eid}'",
                            f"EID not found in Person.Register → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Encounter.Start >= 2035-06-01, not internal-complaint, ReceiverID in D001..D004,
    #             Activity.Type=5, Net>0, Markup>0, unit price differs from markup beyond 45% tolerance
    def _rule_377(self, model: cs.ClaimSubmission, res) -> list:
        _upp_receivers = frozenset({"D001", "D002", "D003", "D004"})
        _allowed_pct = 45.0
        if model.header.receiver_id not in _upp_receivers:
            return []
        errors = []
        for c in model.claims:
            enc_start = _first_enc_start(c)
            if enc_start is None or enc_start < datetime(2035, 6, 1):
                continue
            if c.resubmission and c.resubmission.type == "internal complaint":
                continue
            for act in c.activities:
                if act.type != 5 or act.net <= 0 or not act.quantity:
                    continue
                pkg_markup_str = res.get_pkg_markup(act.code)
                if not pkg_markup_str:
                    continue
                try:
                    pkg_markup = float(pkg_markup_str)
                except (ValueError, TypeError):
                    continue
                if pkg_markup <= 0:
                    continue
                unit_net = act.net / act.quantity
                tolerance = (pkg_markup * _allowed_pct) / 100.0
                if abs(unit_net - pkg_markup) > tolerance:
                    errors.append(self._inactive_err(377, f"Claim '{c.id}', Activity '{act.id}': Claim.PayerID must be D001, D002, D003, D004, (or A001 temporarily), if transaction includes activities with UPP markup prices",
                        trace=(
                            f"Claim.ID: '{c.id}', Activity.ID: '{act.id}', Activity.Code: '{act.code}'",
                            f"Activity.Net: {act.net}, Activity.Quantity: {act.quantity}, UnitNet: {unit_net:.4f}",
                            f"PackageMarkup: {pkg_markup:.4f}, 45% tolerance: {tolerance:.4f}",
                            f"|UnitNet - PackageMarkup| = {abs(unit_net - pkg_markup):.4f} > {tolerance:.4f} → VIOLATION",
                        )))
        return errors

    # Fires when: earliest Encounter.Start < 2025-06-01 and ReceiverID = E001
    def _rule_378(self, model: cs.ClaimSubmission, res) -> list:
        if model.header.receiver_id != "E001":
            return []
        for c in model.claims:
            enc_start = _first_enc_start(c)
            if enc_start is not None and enc_start < datetime(2025, 6, 1):
                return [self._err(378, "Header.ReceiverID cannot be E001",
                    trace=(
                        f"Header.ReceiverID: 'E001'",
                        f"Claim.ID: '{c.id}', first Encounter.Start: {enc_start.date()} < 2025-06-01",
                        f"ReceiverID E001 not allowed for claims before 2025-06-01 → VIOLATION",
                    ))]
        return []

    # Fires when: Encounter.Start >= 2025-06-01, not internal-complaint, Activity.Type=5, Net>0, Markup>0,
    #             unit price >= PriceToPublic or >= Markup (quantity inconsistency)
    def _rule_380(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            enc_start = _first_enc_start(c)
            if enc_start is None or enc_start < datetime(2025, 6, 1):
                continue
            if c.resubmission and c.resubmission.type == "internal complaint":
                continue
            for act in c.activities:
                if act.type != 5 or act.net is None or act.net <= 0 or not act.quantity:
                    continue
                pkg_markup_str = res.get_pkg_markup(act.code)
                if not pkg_markup_str:
                    continue
                try:
                    pkg_markup = float(pkg_markup_str)
                except (ValueError, TypeError):
                    continue
                if pkg_markup <= 0:
                    continue
                unit_net = act.net / act.quantity
                pkg_pub_str = res.get_pkg_price_to_public(act.code)
                try:
                    pkg_pub = float(pkg_pub_str) if pkg_pub_str else None
                except (ValueError, TypeError):
                    pkg_pub = None
                if (pkg_pub is not None and unit_net >= pkg_pub) or unit_net >= pkg_markup:
                    errors.append(self._err(380, f"Claim '{c.id}', Activity '{act.id}': Please check if Activity.Quantity is consistent with Activity.Net and 'Package Price to Public' or 'Package Markup' (UPP Markup Price > 0)",
                        trace=(
                            f"Claim.ID: '{c.id}', Activity.ID: '{act.id}', Activity.Code: '{act.code}'",
                            f"Activity.Net: {act.net}, Activity.Quantity: {act.quantity}, UnitNet: {unit_net:.4f}",
                            f"PackageMarkup: {pkg_markup:.4f}" + (f", PriceToPublic: {pkg_pub:.4f}" if pkg_pub is not None else ""),
                            f"UnitNet {unit_net:.4f} ≥ {'PriceToPublic' if pkg_pub is not None and unit_net >= pkg_pub else 'PackageMarkup'} → quantity inconsistency → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Encounter.EndType=2, claim lacks (ServiceCode 99-01 Net>=0) AND (DRG activity Net=0)
    def _rule_384(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.end_type != 2:
                    continue
                has_service_99_01 = any(
                    a.type == 8 and a.code == "99-01" and a.net >= 0
                    for a in c.activities
                )
                has_drg_zero_net = any(
                    a.type == 9 and a.net == 0 and (
                        res.is_included_drg_activity_code(a.code) or
                        res.is_drg_cahms_code(a.code) or
                        res.is_valid_drg_code(a.code)
                    )
                    for a in c.activities
                )
                if not (has_service_99_01 and has_drg_zero_net):
                    drg_acts = [a for a in c.activities if a.type == 9]
                    drg_info = (f"{len(drg_acts)} DRG activity(ies) found — none with Net=0 and valid DRG code"
                                if drg_acts else "no DRG activities found")
                    trace = (
                        f"Condition 1 — Encounter.EndType: {enc.end_type} = 2 (Discharged against advice) ✓",
                        f"Condition 2 — Service code 99-01 (Type=8) with Net≥0 present: {'YES ✓' if has_service_99_01 else 'NO → missing'}",
                        f"Condition 3 — DRG activity (Type=9) with Net=0 and valid DRG code: {'YES ✓' if has_drg_zero_net else 'NO → ' + drg_info}",
                        f"Both conditions 2 and 3 must be satisfied → VIOLATION",
                    )
                    errors.append(self._inactive_err(384, f"Claim '{c.id}': If Encounter.EndType = 2 (Discharged against advice) then a) An Activity with Activity.Type = 8 (Service Code) and Activity.Code = 99-01 should be present with Activity.Net >= 0 and b) An Activity with Activity.Type = 9 (any DRG) must be present with Activity.Net=0", trace=trace))
        return errors

    # Fires when: (INACTIVE) Encounter.Type=2 or 3, not all activities Net=0, or excluded codes present
    def _rule_386(self, model: cs.ClaimSubmission, res) -> list:
        _excl = frozenset({"98", "99", "99-02", "99-03"})
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.type not in (2, 3):
                    continue
                all_net_zero = all(a.net == 0 for a in c.activities)
                has_excl = any(a.code.strip() in _excl for a in c.activities)
                if not (all_net_zero and not has_excl):
                    non_zero = [a.id for a in c.activities if a.net != 0]
                    excl_found = [a.code.strip() for a in c.activities if a.code.strip() in _excl]
                    errors.append(self._inactive_err(386, f"Claim '{c.id}': If Encounter.EndType = 2 or 3 then a) Activity.Net must be 0 for all Activities including DRG and b) Activity.Code: 98, 99, 99-02, 99-03 must not be present",
                        trace=(
                            f"Claim.ID: '{c.id}', Encounter.EndType: {enc.end_type}",
                            *(
                                (f"Activities with non-zero Net: {non_zero} → all must be 0 → VIOLATION",)
                                if non_zero else ()
                            ),
                            *(
                                (f"Excluded codes present: {excl_found} → must not appear → VIOLATION",)
                                if excl_found else ()
                            ),
                        )))
        return errors

    # Fires when: Encounter.EndType=3 and any Activity.Code = '99-01'
    def _rule_387(self, model: cs.ClaimSubmission, res) -> list:
        errors = []
        for c in model.claims:
            for enc in c.encounters:
                if enc.end_type != 3:
                    continue
                if any(a.code == "99-01" for a in c.activities):
                    act_99_01 = [a.id for a in c.activities if a.code == "99-01"]
                    errors.append(self._err(387, f"Claim '{c.id}': If Encounter.EndType = 3 then Activity.Code 99-01 must not be present",
                        trace=(
                            f"Claim.ID: '{c.id}', Encounter.EndType: {enc.end_type} = 3 (Against medical advice)",
                            f"Activity.Code '99-01' found in activities: {act_99_01} → must not be present → VIOLATION",
                        )))
        return errors


# ── PersonRegister rules ───────────────────────────────────────────────────────

class _PersonRegisterValidator(_BaseValidator):
    TRANSACTION = "Person.Register"

    _RULE_DESCRIPTIONS = {
        "7":   "(INACTIVE) Person.City is empty",
        "9":   "Header.RecordCount does not match the actual number of Person elements",
        "19":  "Person.EmiratesIDNumber is empty or fails Luhn/format check (non-dummy values)",
        "30":  "Header.DispositionFlag is not PTE_SUBMIT, PTE_VALIDATE_ONLY, or PTE_RESPONSE",
        "53":  "Person.Nationality is not a valid nationality code",
        "61":  "Header.TransactionDate does not match today's date",
        "86":  "Contract.ExpiryDate is before Contract.StartDate (from 2010-10-01)",
        "99":  "Member.Relation='Principal' and Member.RelationTo does not equal Member.ID (from 2011-04-18)",
        "100": "(INACTIVE) Contract.RenewalDate > TransactionDate (date range Apr 18 – May 31, 2011)",
        "101": "Contract.RenewalDate is before Contract.StartDate (from 2011-04-18)",
        "102": "Contract.StartDate is before 01/01/2005 (from 2011-04-18)",
        "103": "Contract.ExpiryDate is before Contract.RenewalDate (from 2011-04-18)",
        "104": "BirthDate or any Contract date is before 01/01/1900 (from 2010-10-01)",
        "105": "Header.TransactionDate is before 01/01/1900 (from 2010-10-01)",
        "116": "Person.BirthDate is after Header.TransactionDate (from 2011-04-18)",
        "121": "sender is a payer and Person.Gender=9 (unknown) (from 2011-04-18)",
        "122": "Member.Relation is not Principal but all RelationTo fields are empty (from 2011-04-18)",
        "132": "non-Thiqa Contract.GrossPremium < 600 AED for members older than 1 year (from 2011-04-05)",
        "136": "non-Principal Member.RelationTo is not a known Principal Member.ID in file or DB",
        "153": "Contract.PackageName is not a valid benefit package (from 2010-03-25, non-Thiqa)",
        "195": "sender is a payer but a Person has no Member element",
        "199": "Member.ID is duplicated within the same transaction (from 2011-06-15)",
        "208": "Contract.PayerID is present but not a valid active insurer or other license (from 2014-01-01)",
        "209": "Contract.TPAID is present but not a valid HAAD TPA license (from 2014-01-01)",
        "210": "Contract.TPAID is present but Contract.PayerID is empty (from 2014-01-01)",
        "211": "sender is a payer and Member.Relation is empty (from 2014-06-01)",
        "212": "sender is a payer and a Person's Member has no Contract elements (from 2014-06-01)",
        "246": "sender is a payer and Contract.PayerID does not equal Header.SenderID (from 2014-12-01)",
        "271": "adult member with new/restarted/renewed contract has no UnifiedNumber (payer only)",
        "272": "Person.UnifiedNumber does not match the MOI record (dormant until MOI integration is live)",
        "273": "Person.FirstNameEn does not match the MOI English full name (dormant until MOI integration)",
        "274": "Person.MiddleNameEn does not match the MOI English full name (dormant until MOI integration)",
        "275": "Person.LastNameEn does not match the MOI English full name (dormant until MOI integration)",
        "276": "Person.FirstNameAr does not match the MOI Arabic full name (dormant until MOI integration)",
        "277": "Person.MiddleNameAr does not match the MOI Arabic full name (dormant until MOI integration)",
        "278": "(INACTIVE) MOI FullNameAr does not contain Person.LastNameAr for new/active members",
        "279": "Person.BirthDate year does not match the MOI birth year record (dormant until MOI integration)",
        "280": "Person.Nationality does not match the MOI nationality code (dormant until MOI integration)",
        "281": "Contract.VATPercent is present but outside 0–100",
        "284": "sender is not an insurer/other and Person.CountryOfResidence is missing or invalid",
        "285": "CountryOfResidence='United Arab Emirates' but EmirateOfResidence is missing or not 1-7",
        "310": "Person.EmiratesIDNumber does not match the MOI Emirates ID record (dormant until MOI integration)",
        "328": "Contract.Status is not in the allowed set of values (sender is payer, from 2022-10-13)",
        "329": "Contract.Status='New' and Member.ID was already registered by this sender (from 2022-10-13)",
        "330": "Contract.Status is New/Restarted/Gap Enrollment and StartDate ≠ RenewalDate (from 2022-10-13)",
        "331": "dummy EmiratesID is used with certain statuses (Restarted, Updated EID, Cancelled, etc.) from 2023-01-05",
        "332": "Renewed/Corrected/Updated EID/Cancelled contract has a StartDate different from the previous record (from 2022-10-13)",
        "333": "Renewed/Corrected Date contract has a RenewalDate before the previous record's ExpiryDate (from 2022-10-13)",
        "334": "Contract.Status='Corrected' but no previous record exists for this Member (from 2022-10-13)",
        "335": "Contract.Status='Updated EmiratesIDNumber' but EmiratesIDNumber is not a valid format (from 2022-10-13)",
        "336": "Contract.Status='Cancelled' but the Member.ID has no previous Person.Register record (from 2022-10-13)",
        "337": "(INACTIVE) MOI PassportNumber does not match Person.PassportNumber for new/active members",
        "338": "Person.SponsorNameEn does not match the MOI sponsor English name (dormant until MOI integration)",
        "339": "Person.SponsorNameAr does not match the MOI sponsor Arabic name (dormant until MOI integration)",
        "340": "Person.SponsorNumber does not match the MOI sponsor number (dormant until MOI integration)",
        "347": "Principal Member.RelationToEmiratesIDNumber ≠ Person.EmiratesIDNumber (sender is payer, from 2023-03-22)",
        "348": "Principal Member.RelationToUnifiedNumber ≠ Person.UnifiedNumber (sender is payer, from 2023-03-22)",
        "349": "non-Principal Member.RelationToEmiratesIDNumber is a dummy ID value (sender is payer, from 2023-03-22)",
        "350": "(INACTIVE) Member.RelationToEmiratesIDNumber exists but no Person.Register record found with that EID",
        "351": "(INACTIVE) Member.RelationToUnifiedNumber exists but no Person.Register record found with that UnifiedNumber",
        "352": "Contract.Status='Gap Enrollment' is sent by a sender other than 'E001' (from 2023-03-28)",
        "353": "Gap Enrollment Contract.ExpiryDate is after the previous record's RenewalDate (from 2023-03-29)",
        "354": "non-dummy EmiratesIDNumber does not start with '784' (from 2023-06-23)",
        "355": "SenderID is A001 or E001 and Member.ID starts with '0' (from 2023-06-23)",
        "361": "CountryOfResidence is not UAE but EmirateOfResidence is populated (from 2024-01-03)",
        "400": "(INACTIVE) Contract.Status='Recon' but SenderID is not 'A001' or 'E001'",
    }

    _PR_ALLOWED_FLAGS = frozenset({"PTE_SUBMIT", "PTE_VALIDATE_ONLY", "PTE_RESPONSE"})
    _VALID_EMIRATE_OF_RESIDENCE = frozenset({"1","2","3","4","5","6","7"})
    _NEW_CONTRACT_STATUSES = frozenset({"New","Restarted","Renewed"})
    _VALID_CONTRACT_STATUSES = frozenset({
        "New","Restarted","Renewed","Corrected","Corrected Date","Updated EmiratesIDNumber",
        "Cancelled","Gap Enrollment","Recon","Newborn","WarZone","Visitor",
        "Newborn-correction","Newborn-cancellation",
    })
    _EXEMPT_PAYER_SENDERS = frozenset({"A001","D001","E001"})

    def _rules(self):
        return [
            self._rule_7,   self._rule_9,   self._rule_19,  self._rule_30,  self._rule_53,
            self._rule_61,  self._rule_86,  self._rule_99,  self._rule_100, self._rule_101,
            self._rule_102, self._rule_103, self._rule_104, self._rule_105, self._rule_116,
            self._rule_121, self._rule_122, self._rule_132, self._rule_136, self._rule_153,
            self._rule_195, self._rule_199, self._rule_208, self._rule_209, self._rule_210,
            self._rule_211, self._rule_212, self._rule_246, self._rule_271, self._rule_272,
            self._rule_273, self._rule_274, self._rule_275, self._rule_276, self._rule_277,
            self._rule_278, self._rule_279, self._rule_280, self._rule_281, self._rule_284,
            self._rule_285, self._rule_310, self._rule_328, self._rule_329, self._rule_330,
            self._rule_331, self._rule_332, self._rule_333, self._rule_334, self._rule_335,
            self._rule_336, self._rule_337, self._rule_338, self._rule_339, self._rule_340,
            self._rule_347, self._rule_348, self._rule_349, self._rule_350, self._rule_351,
            self._rule_352, self._rule_353, self._rule_354, self._rule_355, self._rule_361,
            self._rule_400,
        ]

    # Fires when: Header.RecordCount does not match the actual number of Person elements
    def _rule_9(self, model: pr.PersonRegister, res) -> list:
        actual = len(model.persons)
        if model.header.record_count != actual:
            return [self._err(9, f"Header.RecordCount is {model.header.record_count} but {actual} Person element(s) found",
                trace=(
                    f"Header.RecordCount: {model.header.record_count}",
                    f"Actual Person elements in file: {actual}",
                    f"Count mismatch → VIOLATION",
                ))]
        return []

    # Fires when: Person.EmiratesIDNumber is empty or fails Luhn/format check (non-dummy values)
    def _rule_19(self, model: pr.PersonRegister, res) -> list:
        errors = []
        for p in model.persons:
            eid = p.emirates_id_number
            if not eid or not eid.strip():
                errors.append(self._err(19, "Person.EmiratesIDNumber may not be empty",
                    trace=("Person.EmiratesIDNumber: empty/null → VIOLATION",)))
            elif eid not in _DUMMY_EMIRATES_IDS and not _is_valid_emirates_id(eid):
                errors.append(self._err(19, f"Person.EmiratesIDNumber '{eid}' is not a valid Emirates ID",
                    trace=(
                        f"EmiratesIDNumber: '{eid}' → not in dummy set ✓",
                        f"Format/Luhn check: FAILED → VIOLATION",
                        f"Note: expected format 784-YYYY-XXXXXXX-N (passes Luhn algorithm).",
                    )))
        return errors

    # Fires when: Header.DispositionFlag is not PTE_SUBMIT, PTE_VALIDATE_ONLY, or PTE_RESPONSE
    def _rule_30(self, model: pr.PersonRegister, res) -> list:
        flag = model.header.disposition_flag
        if flag not in self._PR_ALLOWED_FLAGS:
            return [self._err(30, f"DispositionFlag must be PTE_SUBMIT, PTE_VALIDATE_ONLY, or PTE_RESPONSE (got '{flag}')",
                trace=(
                    f"Header.DispositionFlag: '{flag}'",
                    f"Allowed values: {sorted(self._PR_ALLOWED_FLAGS)}",
                    f"Not in allowed set → VIOLATION",
                ))]
        return []

    # Fires when: Person.Nationality is not a valid nationality code
    def _rule_53(self, model: pr.PersonRegister, res) -> list:
        errors = []
        for p in model.persons:
            nat_ok = res.is_valid_nationality(p.nationality)
            if not nat_ok:
                trace = (
                    f"Nationality lookup: '{p.nationality}' → NOT FOUND in nationality reference table → VIOLATION",
                    f"Note: nationality codes are case-sensitive. Verify exact value in the reference data.",
                )
                errors.append(self._err(53, f"Person '{p.emirates_id_number}': Nationality '{p.nationality}' is not valid", trace=trace))
        return errors

    # Fires when: Header.TransactionDate does not match today's date
    def _rule_61(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None:
            return []
        today = datetime.now()
        if tx.date() != today.date():
            return [self._err(61, f"Header.TransactionDate '{model.header.transaction_date}' must match today's date",
                trace=(
                    f"Header.TransactionDate: '{model.header.transaction_date}' → parsed as {tx.strftime('%d/%m/%Y')}",
                    f"Today's date: {today.strftime('%d/%m/%Y')}",
                    f"Dates do not match → VIOLATION",
                ))]
        return []

    # Fires when: Contract.ExpiryDate is before Contract.StartDate (from 2010-10-01)
    def _rule_86(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                expiry = _parse_date(c.expiry_date)
                start  = _parse_date(c.start_date)
                if expiry is not None and start is not None and expiry < start:
                    errors.append(self._err(86, f"Person '{p.emirates_id_number}': Contract.ExpiryDate must be >= StartDate",
                        trace=(
                            f"Contract.StartDate: '{c.start_date}' → {start.strftime('%d/%m/%Y')}",
                            f"Contract.ExpiryDate: '{c.expiry_date}' → {expiry.strftime('%d/%m/%Y')}",
                            f"ExpiryDate < StartDate → VIOLATION",
                        )))
        return errors

    # Fires when: Member.Relation='Principal' and Member.RelationTo does not equal Member.ID (from 2011-04-18)
    def _rule_99(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 4, 18):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            m = p.member
            if m.relation == "Principal" and m.relation_to and m.relation_to != m.id:
                errors.append(self._err(99, f"Person '{p.emirates_id_number}': Member.RelationTo must equal Member.ID when Relation is 'Principal'",
                    trace=(
                        f"Member.Relation: 'Principal' ✓",
                        f"Member.ID: '{m.id}'",
                        f"Member.RelationTo: '{m.relation_to}' ≠ Member.ID → VIOLATION",
                    )))
        return errors

    # Fires when: Contract.RenewalDate is before Contract.StartDate (from 2011-04-18)
    def _rule_101(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 4, 18):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                renewal = _parse_date(c.renewal_date)
                start   = _parse_date(c.start_date)
                if renewal is not None and start is not None and renewal < start:
                    errors.append(self._err(101, f"Person '{p.emirates_id_number}': Contract.RenewalDate must be >= StartDate",
                        trace=(
                            f"Contract.StartDate: '{c.start_date}' → {start.strftime('%d/%m/%Y')}",
                            f"Contract.RenewalDate: '{c.renewal_date}' → {renewal.strftime('%d/%m/%Y')}",
                            f"RenewalDate < StartDate → VIOLATION",
                        )))
        return errors

    # Fires when: Contract.StartDate is before 01/01/2005 (from 2011-04-18)
    def _rule_102(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 4, 18):
            return []
        _min = datetime(2005, 1, 1)
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                start = _parse_date(c.start_date)
                if start is not None and start < _min:
                    errors.append(self._err(102, f"Person '{p.emirates_id_number}': Contract.StartDate must be >= 01/01/2005",
                        trace=(
                            f"Contract.StartDate: '{c.start_date}' → {start.strftime('%d/%m/%Y')}",
                            f"Minimum allowed: 01/01/2005",
                            f"StartDate is before minimum → VIOLATION",
                        )))
        return errors

    # Fires when: Contract.ExpiryDate is before Contract.RenewalDate (from 2011-04-18)
    def _rule_103(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 4, 18):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                expiry  = _parse_date(c.expiry_date)
                renewal = _parse_date(c.renewal_date)
                if expiry is not None and renewal is not None and expiry < renewal:
                    errors.append(self._err(103, f"Person '{p.emirates_id_number}': Contract.ExpiryDate must be >= RenewalDate",
                        trace=(
                            f"Contract.RenewalDate: '{c.renewal_date}' → {renewal.strftime('%d/%m/%Y')}",
                            f"Contract.ExpiryDate: '{c.expiry_date}' → {expiry.strftime('%d/%m/%Y')}",
                            f"ExpiryDate < RenewalDate → VIOLATION",
                        )))
        return errors

    # Fires when: BirthDate or any Contract date is before 01/01/1900 (from 2010-10-01)
    def _rule_104(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        _min = datetime(1900, 1, 1)
        errors = []
        for p in model.persons:
            bd = _parse_date(p.birth_date)
            if bd is not None and bd <= _min:
                errors.append(self._err(104, f"Person '{p.emirates_id_number}': BirthDate cannot be before 01/01/1900",
                    trace=(
                        f"Person.BirthDate: '{p.birth_date}' → {bd.strftime('%d/%m/%Y')}",
                        f"Minimum allowed: 01/01/1900",
                        f"BirthDate is before minimum → VIOLATION",
                    )))
            if not p.member:
                continue
            for c in p.member.contracts:
                for field_name, val_str in [("StartDate", c.start_date), ("RenewalDate", c.renewal_date), ("ExpiryDate", c.expiry_date)]:
                    d = _parse_date(val_str)
                    if d is not None and d <= _min:
                        errors.append(self._err(104, f"Person '{p.emirates_id_number}': Contract.{field_name} cannot be before 01/01/1900",
                            trace=(
                                f"Contract.{field_name}: '{val_str}' → {d.strftime('%d/%m/%Y')}",
                                f"Minimum allowed: 01/01/1900",
                                f"{field_name} is before minimum → VIOLATION",
                            )))
        return errors

    # Fires when: Header.TransactionDate is before 01/01/1900 (from 2010-10-01)
    def _rule_105(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        _min = datetime(1900, 1, 1)
        if tx <= _min:
            return [self._err(105, "Header.TransactionDate cannot be before 01/01/1900",
                trace=(
                    f"Header.TransactionDate: '{model.header.transaction_date}' → {tx.strftime('%d/%m/%Y')}",
                    f"Minimum allowed: 01/01/1900",
                    f"TransactionDate is before minimum → VIOLATION",
                ))]
        return []

    # Fires when: Person.BirthDate is after Header.TransactionDate (from 2011-04-18)
    def _rule_116(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 4, 18):
            return []
        errors = []
        for p in model.persons:
            bd = _parse_date(p.birth_date)
            if bd is not None and bd > tx:
                errors.append(self._err(116, f"Person '{p.emirates_id_number}': BirthDate must be before TransactionDate",
                    trace=(
                        f"Person.BirthDate: '{p.birth_date}' → {bd.strftime('%d/%m/%Y')}",
                        f"Header.TransactionDate: '{model.header.transaction_date}' → {tx.strftime('%d/%m/%Y')}",
                        f"BirthDate is after TransactionDate → VIOLATION",
                    )))
        return errors

    # Fires when: sender is a payer and Person.Gender=9 (unknown) (from 2011-04-18)
    def _rule_121(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 4, 18):
            return []
        sender = model.header.sender_id
        is_payer = res.is_active_insurer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if p.gender == 9:
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → active insurer lookup → YES → rule applies ✓",
                    f"Condition 2 — Person '{p.emirates_id_number}' Gender: {p.gender} = 9 (unknown) → VIOLATION",
                )
                errors.append(self._err(121, f"Person '{p.emirates_id_number}': Gender cannot be unknown (9) when sender is a payer", trace=trace))
        return errors

    # Fires when: Member.Relation is not Principal but all RelationTo fields are empty (from 2011-04-18)
    def _rule_122(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 4, 18):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            m = p.member
            if m.relation in (None, "Principal"):
                continue
            has_eid_ref  = bool(m.relation_to_emirates_id_number and m.relation_to_emirates_id_number.strip())
            has_uid_ref  = bool(m.relation_to_unified_number and str(m.relation_to_unified_number).strip())
            has_rel_to   = bool(m.relation_to and m.relation_to.strip())
            if not has_eid_ref and not has_uid_ref and not has_rel_to:
                errors.append(self._err(122, f"Person '{p.emirates_id_number}': Member.RelationTo must have a value when Relation is not Principal",
                    trace=(
                        f"Member.Relation: '{m.relation}' → not Principal ✓",
                        f"Member.RelationTo: '{m.relation_to}' → empty ✓",
                        f"RelationToEmiratesIDNumber: '{m.relation_to_emirates_id_number}' → empty ✓",
                        f"RelationToUnifiedNumber: '{m.relation_to_unified_number}' → empty ✓",
                        f"All RelationTo fields empty → VIOLATION",
                    )))
        return errors

    # Fires when: non-Thiqa Contract.GrossPremium < 600 AED for members older than 1 year with RenewalDate > 1 yr after birth (from 2011-04-05)
    def _rule_132(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 4, 5):
            return []
        errors = []
        for p in model.persons:
            bd = _parse_date(p.birth_date)
            if not p.member or bd is None:
                continue
            for c in p.member.contracts:
                if c.package_name in _THIQA_PACKAGES:
                    continue
                renewal = _parse_date(c.renewal_date)
                if renewal is None:
                    continue
                one_year_after_birth = datetime(bd.year + 1, bd.month, bd.day)
                if renewal <= one_year_after_birth:
                    continue
                if c.gross_premium < 600:
                    errors.append(self._err(132, f"Person '{p.emirates_id_number}': Contract.GrossPremium must be >= 600 AED for package '{c.package_name}'",
                        trace=(
                            f"Package: '{c.package_name}' → not Thiqa ✓",
                            f"BirthDate: '{p.birth_date}' → RenewalDate '{c.renewal_date}' is > 1 year after birth ✓",
                            f"Contract.GrossPremium: {c.gross_premium} < 600 AED → VIOLATION",
                        )))
        return errors

    # Fires when: non-Principal Member.RelationTo is not a known Principal Member.ID in file or DB
    def _rule_136(self, model: pr.PersonRegister, res) -> list:
        if not model.header.sender_id:
            return []
        in_file_ids = {m_obj.id for p in model.persons if p.member for m_obj in [p.member]}
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            m = p.member
            if not m.relation or m.relation == "Principal":
                continue
            rt = m.relation_to
            if not rt or not rt.strip():
                continue
            if rt not in in_file_ids and not res.is_principal_relation_known(rt, model.header.sender_id):
                errors.append(self._err(136, f"Person '{p.emirates_id_number}': Member.RelationTo '{rt}' is not a registered principal member",
                    trace=(
                        f"Member.Relation: '{m.relation}' → not Principal ✓",
                        f"Member.RelationTo: '{rt}' → not found in current file member IDs ✓",
                        f"DB lookup (SenderID='{model.header.sender_id}'): '{rt}' → NOT FOUND → VIOLATION",
                    )))
        return errors

    # Fires when: Contract.PackageName is not a valid benefit package (from 2010-03-25, non-Thiqa)
    def _rule_153(self, model: pr.PersonRegister, res) -> list:
        if not model.header.sender_id:
            return []
        errors = []
        for person in model.persons:
            if not person.member:
                continue
            for c in person.member.contracts:
                start   = _parse_date(c.start_date)
                renewal = _parse_date(c.renewal_date)
                if start is None or start < _RULE_153_CUTOFF:
                    continue
                if renewal is None or renewal < _RULE_153_CUTOFF:
                    continue
                name = c.package_name
                if name not in _THIQA_PACKAGES and not res.is_valid_benefit_package(name):
                    trace = (
                        f"Condition 1 — Contract.StartDate: '{c.start_date}' → ≥ cutoff ✓",
                        f"Condition 2 — Contract.RenewalDate: '{c.renewal_date}' → ≥ cutoff ✓",
                        f"Condition 3 — PackageName: '{name}' → not Thiqa and NOT FOUND in benefit package table → VIOLATION",
                        f"Note: package names are case-sensitive. Verify exact value in the reference data.",
                    )
                    errors.append(self._err(153, f"Person '{person.emirates_id_number}': PackageName '{name}' is not a valid benefit package", trace=trace))
        return errors

    # Fires when: sender is a payer but a Person has no Member element
    def _rule_195(self, model: pr.PersonRegister, res) -> list:
        sender = model.header.sender_id
        is_payer = res.is_active_insurer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if p.member is None:
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → active insurer lookup → YES → rule applies ✓",
                    f"Condition 2 — Person '{p.emirates_id_number}' → no Member element found → VIOLATION",
                )
                errors.append(self._err(195, f"Person '{p.emirates_id_number}': must have at least one Member when sender is a payer", trace=trace))
        return errors

    # Fires when: Member.ID is duplicated within the same transaction (from 2011-06-15)
    def _rule_199(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        seen, errors = set(), []
        for p in model.persons:
            if not p.member:
                continue
            mid = p.member.id
            if mid in seen:
                errors.append(self._err(199, f"Person '{p.emirates_id_number}': Member.ID '{mid}' is duplicated in this file",
                    trace=(
                        f"Member.ID: '{mid}' → already seen earlier in this transaction → VIOLATION",
                        f"Member.ID must be unique within a transaction file",
                    )))
            seen.add(mid)
        return errors

    # Fires when: Contract.PayerID is present but not a valid active insurer or other license (from 2014-01-01)
    def _rule_208(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 1, 1):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.payer_id and c.payer_id.strip():
                    payer_ok = res.is_active_insurer_or_other(c.payer_id)
                    if not payer_ok:
                        trace = (
                            f"Condition 1 — Contract.PayerID: '{c.payer_id}' → present and non-empty ✓",
                            f"Condition 2 — Insurer/other license lookup: '{c.payer_id}' → NOT FOUND or inactive → VIOLATION",
                            f"Note: PayerID must be an active insurer or 'other' license in the registry.",
                        )
                        errors.append(self._err(208, f"Person '{p.emirates_id_number}': Contract.PayerID '{c.payer_id}' is not a valid insurer license", trace=trace))
        return errors

    # Fires when: Contract.TPAID is present but not a valid HAAD TPA license (from 2014-01-01)
    def _rule_209(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 1, 1):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                tpa = c.tpa_id
                if tpa and tpa.strip():
                    tpa_ok = res.is_haad_tpa(tpa)
                    if not tpa_ok:
                        trace = (
                            f"Condition 1 — Contract.TPAID: '{tpa}' → present and non-empty ✓",
                            f"Condition 2 — HAAD TPA license lookup: '{tpa}' → NOT FOUND or inactive → VIOLATION",
                            f"Note: TPAID must be a valid HAAD TPA license in the registry.",
                        )
                        errors.append(self._err(209, f"Person '{p.emirates_id_number}': Contract.TPAID '{tpa}' is not a valid TPA license", trace=trace))
        return errors

    # Fires when: Contract.TPAID is present but Contract.PayerID is empty (from 2014-01-01)
    def _rule_210(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 1, 1):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                tpa = c.tpa_id
                if tpa and tpa.strip() and (not c.payer_id or not c.payer_id.strip()):
                    errors.append(self._err(210, f"Person '{p.emirates_id_number}': Contract.PayerID must have a value when TPAID is present",
                        trace=(
                            f"Contract.TPAID: '{tpa}' → present ✓",
                            f"Contract.PayerID: '{c.payer_id}' → empty/missing → VIOLATION",
                        )))
        return errors

    # Fires when: sender is a payer and Member.Relation is empty (from 2014-06-01)
    def _rule_211(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 6, 1):
            return []
        sender = model.header.sender_id
        is_payer = res.is_active_insurer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            if not p.member.relation:
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → active insurer lookup → YES → rule applies ✓",
                    f"Condition 2 — Person '{p.emirates_id_number}' Member.Relation: empty → VIOLATION",
                )
                errors.append(self._err(211, f"Person '{p.emirates_id_number}': Member.Relation may not be empty when sender is a payer", trace=trace))
        return errors

    # Fires when: sender is a payer and a Person's Member has no Contract elements (from 2014-06-01)
    def _rule_212(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 6, 1):
            return []
        sender = model.header.sender_id
        is_payer = res.is_active_insurer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if p.member is None or not p.member.contracts:
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → active insurer lookup → YES → rule applies ✓",
                    f"Condition 2 — Person '{p.emirates_id_number}' → {'no Member element' if p.member is None else 'Member has no Contract elements'} → VIOLATION",
                )
                errors.append(self._err(212, f"Person '{p.emirates_id_number}': must have at least one Contract when sender is a payer", trace=trace))
        return errors

    # Fires when: sender is a payer and Contract.PayerID does not equal Header.SenderID (from 2014-12-01)
    def _rule_246(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 12, 1):
            return []
        sender = model.header.sender_id
        is_payer = res.is_active_insurer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.payer_id and c.payer_id.strip() and c.payer_id != sender:
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → active insurer lookup → YES → rule applies ✓",
                        f"Condition 2 — Contract.PayerID: '{c.payer_id}' ≠ SenderID: '{sender}' → VIOLATION",
                    )
                    errors.append(self._err(246, f"Person '{p.emirates_id_number}': Contract.PayerID must equal Header.SenderID '{sender}'", trace=trace))
        return errors

    # ── MOI validation rules (271-280, 310, 338-340) ───────────────────────────
    # get_moi_record() returns None until MOI web service integration is added;
    # rules are structurally complete and will activate once MOI is wired up.

    def _moi_precondition(self, model: pr.PersonRegister, person: pr.Person, contract) -> bool:
        """Common precondition for MOI rules: new/restarted/renewed, adult, non-exempt."""
        if model.header.sender_id in self._EXEMPT_PAYER_SENDERS:
            return False
        bd = _parse_date(person.birth_date)
        if bd is None:
            return False
        return (contract.status in self._NEW_CONTRACT_STATUSES
                and person.unified_number is not None)

    # Fires when: adult member with new/restarted/renewed contract has no UnifiedNumber (non-exempt sender, payer only)
    def _rule_271(self, model: pr.PersonRegister, res) -> list:
        sender = model.header.sender_id
        if sender in self._EXEMPT_PAYER_SENDERS:
            return []
        is_payer = res.is_active_insurer(sender)
        if not is_payer:
            return []
        errors = []
        cutoff = datetime.now() - timedelta(days=365)
        for p in model.persons:
            bd = _parse_date(p.birth_date)
            if bd is None or bd >= cutoff:
                continue
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status not in self._NEW_CONTRACT_STATUSES:
                    continue
                if p.unified_number is not None:
                    continue
                if c.status == "WarZone":
                    continue
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → not exempt, active insurer lookup → YES → rule applies ✓",
                    f"Condition 2 — Person '{p.emirates_id_number}' BirthDate: '{p.birth_date}' → adult (> 1 year ago) ✓",
                    f"Condition 3 — Contract.Status: '{c.status}' → New/Restarted/Renewed ✓",
                    f"Condition 4 — Person UnifiedNumber → absent → VIOLATION",
                )
                errors.append(self._err(271, f"Person '{p.emirates_id_number}': UnifiedNumber must be present", trace=trace))
        return errors

    # Fires when: Person.UnifiedNumber does not match the MOI record (dormant until MOI integration is live)
    def _rule_272(self, model: pr.PersonRegister, res) -> list:
        if model.header.sender_id in self._EXEMPT_PAYER_SENDERS:
            return []
        errors = []
        cutoff = datetime.now() - timedelta(days=365)
        for p in model.persons:
            if p.unified_number is None:
                continue
            if not p.member:
                continue
            bd = _parse_date(p.birth_date)
            for c in p.member.contracts:
                if c.status not in self._NEW_CONTRACT_STATUSES:
                    continue
                if bd is not None and bd >= cutoff:
                    moi = res.get_moi_record(str(p.unified_number))
                    if moi is not None and not moi.get("valid", True):
                        errors.append(self._err(272, f"Person '{p.emirates_id_number}': UnifiedNumber must be valid as per MOI",
                            trace=(
                                f"Person.UnifiedNumber: '{p.unified_number}'",
                                f"MOI record: found",
                                f"MOI 'valid' flag: {moi.get('valid', True)} → VIOLATION",
                            )))
                elif bd is not None and res.is_active_insurer(model.header.sender_id):
                    moi = res.get_moi_record(str(p.unified_number))
                    if moi is not None and not moi.get("valid", True):
                        errors.append(self._err(272, f"Person '{p.emirates_id_number}': UnifiedNumber must be valid as per MOI",
                            trace=(
                                f"Person.UnifiedNumber: '{p.unified_number}'",
                                f"MOI record: found",
                                f"MOI 'valid' flag: {moi.get('valid', True)} → VIOLATION",
                            )))
        return errors

    def _moi_name_check(self, model: pr.PersonRegister, res, rule_id: int,
                         field_name: str, person_value: "str | None",
                         moi_field: str, required: bool) -> list:
        if model.header.sender_id in self._EXEMPT_PAYER_SENDERS:
            return []
        if not res.is_active_insurer(model.header.sender_id):
            return []
        cutoff = datetime.now() - timedelta(days=365)
        errors = []
        for p in model.persons:
            if p.unified_number is None:
                continue
            bd = _parse_date(p.birth_date)
            if bd is None or bd >= cutoff:
                continue
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status not in self._NEW_CONTRACT_STATUSES:
                    continue
                moi = res.get_moi_record(str(p.unified_number))
                if moi is None:
                    continue
                moi_val = moi.get(moi_field, "")
                if not moi_val:
                    continue
                pval = getattr(p, field_name, None) or ""
                if required and (not pval or moi_val not in pval):
                    errors.append(self._err(rule_id, f"Person '{p.emirates_id_number}': {field_name} must match MOI record",
                        trace=(
                            f"Person.{field_name}: '{pval}'",
                            f"MOI {moi_field}: '{moi_val}'",
                            f"Person value {'empty' if not pval else 'not found in MOI'} → VIOLATION",
                        )))
                elif not required and pval and moi_val not in pval:
                    errors.append(self._err(rule_id, f"Person '{p.emirates_id_number}': {field_name} must match MOI record",
                        trace=(
                            f"Person.{field_name}: '{pval}'",
                            f"MOI {moi_field}: '{moi_val}'",
                            f"Person value not found in MOI field → VIOLATION",
                        )))
        return errors

    # Fires when: Person.FirstNameEn does not match the MOI English full name (dormant until MOI integration is live)
    def _rule_273(self, model: pr.PersonRegister, res) -> list:
        return self._moi_name_check(model, res, 273, "first_name_en", None, "FullNameEn", required=True)

    # Fires when: Person.MiddleNameEn does not match the MOI English full name (dormant until MOI integration is live)
    def _rule_274(self, model: pr.PersonRegister, res) -> list:
        return self._moi_name_check(model, res, 274, "middle_name_en", None, "FullNameEn", required=False)

    # Fires when: Person.LastNameEn does not match the MOI English full name (dormant until MOI integration is live)
    def _rule_275(self, model: pr.PersonRegister, res) -> list:
        return self._moi_name_check(model, res, 275, "last_name_en", None, "FullNameEn", required=True)

    # Fires when: Person.FirstNameAr does not match the MOI Arabic full name (dormant until MOI integration is live)
    def _rule_276(self, model: pr.PersonRegister, res) -> list:
        return self._moi_name_check(model, res, 276, "first_name_ar", None, "FullNameAr", required=True)

    # Fires when: Person.MiddleNameAr does not match the MOI Arabic full name (dormant until MOI integration is live)
    def _rule_277(self, model: pr.PersonRegister, res) -> list:
        return self._moi_name_check(model, res, 277, "middle_name_ar", None, "FullNameAr", required=False)

    # Fires when: Person.BirthDate year does not match the MOI birth year record (dormant until MOI integration is live)
    def _rule_279(self, model: pr.PersonRegister, res) -> list:
        if model.header.sender_id in self._EXEMPT_PAYER_SENDERS:
            return []
        if not res.is_active_insurer(model.header.sender_id):
            return []
        cutoff = datetime.now() - timedelta(days=365)
        errors = []
        for p in model.persons:
            if p.unified_number is None:
                continue
            bd = _parse_date(p.birth_date)
            if bd is None or bd >= cutoff:
                continue
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status not in self._NEW_CONTRACT_STATUSES:
                    continue
                moi = res.get_moi_record(str(p.unified_number))
                if moi is None:
                    continue
                moi_year = str(moi.get("BirthYear", ""))
                if moi_year and not p.birth_date.startswith(moi_year[-4:] if len(moi_year) >= 4 else moi_year):
                    errors.append(self._err(279, f"Person '{p.emirates_id_number}': BirthDate year must match MOI record",
                        trace=(
                            f"Person.BirthDate: '{p.birth_date}'",
                            f"MOI BirthYear: '{moi_year}'",
                            f"BirthDate year does not start with MOI year → VIOLATION",
                        )))
        return errors

    # Fires when: Person.Nationality does not match the MOI nationality code (dormant until MOI integration is live)
    def _rule_280(self, model: pr.PersonRegister, res) -> list:
        if model.header.sender_id in self._EXEMPT_PAYER_SENDERS:
            return []
        cutoff = datetime.now() - timedelta(days=365)
        errors = []
        for p in model.persons:
            if p.unified_number is None:
                continue
            if not p.member:
                continue
            bd = _parse_date(p.birth_date)
            for c in p.member.contracts:
                if c.status not in self._NEW_CONTRACT_STATUSES:
                    continue
                moi = res.get_moi_record(str(p.unified_number))
                if moi is None:
                    continue
                moi_nat = moi.get("NationalityCode", "")
                if moi_nat and moi_nat != p.nationality:
                    errors.append(self._err(280, f"Person '{p.emirates_id_number}': NationalityCode must match MOI record",
                        trace=(
                            f"Person.Nationality: '{p.nationality}'",
                            f"MOI NationalityCode: '{moi_nat}'",
                            f"Values differ → VIOLATION",
                        )))
        return errors

    # Fires when: Contract.VATPercent is present but outside 0–100
    def _rule_281(self, model: pr.PersonRegister, res) -> list:
        if not model.header.sender_id:
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                vp = c.vat_percent
                if vp is not None and (vp < 0 or vp > 100):
                    errors.append(self._err(281, f"Person '{p.emirates_id_number}': Contract.VATPercent must be between 0 and 100 (got {vp})",
                        trace=(
                            f"Contract.VATPercent: {vp} → outside allowed range [0, 100] → VIOLATION",
                        )))
        return errors

    # Fires when: sender is not an insurer/other and Person.CountryOfResidence is missing or invalid
    def _rule_284(self, model: pr.PersonRegister, res) -> list:
        if not model.header.sender_id:
            return []
        if res.is_active_insurer_or_other(model.header.sender_id):
            return []
        errors = []
        for p in model.persons:
            cor = p.country_of_residence
            if not cor or not cor.strip() or not res.is_valid_nationality_description(cor):
                errors.append(self._err(284, f"Person '{p.emirates_id_number}': CountryOfResidence '{cor}' is not valid",
                    trace=(
                        f"SenderID: '{model.header.sender_id}' → not insurer/other → rule applies ✓",
                        f"Person.CountryOfResidence: '{cor}' → {'empty/missing' if not cor or not cor.strip() else 'not in nationality description table'} → VIOLATION",
                    )))
        return errors

    # Fires when: CountryOfResidence='United Arab Emirates' but EmirateOfResidence is missing or not 1-7
    def _rule_285(self, model: pr.PersonRegister, res) -> list:
        if not model.header.sender_id:
            return []
        errors = []
        for p in model.persons:
            if p.country_of_residence != "United Arab Emirates":
                continue
            eor = p.emirate_of_residence
            if not eor or eor not in self._VALID_EMIRATE_OF_RESIDENCE:
                errors.append(self._err(285, f"Person '{p.emirates_id_number}': EmirateOfResidence must be 1-7 when CountryOfResidence is UAE",
                    trace=(
                        f"Person.CountryOfResidence: 'United Arab Emirates' ✓",
                        f"Person.EmirateOfResidence: '{eor}' → {'missing' if not eor else 'not in {1-7}'} → VIOLATION",
                    )))
        return errors

    # Fires when: Person.EmiratesIDNumber does not match the MOI Emirates ID record (dormant until MOI integration is live)
    def _rule_310(self, model: pr.PersonRegister, res) -> list:
        if model.header.sender_id in self._EXEMPT_PAYER_SENDERS:
            return []
        cutoff = datetime.now() - timedelta(days=365)
        errors = []
        for p in model.persons:
            if p.unified_number is None:
                continue
            bd = _parse_date(p.birth_date)
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status not in self._NEW_CONTRACT_STATUSES:
                    continue
                moi = res.get_moi_record(str(p.unified_number))
                if moi is None:
                    continue
                moi_eid = moi.get("EmiratesIDNumber", "")
                if not moi_eid:
                    continue
                eid_clean = p.emirates_id_number.replace("-", "")
                if eid_clean != moi_eid:
                    errors.append(self._err(310, f"Person '{p.emirates_id_number}': EmiratesIDNumber must match MOI record",
                        trace=(
                            f"Person.EmiratesIDNumber (normalised): '{eid_clean}'",
                            f"MOI EmiratesIDNumber: '{moi_eid}'",
                            f"Values differ → VIOLATION",
                        )))
        return errors

    # Fires when: Contract.Status is not in the allowed set of values (sender is payer, from 2022-10-13)
    def _rule_328(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2022, 10, 13):
            return []
        sender = model.header.sender_id
        is_payer = res.is_active_insurer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status not in self._VALID_CONTRACT_STATUSES:
                    trace = (
                        f"Condition 1 — SenderID: '{sender}' → active insurer lookup → YES → rule applies ✓",
                        f"Condition 2 — Contract.Status: '{c.status}' → not in allowed set → VIOLATION",
                        f"Allowed values: {', '.join(sorted(self._VALID_CONTRACT_STATUSES))}",
                    )
                    errors.append(self._err(328, f"Person '{p.emirates_id_number}': Contract.Status '{c.status}' is not a valid value", trace=trace))
        return errors

    # Fires when: Contract.Status='New' and Member.ID was already registered by this sender (non-TUP package, from 2022-10-13)
    def _rule_329(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2022, 10, 13):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status != "New":
                    continue
                if c.package_name and c.package_name.startswith("TUP"):
                    continue
                if res.has_person_register_member(p.member.id, model.header.sender_id):
                    errors.append(self._err(329, f"Person '{p.emirates_id_number}': Status 'New' can only be sent once per Member.ID",
                        trace=(
                            f"Contract.Status: 'New' ✓",
                            f"Member.ID: '{p.member.id}', SenderID: '{model.header.sender_id}'",
                            f"DB lookup: Member.ID already exists → VIOLATION",
                        )))
        return errors

    # Fires when: Contract.Status is New/Restarted/Gap Enrollment and StartDate ≠ RenewalDate (from 2022-10-13)
    def _rule_330(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2022, 10, 13):
            return []
        _statuses = frozenset({"New","Restarted","Gap Enrollment"})
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status not in _statuses:
                    continue
                if c.start_date != c.renewal_date:
                    errors.append(self._err(330, f"Person '{p.emirates_id_number}': Contract.StartDate must equal RenewalDate when Status is '{c.status}'",
                        trace=(
                            f"Contract.Status: '{c.status}' → requires StartDate = RenewalDate ✓",
                            f"Contract.StartDate: '{c.start_date}'",
                            f"Contract.RenewalDate: '{c.renewal_date}'",
                            f"Dates differ → VIOLATION",
                        )))
        return errors

    # Fires when: dummy EmiratesID is used with certain statuses (Restarted, Updated EID, Cancelled, etc.) from 2023-01-05
    def _rule_331(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 1, 5):
            return []
        _statuses_case1 = frozenset({"Restarted","Updated EmiratesIDNumber","Cancelled","Gap Enrollment"})
        errors = []
        for p in model.persons:
            eid = p.emirates_id_number
            if eid not in _DUMMY_EMIRATES_IDS:
                continue
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status in _statuses_case1:
                    if model.header.sender_id == "E001" and c.package_name in ("101","102","103","104","105","106","107","108","109"):
                        continue
                    errors.append(self._err(331, f"Person '{p.emirates_id_number}': must have a non-default EmiratesID for Status '{c.status}'",
                        trace=(
                            f"Person.EmiratesIDNumber: '{eid}' → is a dummy/default value ✓",
                            f"Contract.Status: '{c.status}' → requires real EmiratesID → VIOLATION",
                        )))
                elif c.status == "Renewed":
                    start = _parse_date(c.start_date)
                    cutoff = datetime.now() - timedelta(days=30)
                    if start is not None and start < cutoff:
                        if model.header.sender_id == "E001" and c.package_name in ("101","102","103","104","105","106","107","108","109"):
                            continue
                        errors.append(self._err(331, f"Person '{p.emirates_id_number}': must have a non-default EmiratesID for Status 'Renewed'",
                            trace=(
                                f"Person.EmiratesIDNumber: '{eid}' → is a dummy/default value ✓",
                                f"Contract.Status: 'Renewed', StartDate: '{c.start_date}' → older than 30 days → VIOLATION",
                            )))
        return errors

    # Fires when: Renewed/Corrected/Updated EID/Cancelled contract has a StartDate different from the previous record (from 2022-10-13)
    def _rule_332(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2022, 10, 13):
            return []
        _statuses = frozenset({"Renewed","Corrected","Updated EmiratesIDNumber","Cancelled"})
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status not in _statuses:
                    continue
                start = _parse_date(c.start_date)
                if start is None or start <= datetime(2023, 1, 5):
                    continue
                prev = res.get_latest_person_register_contract(p.member.id, model.header.sender_id)
                if prev is None:
                    continue
                prev_start = _parse_date(str(prev.get("START_DATE", "")))
                if prev_start is not None and start != prev_start:
                    errors.append(self._err(332, f"Person '{p.emirates_id_number}': Contract.StartDate must equal previous StartDate for Status '{c.status}'",
                        trace=(
                            f"Contract.Status: '{c.status}' → requires StartDate = previous StartDate ✓",
                            f"Current StartDate: '{c.start_date}' → {start.strftime('%d/%m/%Y')}",
                            f"Previous StartDate: {prev_start.strftime('%d/%m/%Y')}",
                            f"Dates differ → VIOLATION",
                        )))
        return errors

    # Fires when: Renewed/Corrected Date contract has a RenewalDate before the previous record's ExpiryDate (from 2022-10-13)
    def _rule_333(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2022, 10, 13):
            return []
        _statuses = frozenset({"Renewed","Corrected Date"})
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status not in _statuses:
                    continue
                renewal = _parse_date(c.renewal_date)
                if renewal is None:
                    continue
                prev = res.get_latest_person_register_contract(p.member.id, model.header.sender_id)
                if prev is None:
                    continue
                prev_expiry = _parse_date(str(prev.get("EXPIRY_DATE", "")))
                if prev_expiry is not None and renewal < prev_expiry:
                    errors.append(self._err(333, f"Person '{p.emirates_id_number}': Contract.RenewalDate must be >= previous ExpiryDate for Status '{c.status}'",
                        trace=(
                            f"Contract.Status: '{c.status}' → requires RenewalDate ≥ previous ExpiryDate ✓",
                            f"Current RenewalDate: '{c.renewal_date}' → {renewal.strftime('%d/%m/%Y')}",
                            f"Previous ExpiryDate: {prev_expiry.strftime('%d/%m/%Y')}",
                            f"RenewalDate < previous ExpiryDate → VIOLATION",
                        )))
        return errors

    # Fires when: Contract.Status='Corrected' but no previous record exists for this Member (from 2022-10-13)
    def _rule_334(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2022, 10, 13):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status != "Corrected":
                    continue
                prev = res.get_latest_person_register_contract(p.member.id, model.header.sender_id)
                if prev is None:
                    errors.append(self._err(334, f"Person '{p.emirates_id_number}': no previous record found for Status 'Corrected'",
                        trace=(
                            f"Contract.Status: 'Corrected' → requires previous record ✓",
                            f"Member.ID: '{p.member.id}', SenderID: '{model.header.sender_id}'",
                            f"DB lookup: no previous Person.Register contract found → VIOLATION",
                        )))
        return errors

    # Fires when: Contract.Status='Updated EmiratesIDNumber' but EmiratesIDNumber is not a valid format (from 2022-10-13)
    def _rule_335(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2022, 10, 13):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status != "Updated EmiratesIDNumber":
                    continue
                eid = p.emirates_id_number
                if not _is_valid_emirates_id(eid):
                    errors.append(self._err(335, f"Person '{p.emirates_id_number}': EmiratesIDNumber must have a valid format for Status 'Updated EmiratesIDNumber'",
                        trace=(
                            f"Contract.Status: 'Updated EmiratesIDNumber' → requires valid EID ✓",
                            f"Person.EmiratesIDNumber: '{eid}' → format/Luhn check FAILED → VIOLATION",
                        )))
        return errors

    # Fires when: Contract.Status='Cancelled' but the Member.ID has no previous Person.Register record (from 2022-10-13)
    def _rule_336(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2022, 10, 13):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status != "Cancelled":
                    continue
                if not res.has_person_register_member(p.member.id, model.header.sender_id):
                    errors.append(self._err(336, f"Person '{p.emirates_id_number}': Member.ID '{p.member.id}' must exist in previous Person.Register for Status 'Cancelled'",
                        trace=(
                            f"Contract.Status: 'Cancelled' → requires previous record ✓",
                            f"Member.ID: '{p.member.id}', SenderID: '{model.header.sender_id}'",
                            f"DB lookup: no previous Person.Register record found → VIOLATION",
                        )))
        return errors

    def _moi_sponsor_check(self, model: pr.PersonRegister, res, rule_id: int,
                            person_field: str, moi_field: str) -> list:
        if model.header.sender_id in self._EXEMPT_PAYER_SENDERS:
            return []
        if not res.is_active_insurer(model.header.sender_id):
            return []
        cutoff = datetime.now() - timedelta(days=365)
        errors = []
        for p in model.persons:
            if p.unified_number is None:
                continue
            bd = _parse_date(p.birth_date)
            if bd is None or bd >= cutoff:
                continue
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status not in self._NEW_CONTRACT_STATUSES:
                    continue
                moi = res.get_moi_record(str(p.unified_number))
                if moi is None:
                    continue
                moi_val = moi.get(moi_field, "")
                if not moi_val:
                    continue
                pval = getattr(p, person_field, None) or ""
                if moi_val != pval:
                    errors.append(self._err(rule_id, f"Person '{p.emirates_id_number}': {person_field} must match MOI record",
                        trace=(
                            f"Person.{person_field}: '{pval}'",
                            f"MOI {moi_field}: '{moi_val}'",
                            f"Values differ → VIOLATION",
                        )))
        return errors

    # Fires when: Person.SponsorNameEn does not match the MOI sponsor English name (dormant until MOI integration is live)
    def _rule_338(self, model: pr.PersonRegister, res) -> list:
        return self._moi_sponsor_check(model, res, 338, "sponsor_name_en", "SponsorNameEn")

    # Fires when: Person.SponsorNameAr does not match the MOI sponsor Arabic name (dormant until MOI integration is live)
    def _rule_339(self, model: pr.PersonRegister, res) -> list:
        return self._moi_sponsor_check(model, res, 339, "sponsor_name_ar", "SponsorNameAr")

    # Fires when: Person.SponsorNumber does not match the MOI sponsor number (dormant until MOI integration is live)
    def _rule_340(self, model: pr.PersonRegister, res) -> list:
        return self._moi_sponsor_check(model, res, 340, "sponsor_number", "SponsorNumber")

    # Fires when: Principal Member.RelationToEmiratesIDNumber ≠ Person.EmiratesIDNumber (sender is payer, from 2023-03-22)
    def _rule_347(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 3, 22):
            return []
        sender = model.header.sender_id
        is_payer = res.is_active_insurer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            m = p.member
            if m.relation != "Principal":
                continue
            rteid = m.relation_to_emirates_id_number
            if rteid and rteid.strip() and rteid != p.emirates_id_number:
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → active insurer lookup → YES → rule applies ✓",
                    f"Condition 2 — Member.Relation: 'Principal' ✓",
                    f"Condition 3 — RelationToEmiratesIDNumber: '{rteid}' ≠ EmiratesIDNumber: '{p.emirates_id_number}' → VIOLATION",
                )
                errors.append(self._err(347, f"Person '{p.emirates_id_number}': Member.RelationToEmiratesIDNumber must equal EmiratesIDNumber when Relation is Principal", trace=trace))
        return errors

    # Fires when: Principal Member.RelationToUnifiedNumber ≠ Person.UnifiedNumber (sender is payer, from 2023-03-22)
    def _rule_348(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 3, 22):
            return []
        sender = model.header.sender_id
        is_payer = res.is_active_insurer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            m = p.member
            if m.relation != "Principal":
                continue
            rtuid = m.relation_to_unified_number
            if rtuid and str(rtuid).strip() and str(rtuid) != str(p.unified_number):
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → active insurer lookup → YES → rule applies ✓",
                    f"Condition 2 — Member.Relation: 'Principal' ✓",
                    f"Condition 3 — RelationToUnifiedNumber: '{rtuid}' ≠ UnifiedNumber: '{p.unified_number}' → VIOLATION",
                )
                errors.append(self._err(348, f"Person '{p.emirates_id_number}': Member.RelationToUnifiedNumber must equal UnifiedNumber when Relation is Principal", trace=trace))
        return errors

    # Fires when: non-Principal Member.RelationToEmiratesIDNumber is a dummy ID value (sender is payer, from 2023-03-22)
    def _rule_349(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 3, 22):
            return []
        sender = model.header.sender_id
        is_payer = res.is_active_insurer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            m = p.member
            if m.relation == "Principal":
                continue
            rteid = m.relation_to_emirates_id_number
            if rteid and rteid in _DUMMY_EMIRATES_IDS:
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → active insurer lookup → YES → rule applies ✓",
                    f"Condition 2 — Member.Relation: '{m.relation}' → not Principal ✓",
                    f"Condition 3 — RelationToEmiratesIDNumber: '{rteid}' → is a dummy/default value → VIOLATION",
                )
                errors.append(self._err(349, f"Person '{p.emirates_id_number}': Member.RelationToEmiratesIDNumber cannot be a default value for non-Principal members", trace=trace))
        return errors

    # Fires when: Contract.Status='Gap Enrollment' is sent by a sender other than 'E001' (from 2023-03-28)
    def _rule_352(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 3, 28):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status == "Gap Enrollment" and model.header.sender_id != "E001":
                    errors.append(self._err(352, f"Person '{p.emirates_id_number}': Status 'Gap Enrollment' is only allowed when SenderID is 'E001'",
                        trace=(
                            f"Contract.Status: 'Gap Enrollment' → only SenderID='E001' allowed ✓",
                            f"Header.SenderID: '{model.header.sender_id}' ≠ 'E001' → VIOLATION",
                        )))
        return errors

    # Fires when: Gap Enrollment Contract.ExpiryDate is after the previous record's RenewalDate (from 2023-03-29)
    def _rule_353(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 3, 29):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status != "Gap Enrollment":
                    continue
                expiry = _parse_date(c.expiry_date)
                if expiry is None:
                    continue
                prev = res.get_latest_person_register_contract(p.member.id, model.header.sender_id)
                if prev is None:
                    continue
                prev_renewal = _parse_date(str(prev.get("RENEWAL_DATE", "")))
                if prev_renewal is not None and expiry > prev_renewal:
                    errors.append(self._err(353, f"Person '{p.emirates_id_number}': Contract.ExpiryDate must be <= previous RenewalDate for Status 'Gap Enrollment'",
                        trace=(
                            f"Contract.Status: 'Gap Enrollment' ✓",
                            f"Current ExpiryDate: '{c.expiry_date}' → {expiry.strftime('%d/%m/%Y')}",
                            f"Previous RenewalDate: {prev_renewal.strftime('%d/%m/%Y')}",
                            f"ExpiryDate > previous RenewalDate → VIOLATION",
                        )))
        return errors

    # Fires when: non-dummy EmiratesIDNumber does not start with '784' (from 2023-06-23)
    def _rule_354(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 6, 23):
            return []
        errors = []
        for p in model.persons:
            eid = p.emirates_id_number
            if eid in _DUMMY_EMIRATES_IDS:
                continue
            if not eid.startswith("784"):
                errors.append(self._err(354, f"Person '{p.emirates_id_number}': EmiratesIDNumber must start with '784' (except default values)",
                    trace=(
                        f"EmiratesIDNumber: '{eid}' → not a dummy value ✓",
                        f"Does not start with '784' → VIOLATION",
                    )))
        return errors

    # Fires when: SenderID is A001 or E001 and Member.ID starts with '0' (from 2023-06-23)
    def _rule_355(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 6, 23):
            return []
        if model.header.sender_id not in ("A001", "E001"):
            return []
        errors = []
        for p in model.persons:
            if p.member and p.member.id.startswith("0"):
                errors.append(self._err(355, f"Person '{p.emirates_id_number}': Member.ID must not start with '0' when SenderID is '{model.header.sender_id}'",
                    trace=(
                        f"SenderID: '{model.header.sender_id}' → A001 or E001 ✓",
                        f"Member.ID: '{p.member.id}' → starts with '0' → VIOLATION",
                    )))
        return errors

    # Fires when: CountryOfResidence is not UAE but EmirateOfResidence is populated (from 2024-01-03)
    def _rule_361(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2024, 1, 3):
            return []
        errors = []
        for p in model.persons:
            if p.country_of_residence == "United Arab Emirates":
                continue
            eor = p.emirate_of_residence
            if eor and eor.strip():
                errors.append(self._err(361, f"Person '{p.emirates_id_number}': EmirateOfResidence must be empty when CountryOfResidence is not UAE",
                    trace=(
                        f"Person.CountryOfResidence: '{p.country_of_residence}' → not 'United Arab Emirates' ✓",
                        f"Person.EmirateOfResidence: '{eor}' → must be empty → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Person.City is empty
    def _rule_7(self, model: pr.PersonRegister, res) -> list:
        errors = []
        for p in model.persons:
            if not p.city or not p.city.strip():
                errors.append(self._inactive_err(7, f"Person '{p.emirates_id_number}': City may not be empty",
                    trace=(
                        f"Person.EmiratesIDNumber: '{p.emirates_id_number}'",
                        f"Person.City: {repr(p.city)} → empty or whitespace → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Contract.RenewalDate > TransactionDate (date range Apr 18 – May 31, 2011)
    def _rule_100(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None:
            return []
        if not (datetime(2011, 4, 18) <= tx < datetime(2011, 5, 31)):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                renewal = _parse_date(c.renewal_date)
                if renewal is not None and renewal > tx:
                    errors.append(self._inactive_err(100, f"Person '{p.emirates_id_number}': Contract.RenewalDate '{c.renewal_date}' may not be greater than Header.TransactionDate '{model.header.transaction_date}'",
                        trace=(
                            f"Person.EmiratesIDNumber: '{p.emirates_id_number}'",
                            f"Contract.RenewalDate: '{c.renewal_date}' → {renewal.date()}",
                            f"Header.TransactionDate: '{model.header.transaction_date}' → {tx.date()}",
                            f"RenewalDate {renewal.date()} > TransactionDate {tx.date()} → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) MOI FullNameAr does not contain Person.LastNameAr for new/active members
    def _rule_278(self, model: pr.PersonRegister, res) -> list:
        sender = model.header.sender_id
        if sender in ("A001", "D001", "E001"):
            return []
        is_payer = res.is_haad_payer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if not p.unified_number or not p.member:
                continue
            status = next((c.status for c in p.member.contracts if c.status), None)
            if status not in ("New", "Restarted", "Renewed"):
                continue
            birth = _parse_date(p.birth_date)
            if birth is None or (datetime.now() - birth).days <= 365:
                continue
            try:
                moi = res.get_moi_record(str(p.unified_number))
            except Exception:
                continue
            if not moi:
                continue
            full_name_ar = (moi.get("FullNameAr") or "").strip()
            if not full_name_ar:
                continue
            last_name_ar = (p.last_name_ar or "").strip()
            if not last_name_ar or last_name_ar not in full_name_ar:
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → HAAD payer lookup → YES → rule applies ✓",
                    f"Condition 2 — Contract.Status: '{status}' → New/Restarted/Renewed ✓",
                    f"Condition 3 — MOI FullNameAr: '{full_name_ar}' → does not contain LastNameAr: '{last_name_ar}' → VIOLATION",
                )
                errors.append(self._inactive_err(278, f"Person '{p.emirates_id_number}': LastNameAr must be part of MOI FullNameAr for UnifiedNumber '{p.unified_number}'", trace=trace))
        return errors

    # Fires when: (INACTIVE) MOI PassportNumber does not match Person.PassportNumber for new/active members
    def _rule_337(self, model: pr.PersonRegister, res) -> list:
        sender = model.header.sender_id
        if sender in ("A001", "D001", "E001"):
            return []
        is_payer = res.is_haad_payer(sender)
        if not is_payer:
            return []
        errors = []
        for p in model.persons:
            if not p.unified_number or not p.member:
                continue
            status = next((c.status for c in p.member.contracts if c.status), None)
            if status not in ("New", "Restarted", "Renewed"):
                continue
            birth = _parse_date(p.birth_date)
            if birth is None or (datetime.now() - birth).days <= 365:
                continue
            try:
                moi = res.get_moi_record(str(p.unified_number))
            except Exception:
                continue
            if not moi:
                continue
            moi_passport = (moi.get("PassportNumber") or "").strip()
            if not moi_passport:
                continue
            person_passport = (p.passport_number or "").strip()
            if not person_passport or person_passport != moi_passport:
                trace = (
                    f"Condition 1 — SenderID: '{sender}' → HAAD payer lookup → YES → rule applies ✓",
                    f"Condition 2 — Contract.Status: '{status}' → New/Restarted/Renewed ✓",
                    f"Condition 3 — MOI PassportNumber: '{moi_passport}' ≠ Person.PassportNumber: '{person_passport}' → VIOLATION",
                )
                errors.append(self._inactive_err(337, f"Person '{p.emirates_id_number}': PassportNumber must match MOI PassportNumber for UnifiedNumber '{p.unified_number}'", trace=trace))
        return errors

    # Fires when: (INACTIVE) Member.RelationToEmiratesIDNumber exists but no Person.Register record found with that EID
    def _rule_350(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 3, 22):
            return []
        if not res.is_haad_payer(model.header.sender_id):
            return []
        errors = []
        for p in model.persons:
            if not p.member or p.member.relation == "Principal":
                continue
            rel_eid = p.member.relation_to_emirates_id_number
            if not rel_eid or not rel_eid.strip() or rel_eid in _DUMMY_EMIRATES_IDS:
                continue
            if not res.person_register_eid_exists(rel_eid):
                errors.append(self._inactive_err(350, f"Person '{p.emirates_id_number}': RelationToEmiratesIDNumber '{rel_eid}' is not present in any Person.Register record",
                    trace=(
                        f"Person.EmiratesIDNumber: '{p.emirates_id_number}', Member.Relation: '{p.member.relation}'",
                        f"Member.RelationToEmiratesIDNumber: '{rel_eid}'",
                        f"EID '{rel_eid}' not found in any Person.Register record → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Member.RelationToUnifiedNumber exists but no Person.Register record found with that UnifiedNumber
    def _rule_351(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 3, 22):
            return []
        if not res.is_haad_payer(model.header.sender_id):
            return []
        errors = []
        for p in model.persons:
            if not p.member or p.member.relation == "Principal":
                continue
            rel_uid = p.member.relation_to_unified_number
            if not rel_uid or not rel_uid.strip():
                continue
            if not res.person_register_unified_number_exists(rel_uid):
                errors.append(self._inactive_err(351, f"Person '{p.emirates_id_number}': RelationToUnifiedNumber '{rel_uid}' is not present in any Person.Register record",
                    trace=(
                        f"Person.EmiratesIDNumber: '{p.emirates_id_number}', Member.Relation: '{p.member.relation}'",
                        f"Member.RelationToUnifiedNumber: '{rel_uid}'",
                        f"UnifiedNumber '{rel_uid}' not found in any Person.Register record → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Contract.Status='Recon' but SenderID is not 'A001' or 'E001'
    def _rule_400(self, model: pr.PersonRegister, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2024, 1, 28):
            return []
        sender = model.header.sender_id
        if sender in ("A001", "E001"):
            return []
        errors = []
        for p in model.persons:
            if not p.member:
                continue
            for c in p.member.contracts:
                if c.status == "Recon":
                    errors.append(self._inactive_err(400, f"Person '{p.emirates_id_number}': Contract.Status='Recon' is only allowed for SenderID 'A001' or 'E001'",
                        trace=(
                            f"Person.EmiratesIDNumber: '{p.emirates_id_number}'",
                            f"Header.SenderID: '{sender}' → not 'A001' or 'E001'",
                            f"Contract.Status: 'Recon' → only allowed from A001/E001 → VIOLATION",
                        )))
        return errors


# ── PriorAuthorization rules ───────────────────────────────────────────────────

class _PriorAuthorizationValidator(_BaseValidator):
    TRANSACTION = "Prior.Authorization"

    _RULE_DESCRIPTIONS = {
        "9":   "Header.RecordCount is not 1 (Prior.Authorization always contains exactly one Authorization)",
        "30":  "Header.DispositionFlag is not PTE_SUBMIT, PTE_VALIDATE_ONLY, or PTE_RESPONSE",
        "55":  "SenderID is not a valid payer or TPA license",
        "61":  "Header.TransactionDate does not match today's date",
        "62":  "any Activity.Type is outside the allowed set {3,4,5,6,8,9}",
        "63":  "any Activity.Net < 0",
        "64":  "(INACTIVE) Activity.Code is not a valid ICD9 code",
        "65":  "Activity.Type is CPT/HCPCS-compatible but code is not a valid CPT or HCPCS code",
        "66":  "Activity.Type=2 (Drug) and code is not a valid trade or generic drug code",
        "67":  "Activity.Type=10 (Dental) and code is not a valid USCLS dental code",
        "68":  "Activity.ID is duplicated within the Authorization",
        "69":  "Activity.Quantity is present and <= 0",
        "70":  "Activity.Quantity is present and is not a whole number",
        "78":  "Authorization.Result is Approved/Partially Approved/Not Required but DenialCode is present",
        "91":  "any Activity.DenialCode is not a registered denial code",
        "113": "(INACTIVE) Activity.Type=3 and Activity.Code contains '-'",
        "114": "Authorization.DenialCode is present but not a registered denial code",
        "146": "Authorization.End is before Authorization.Start",
        "159": "the Prior.Request type is Cancellation and Activities are present",
        "160": "the Prior.Request type is Authorization or Extension but no Activities are present",
        "161": "(INACTIVE) TransactionDate >= 2011-01-01 and this Authorization.ID is a duplicate in the file",
        "163": "Authorization.Result is Denied or Partially Approved but DenialCode is missing",
        "164": "(INACTIVE) TransactionDate >= 2011-01-01 and Authorization.Start is null/empty",
        "165": "(INACTIVE) TransactionDate >= 2011-01-01 and Authorization.End is null/empty",
        "166": "Authorization.IDPayer is already used by another Prior.Authorization transaction",
        "169": "ReceiverID is not HAAD and not a valid TPA for Prior.Authorization",
        "178": "Authorization.ID is missing or blank",
        "180": "(INACTIVE) TransactionDate >= 2011-06-15 and Authorization.Start > TransactionDate",
        "181": "a Prior.Authorization response was already submitted for this Authorization.ID",
        "236": "Authorization.Start is after the earliest activity Start in the corresponding Prior.Request",
        "237": "(INACTIVE) TransactionDate >= 2014-09-01 and Activity.PaymentAmount=0 but Quantity!=0",
        "240": "(INACTIVE) Corresponding PriorRequest type is Prescription/Authorization and Authorization.DenialCode is set",
        "241": "Activity.PaymentAmount > Activity.Net",
        "242": "Activity.PaymentAmount < 0",
        "257": "(INACTIVE) Corresponding PriorRequest type is Prescription/Authorization and no Activities present",
        "258": "Authorization Activity IDs contain IDs not found in the corresponding Prior.Request",
        "259": "Authorization.IDPayer is present but Authorization.ID is not unique per sender",
        "264": "(INACTIVE) Result rules conflict with PriorRequest type (Eligibility/Cancellation need result; Prescription/Authorization must not)",
        "266": "Prior.Request type is Eligibility but Authorization contains Activities",
        "267": "(INACTIVE) PriorRequest type is not Prescription but Authorization.Limit is set",
        "268": "Prior.Request type is Status Inquiry but Authorization contains Activities",
        "269": "Authorization/Extension PA has Result=Approved/Partially Approved/Not Required but IDPayer is missing",
        "270": "Prescription PA has Result=Approved/Partially Approved/Not Required but IDPayer is missing",
        "346": "any DenialCode (Authorization or Activity level) is not active on the transaction date (from 2023-01-30)",
        "367": "(INACTIVE) TransactionDate >= 2024-08-05 and Activity.Net != Activity.PaymentAmount but result is not 'No'",
        "368": "(INACTIVE) TransactionDate >= 2024-08-05 and Activity.Net == Activity.PaymentAmount but result is not 'Yes'",
        "379": "(INACTIVE) TransactionDate >= 2025-06-01, Trade Drug activity with UPP markup, but SenderID not in allowed list",
    }

    _PA_ALLOWED_FLAGS = frozenset({"PTE_SUBMIT", "PTE_VALIDATE_ONLY", "PTE_RESPONSE"})
    _PA_ALLOWED_ACTIVITY_TYPES = frozenset({3, 4, 5, 6, 8, 9})

    def _rules(self):
        return [
            self._rule_9,   self._rule_30,  self._rule_55,  self._rule_61,  self._rule_62,
            self._rule_63,  self._rule_64,  self._rule_65,  self._rule_66,  self._rule_67,
            self._rule_68,  self._rule_69,  self._rule_70,  self._rule_78,  self._rule_91,
            self._rule_113, self._rule_114, self._rule_146, self._rule_159, self._rule_160,
            self._rule_161, self._rule_163, self._rule_164, self._rule_165, self._rule_166,
            self._rule_169, self._rule_178, self._rule_180, self._rule_181, self._rule_236,
            self._rule_237, self._rule_240, self._rule_241, self._rule_242, self._rule_257,
            self._rule_258, self._rule_259, self._rule_264, self._rule_266, self._rule_267,
            self._rule_268, self._rule_269, self._rule_270, self._rule_346, self._rule_367,
            self._rule_368, self._rule_379,
        ]

    # Fires when: Header.RecordCount is not 1 (Prior.Authorization always contains exactly one Authorization)
    def _rule_9(self, model: pa.PriorAuthorization, res) -> list:
        if model.header.record_count != 1:
            return [self._err(9, f"Header.RecordCount is {model.header.record_count} but Prior.Authorization always contains 1 Authorization",
                trace=(
                    f"Header.RecordCount: {model.header.record_count}",
                    f"Expected: exactly 1 Authorization element",
                    f"Count mismatch → VIOLATION",
                ))]
        return []

    # Fires when: Header.DispositionFlag is not PTE_SUBMIT, PTE_VALIDATE_ONLY, or PTE_RESPONSE
    def _rule_30(self, model: pa.PriorAuthorization, res) -> list:
        flag = model.header.disposition_flag
        if flag not in self._PA_ALLOWED_FLAGS:
            return [self._err(30, f"DispositionFlag must be PTE_SUBMIT, PTE_VALIDATE_ONLY, or PTE_RESPONSE (got '{flag}')",
                trace=(
                    f"Header.DispositionFlag: '{flag}'",
                    f"Allowed values: {sorted(self._PA_ALLOWED_FLAGS)}",
                    f"Not in allowed set → VIOLATION",
                ))]
        return []

    # Fires when: SenderID is not a valid payer or TPA license
    def _rule_55(self, model: pa.PriorAuthorization, res) -> list:
        sender = model.header.sender_id
        is_payer = res.is_haad_payer(sender)
        is_tpa = res.is_haad_tpa(sender)
        if not (is_payer or is_tpa):
            trace = (
                f"SenderID: '{sender}' → HAAD payer lookup → {'YES' if is_payer else 'NO'}",
                f"SenderID: '{sender}' → HAAD TPA lookup → {'YES' if is_tpa else 'NO'}",
                f"Neither payer nor TPA → VIOLATION",
            )
            return [self._err(55, f"Header.SenderID '{sender}' must be a valid payer or TPA for Prior.Authorization", trace=trace)]
        return []

    # Fires when: Header.TransactionDate does not match today's date
    def _rule_61(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None:
            return []
        if tx.date() != datetime.now().date():
            return [self._err(61, f"Header.TransactionDate '{model.header.transaction_date}' must match today's date",
                trace=(
                    f"Header.TransactionDate: '{model.header.transaction_date}' → parsed as {tx.strftime('%d/%m/%Y')}",
                    f"Today's date: {datetime.now().strftime('%d/%m/%Y')}",
                    f"Dates do not match → VIOLATION",
                ))]
        return []

    # Fires when: any Activity.Type is outside the allowed set {3,4,5,6,8,9}
    def _rule_62(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type not in self._PA_ALLOWED_ACTIVITY_TYPES:
                errors.append(self._err(62, f"Authorization '{auth.id}', Activity '{act.id}': Type {act.type} is not allowed in Prior.Authorization",
                    trace=(
                        f"Activity.Type: {act.type} → not in allowed set {sorted(self._PA_ALLOWED_ACTIVITY_TYPES)} → VIOLATION",
                    )))
        return errors

    # Fires when: any Activity.Net < 0
    def _rule_63(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.net < 0:
                errors.append(self._err(63, f"Authorization '{auth.id}', Activity '{act.id}': Net {act.net} must be >= 0",
                    trace=(
                        f"Activity.Net: {act.net} < 0 → VIOLATION",
                    )))
        return errors

    # Fires when: Activity.Type is CPT/HCPCS-compatible but code is not a valid CPT or HCPCS code
    def _rule_65(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type in (1, 3, 4, 5, 6, 8, 9):
                cpt_ok = res.is_valid_cpt_code(act.code)
                hcpcs_ok = res.is_valid_hcpcs_code(act.code)
                if not cpt_ok and not hcpcs_ok:
                    trace = (
                        f"Condition 1 — Activity.Type: {act.type} → CPT/HCPCS-compatible type ✓",
                        f"Condition 2 — CPT lookup: '{act.code}' → {'FOUND ✓' if cpt_ok else 'NOT FOUND'}",
                        f"Condition 3 — HCPCS lookup: '{act.code}' → {'FOUND ✓' if hcpcs_ok else 'NOT FOUND'}",
                        f"Neither CPT nor HCPCS match → VIOLATION",
                    )
                    errors.append(self._err(65, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid CPT/HCPCS code", trace=trace))
        return errors

    # Fires when: Activity.Type=2 (Drug) and code is not a valid trade or generic drug code
    def _rule_66(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 2:
                trade_ok = res.is_valid_trade_drug(act.code)
                generic_ok = res.is_valid_generic_drug(act.code)
                if not trade_ok and not generic_ok:
                    trace = (
                        f"Condition 1 — Activity.Type: 2 (Drug) ✓",
                        f"Condition 2 — Trade drug lookup: '{act.code}' → {'FOUND ✓' if trade_ok else 'NOT FOUND'}",
                        f"Condition 3 — Generic drug lookup: '{act.code}' → {'FOUND ✓' if generic_ok else 'NOT FOUND'}",
                        f"Neither trade nor generic drug match → VIOLATION",
                    )
                    errors.append(self._err(66, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid drug code", trace=trace))
        return errors

    # Fires when: Activity.Type=10 (Dental) and code is not a valid USCLS dental code
    def _rule_67(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 10:
                dental_ok = res.is_valid_dental_code(act.code)
                if not dental_ok:
                    trace = (
                        f"Condition 1 — Activity.Type: 10 (Dental/USCLS) ✓",
                        f"Condition 2 — Dental (USCLS) code lookup: '{act.code}' → NOT FOUND → VIOLATION",
                        f"Note: dental codes are case-sensitive. Verify exact value in the tariff.",
                    )
                    errors.append(self._err(67, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid dental code", trace=trace))
        return errors

    # Fires when: Activity.ID is duplicated within the Authorization
    def _rule_68(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        seen = set()
        for act in auth.activities:
            if act.id in seen:
                errors.append(self._err(68, f"Authorization '{auth.id}', Activity '{act.id}': Activity ID is duplicated",
                    trace=(
                        f"Activity.ID: '{act.id}' → already seen earlier in this Authorization → VIOLATION",
                    )))
            seen.add(act.id)
        return errors

    # Fires when: Activity.Quantity is present and <= 0
    def _rule_69(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            qty = act.quantity
            if qty is not None and qty <= 0:
                errors.append(self._err(69, f"Authorization '{auth.id}', Activity '{act.id}': Quantity must be > 0",
                    trace=(
                        f"Activity.Quantity: {qty} ≤ 0 → VIOLATION",
                    )))
        return errors

    # Fires when: Activity.Quantity is present and is not a whole number
    def _rule_70(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            qty = act.quantity
            if qty is not None and qty != int(qty):
                errors.append(self._err(70, f"Authorization '{auth.id}', Activity '{act.id}': Quantity must be a whole number",
                    trace=(
                        f"Activity.Quantity: {qty} → not a whole number → VIOLATION",
                    )))
        return errors

    # Fires when: Authorization.Result is Approved/Partially Approved/Not Required but DenialCode is present
    def _rule_78(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        if auth.result not in ("Approved", "Partially Approved", "Not Required"):
            return []
        if auth.denial_code and auth.denial_code.strip():
            return [self._err(78, f"Authorization '{auth.id}': DenialCode must not be present when Result is '{auth.result}'",
                trace=(
                    f"Authorization.Result: '{auth.result}' → approved/not-required result ✓",
                    f"Authorization.DenialCode: '{auth.denial_code}' → present → VIOLATION",
                ))]
        return []

    # Fires when: any Activity.DenialCode is not a registered denial code
    def _rule_91(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.denial_code:
                code_ok = res.is_valid_denial_code(act.denial_code)
                if not code_ok:
                    trace = (
                        f"Activity DenialCode lookup: '{act.denial_code}' → NOT FOUND in denial code reference → VIOLATION",
                    )
                    errors.append(self._err(91, f"Authorization '{auth.id}', Activity '{act.id}': DenialCode '{act.denial_code}' is not a registered denial code", trace=trace))
        return errors

    # Fires when: Authorization.DenialCode is present but not a registered denial code
    def _rule_114(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        if not auth.denial_code:
            return []
        code_ok = res.is_valid_denial_code(auth.denial_code)
        if not code_ok:
            trace = (
                f"Authorization DenialCode lookup: '{auth.denial_code}' → NOT FOUND in denial code reference → VIOLATION",
            )
            return [self._err(114, f"Authorization '{auth.id}': DenialCode '{auth.denial_code}' is not a registered denial code", trace=trace)]
        return []

    # Fires when: Authorization.End is before Authorization.Start
    def _rule_146(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        start = _parse_datetime(auth.start)
        end   = _parse_datetime(auth.end)
        if start is not None and end is not None and end < start:
            return [self._err(146, f"Authorization '{auth.id}': End must be >= Start",
                trace=(
                    f"Authorization.Start: '{auth.start}' → {start.strftime('%d/%m/%Y')}",
                    f"Authorization.End: '{auth.end}' → {end.strftime('%d/%m/%Y')}",
                    f"End < Start → VIOLATION",
                ))]
        return []

    # Fires when: the Prior.Request type is Cancellation and Activities are present
    def _rule_159(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        if pr_type is None:
            return []
        if pr_type == "Cancellation":
            if auth.activities:
                return [self._err(159, f"Authorization '{auth.id}': Activities must not be present when Prior.Request type is Cancellation",
                    trace=(
                        f"Prior.Request type: '{pr_type}' = Cancellation ✓",
                        f"Authorization has {len(auth.activities)} Activity(ies) → must be empty → VIOLATION",
                    ))]
        return []

    # Fires when: the Prior.Request type is Authorization or Extension but no Activities are present
    def _rule_160(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        if pr_type not in ("Authorization", "Extension"):
            return []
        if not auth.activities:
            return [self._err(160, f"Authorization '{auth.id}': At least one Activity is required when Prior.Request type is '{pr_type}'",
                trace=(
                    f"Prior.Request type: '{pr_type}' → requires at least one Activity ✓",
                    f"Authorization has 0 Activities → VIOLATION",
                ))]
        return []

    # Fires when: Authorization.Result is Denied or Partially Approved but DenialCode is missing
    def _rule_163(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        if auth.result not in ("Denied", "Partially Approved"):
            return []
        if not auth.denial_code or not auth.denial_code.strip():
            return [self._err(163, f"Authorization '{auth.id}': DenialCode is required when Result is '{auth.result}'",
                trace=(
                    f"Authorization.Result: '{auth.result}' → Denied/Partially Approved → requires DenialCode ✓",
                    f"Authorization.DenialCode: '{auth.denial_code}' → missing/empty → VIOLATION",
                ))]
        return []

    # Fires when: Authorization.IDPayer is already used by another Prior.Authorization transaction
    def _rule_166(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        if not auth.id_payer or not auth.id_payer.strip():
            return []
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None:
            return []
        if res.is_id_payer_used_by_other_claim(auth.id_payer, model.header.receiver_id, auth.id):
            return [self._err(166, f"Authorization '{auth.id}': IDPayer '{auth.id_payer}' is already used by another transaction",
                trace=(
                    f"Authorization.IDPayer: '{auth.id_payer}'",
                    f"ReceiverID: '{model.header.receiver_id}'",
                    f"DB lookup: IDPayer already used by a different Authorization.ID → VIOLATION",
                ))]
        return []

    # Fires when: ReceiverID is not HAAD and not a valid TPA for Prior.Authorization
    def _rule_169(self, model: pa.PriorAuthorization, res) -> list:
        receiver = model.header.receiver_id
        is_tpa = res.is_haad_tpa(receiver)
        if receiver != _HAAD_RECEIVER_ID and not is_tpa:
            trace = (
                f"ReceiverID: '{receiver}' → not HAAD",
                f"HAAD TPA lookup: '{receiver}' → NOT FOUND → VIOLATION",
            )
            return [self._err(169, f"Header.ReceiverID '{receiver}' must be HAAD or a valid TPA for Prior.Authorization", trace=trace)]
        return []

    # Fires when: Authorization.ID is missing or blank
    def _rule_178(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        if not auth.id or not auth.id.strip():
            return [self._err(178, f"Authorization.ID may not be empty",
                trace=("Authorization.ID: empty/null → VIOLATION",))]
        return []

    # Fires when: a Prior.Authorization response was already submitted for this Authorization.ID
    def _rule_181(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        if not res.prior_request_has_response(auth.id, model.header.sender_id):
            return []
        return [self._err(181, f"Authorization '{auth.id}': a response has already been submitted for this Prior.Request",
            trace=(
                f"Authorization.ID: '{auth.id}', SenderID: '{model.header.sender_id}'",
                f"DB lookup: a Prior.Authorization response already exists for this ID → VIOLATION",
            ))]

    # Fires when: Authorization.Start is after the earliest activity Start in the corresponding Prior.Request
    def _rule_236(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        start = _parse_datetime(auth.start)
        if start is None:
            return []
        pr_min = res.get_pr_min_activity_start(auth.id, model.header.sender_id)
        if pr_min is not None and start > pr_min:
            return [self._err(236, f"Authorization '{auth.id}': Start must be <= earliest activity Start in the Prior.Request",
                trace=(
                    f"Authorization.Start: '{auth.start}' → {start.strftime('%d/%m/%Y')}",
                    f"Earliest activity Start in Prior.Request: {pr_min.strftime('%d/%m/%Y')}",
                    f"Authorization.Start > PR activity Start → VIOLATION",
                ))]
        return []

    # Fires when: Activity.PaymentAmount > Activity.Net
    def _rule_241(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        for act in auth.activities:
            pa_amount = act.payment_amount
            if pa_amount is not None and pa_amount > act.net:
                return [self._err(241, f"Authorization '{auth.id}', Activity '{act.id}': PaymentAmount {pa_amount} must be <= Net {act.net}",
                    trace=(
                        f"Activity.PaymentAmount: {pa_amount}",
                        f"Activity.Net: {act.net}",
                        f"PaymentAmount > Net → VIOLATION",
                    ))]
        return []

    # Fires when: Activity.PaymentAmount < 0
    def _rule_242(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        for act in auth.activities:
            pa_amount = act.payment_amount
            if pa_amount is not None and pa_amount < 0:
                return [self._err(242, f"Authorization '{auth.id}', Activity '{act.id}': PaymentAmount must be >= 0",
                    trace=(
                        f"Activity.PaymentAmount: {pa_amount} < 0 → VIOLATION",
                    ))]
        return []

    # Fires when: Authorization Activity IDs contain IDs not found in the corresponding Prior.Request (type is Authorization/Extension/Prescription)
    def _rule_258(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        if pr_type not in ("Authorization", "Extension", "Prescription"):
            return []
        pa_ids = {act.id for act in auth.activities}
        pr_ids = res.get_pr_historical_activity_ids(auth.id, model.header.sender_id)
        if pr_ids is None:
            return []
        extra = pa_ids - pr_ids
        if extra:
            return [self._err(258, f"Authorization '{auth.id}': Activity IDs {sorted(extra)} not found in corresponding Prior.Request",
                trace=(
                    f"Prior.Request type: '{pr_type}' → Activities must match PR ✓",
                    f"Authorization Activity IDs: {sorted(pa_ids)}",
                    f"Prior.Request Activity IDs: {sorted(pr_ids)}",
                    f"Extra IDs not in PR: {sorted(extra)} → VIOLATION",
                ))]
        return []

    # Fires when: Authorization.IDPayer is present but Authorization.ID is not unique per sender
    def _rule_259(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        if not auth.id_payer or not auth.id_payer.strip():
            return []
        if not res.prior_auth_exists_for_id(auth.id, model.header.receiver_id):
            return []
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None:
            return []
        if not res.is_pr_authorization_id_unique(auth.id, model.header.sender_id):
            return [self._err(259, f"Authorization '{auth.id}': Authorization.ID must be unique per sender",
                trace=(
                    f"Authorization.IDPayer: '{auth.id_payer}' → present ✓",
                    f"Authorization.ID: '{auth.id}', SenderID: '{model.header.sender_id}'",
                    f"DB lookup: Authorization.ID not unique for this sender → VIOLATION",
                ))]
        return []

    # Fires when: Prior.Request type is Eligibility but Authorization contains Activities
    def _rule_266(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        if pr_type != "Eligibility":
            return []
        if auth.activities:
            return [self._err(266, f"Authorization '{auth.id}': Activities must not be present when Prior.Request type is Eligibility",
                trace=(
                    f"Prior.Request type: 'Eligibility' → no Activities allowed ✓",
                    f"Authorization has {len(auth.activities)} Activity(ies) → VIOLATION",
                ))]
        return []

    # Fires when: Prior.Request type is Status Inquiry but Authorization contains Activities
    def _rule_268(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        if pr_type != "Status Inquiry":
            return []
        if auth.activities:
            return [self._err(268, f"Authorization '{auth.id}': Activities must not be present when Prior.Request type is Status Inquiry",
                trace=(
                    f"Prior.Request type: 'Status Inquiry' → no Activities allowed ✓",
                    f"Authorization has {len(auth.activities)} Activity(ies) → VIOLATION",
                ))]
        return []

    # Fires when: Authorization/Extension PA has Result=Approved/Partially Approved/Not Required but IDPayer is missing
    def _rule_269(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        if pr_type is not None and pr_type not in ("Authorization", "Extension"):
            return []
        if auth.result in ("Approved", "Partially Approved", "Not Required"):
            if not auth.id_payer or not auth.id_payer.strip():
                return [self._err(269, f"Authorization '{auth.id}': IDPayer is required when Result is '{auth.result}'",
                    trace=(
                        f"Prior.Request type: '{pr_type}' ✓",
                        f"Authorization.Result: '{auth.result}' → approved/not-required ✓",
                        f"Authorization.IDPayer: '{auth.id_payer}' → missing/empty → VIOLATION",
                    ))]
        return []

    # Fires when: Prescription PA has Result=Approved/Partially Approved/Not Required but IDPayer is missing
    def _rule_270(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        if pr_type != "Prescription":
            return []
        if auth.result in ("Approved", "Partially Approved", "Not Required"):
            if not auth.id_payer or not auth.id_payer.strip():
                return [self._err(270, f"Authorization '{auth.id}': IDPayer is required for Prescription PA with Result '{auth.result}'",
                    trace=(
                        f"Prior.Request type: 'Prescription' ✓",
                        f"Authorization.Result: '{auth.result}' → approved/not-required ✓",
                        f"Authorization.IDPayer: '{auth.id_payer}' → missing/empty → VIOLATION",
                    ))]
        return []

    # Fires when: any DenialCode (Authorization or Activity level) is not active on the transaction date (from 2023-01-30)
    def _rule_346(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 1, 30):
            return []
        auth = model.authorization
        tx_str = tx.strftime("%d/%m/%Y")
        if auth.denial_code and auth.denial_code.strip():
            if not res.is_denial_code_valid_on_date(auth.denial_code, tx):
                trace = (
                    f"Authorization DenialCode date lookup: '{auth.denial_code}' on {tx_str} → NOT FOUND or inactive → VIOLATION",
                )
                return [self._err(346, f"Authorization '{auth.id}': DenialCode '{auth.denial_code}' is not active on transaction date", trace=trace)]
        for act in auth.activities:
            if act.denial_code and act.denial_code.strip():
                if not res.is_denial_code_valid_on_date(act.denial_code, tx):
                    trace = (
                        f"Activity DenialCode date lookup: '{act.denial_code}' on {tx_str} → NOT FOUND or inactive → VIOLATION",
                    )
                    return [self._err(346, f"Authorization '{auth.id}', Activity '{act.id}': DenialCode '{act.denial_code}' is not active on transaction date", trace=trace)]
        return []

    # Fires when: (INACTIVE) Activity.Code is not a valid ICD9 code
    def _rule_64(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            icd9_ok = res.is_valid_icd9_code(act.code)
            if not icd9_ok:
                trace = (
                    f"ICD9 lookup: code = '{act.code}' → NOT FOUND in HIB_MDM.ICD09 (or IsActive ≠ 1) → VIOLATION",
                    f"Note: codes are case-sensitive. Verify exact casing and IsActive flag in the DB.",
                )
                errors.append(self._inactive_err(64, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid ICD9 code", trace=trace))
        return errors

    # Fires when: (INACTIVE) Activity.Type=3 and Activity.Code contains '-'
    def _rule_113(self, model: pa.PriorAuthorization, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 3 and "-" in act.code:
                errors.append(self._inactive_err(113, f"Authorization '{auth.id}', Activity '{act.id}': Code must not contain modifier when Activity.Type=3 (CPT)",
                    trace=(
                        f"Authorization.ID: '{auth.id}', Activity.ID: '{act.id}', Activity.Type: 3 (CPT)",
                        f"Activity.Code: '{act.code}' → contains '-' modifier → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2011-01-01 and this Authorization.ID is a duplicate in the file
    def _rule_161(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 1, 1):
            return []
        auth = model.authorization
        try:
            if not res.is_pr_authorization_id_unique(auth.id, model.header.sender_id):
                return [self._inactive_err(161, f"Authorization ID '{auth.id}' must be unique within a file",
                    trace=(
                        f"Authorization.ID: '{auth.id}'",
                        f"SenderID: '{model.header.sender_id}'",
                        f"ID already exists in submitted file → VIOLATION",
                    ))]
        except Exception:
            pass
        return []

    # Fires when: (INACTIVE) TransactionDate >= 2011-01-01 and Authorization.Start is null/empty
    def _rule_164(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 1, 1):
            return []
        auth = model.authorization
        if not auth.start or not auth.start.strip():
            return [self._inactive_err(164, f"Authorization '{auth.id}': Start may not be null",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"Authorization.Start: '{auth.start}' → empty or None → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) TransactionDate >= 2011-01-01 and Authorization.End is null/empty
    def _rule_165(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 1, 1):
            return []
        auth = model.authorization
        if not auth.end or not auth.end.strip():
            return [self._inactive_err(165, f"Authorization '{auth.id}': End may not be null",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"Authorization.End: '{auth.end}' → empty or None → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) TransactionDate >= 2011-06-15 and Authorization.Start > TransactionDate
    def _rule_180(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        auth = model.authorization
        auth_start = _parse_datetime(auth.start)
        if auth_start is not None and auth_start > tx:
            return [self._inactive_err(180, f"Authorization '{auth.id}': Start '{auth.start}' must be before Header.TransactionDate",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"Authorization.Start: '{auth.start}' → {auth_start}",
                    f"Header.TransactionDate: '{model.header.transaction_date}' → {tx}",
                    f"Authorization.Start > TransactionDate → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) TransactionDate >= 2014-09-01 and Activity.PaymentAmount=0 but Quantity!=0
    def _rule_237(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 9, 1):
            return []
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.payment_amount == 0 and act.quantity is not None and act.quantity != 0:
                errors.append(self._inactive_err(237, f"Authorization '{auth.id}', Activity '{act.id}': Quantity must be zero when PaymentAmount is zero",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.PaymentAmount: {act.payment_amount} → 0",
                        f"Activity.Quantity: {act.quantity} → not 0 → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Corresponding PriorRequest type is Prescription/Authorization and Authorization.DenialCode is set
    def _rule_240(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 9, 1):
            return []
        auth = model.authorization
        try:
            pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        except Exception:
            return []
        if pr_type not in ("Prescription", "Authorization"):
            return []
        if auth.denial_code and auth.denial_code.strip():
            return [self._inactive_err(240, f"Authorization '{auth.id}': DenialCode must be empty for this transaction type",
                trace=(
                    f"Authorization.ID: '{auth.id}', PriorRequest.Type: '{pr_type}'",
                    f"Authorization.DenialCode: '{auth.denial_code}' → must be empty → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) Corresponding PriorRequest type is Prescription/Authorization and no Activities present
    def _rule_257(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        try:
            pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        except Exception:
            return []
        if pr_type not in ("Prescription", "Authorization"):
            return []
        if len(auth.activities) < 1:
            return [self._inactive_err(257, f"Authorization '{auth.id}': At least one Activity must be present for this request type",
                trace=(
                    f"Authorization.ID: '{auth.id}', PriorRequest.Type: '{pr_type}'",
                    f"Activity count: 0 → requires at least 1 → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) Result rules conflict with PriorRequest type (Eligibility/Cancellation need result; Prescription/Authorization must not have result)
    def _rule_264(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        try:
            pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        except Exception:
            return []
        if pr_type in ("Eligibility", "Cancellation"):
            if not auth.result or not auth.result.strip():
                return [self._inactive_err(264, f"Authorization '{auth.id}': Result may not be empty for type '{pr_type}'",
                    trace=(
                        f"Authorization.ID: '{auth.id}', PriorRequest.Type: '{pr_type}'",
                        f"Authorization.Result: '{auth.result}' → empty or None → VIOLATION",
                    ))]
        elif pr_type in ("Prescription", "Authorization"):
            if auth.result and auth.result.strip():
                return [self._inactive_err(264, f"Authorization '{auth.id}': Result must not have value for type '{pr_type}'",
                    trace=(
                        f"Authorization.ID: '{auth.id}', PriorRequest.Type: '{pr_type}'",
                        f"Authorization.Result: '{auth.result}' → must be empty for this type → VIOLATION",
                    ))]
        return []

    # Fires when: (INACTIVE) PriorRequest type is not Prescription but Authorization.Limit is set
    def _rule_267(self, model: pa.PriorAuthorization, res) -> list:
        auth = model.authorization
        try:
            pr_type = res.get_prior_request_type(auth.id, model.header.sender_id)
        except Exception:
            return []
        if pr_type == "Prescription":
            return []
        if auth.limit is not None:
            return [self._inactive_err(267, f"Authorization '{auth.id}': Limit must not have value for type '{pr_type}'",
                trace=(
                    f"Authorization.ID: '{auth.id}', PriorRequest.Type: '{pr_type}' (not Prescription)",
                    f"Authorization.Limit: {auth.limit} → must be None for this type → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) TransactionDate >= 2024-08-05 and Activity.Net != Activity.PaymentAmount but result is not "No"
    def _rule_367(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2024, 8, 5):
            return []
        auth = model.authorization
        errors = []
        for act in auth.activities:
            if act.net is not None and act.payment_amount is not None:
                if act.net != act.payment_amount and auth.result != "No":
                    errors.append(self._inactive_err(367, f"Authorization '{auth.id}', Activity '{act.id}': Result must be 'No' when Activity.Net != Activity.PaymentAmount",
                        trace=(
                            f"Activity.ID: '{act.id}', Activity.Net: {act.net}, Activity.PaymentAmount: {act.payment_amount}",
                            f"Authorization.Result: '{auth.result}' → Net ≠ PaymentAmount so Result must be 'No' → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2024-08-05 and Activity.Net == Activity.PaymentAmount but result is not "Yes"
    def _rule_368(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2024, 8, 5):
            return []
        auth = model.authorization
        errors = []
        for act in auth.activities:
            if act.net is not None and act.payment_amount is not None:
                if act.net == act.payment_amount and auth.result != "Yes":
                    errors.append(self._inactive_err(368, f"Authorization '{auth.id}', Activity '{act.id}': Result must be 'Yes' when Activity.Net = Activity.PaymentAmount",
                        trace=(
                            f"Activity.ID: '{act.id}', Activity.Net: {act.net}, Activity.PaymentAmount: {act.payment_amount}",
                            f"Authorization.Result: '{auth.result}' → Net = PaymentAmount so Result must be 'Yes' → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2025-06-01, Trade Drug activity with UPP markup, but SenderID not in allowed list
    def _rule_379(self, model: pa.PriorAuthorization, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2025, 6, 1):
            return []
        sender = model.header.sender_id
        if sender in ("D001", "D002", "D003", "D004"):
            return []
        auth = model.authorization
        _ALLOWED_PRICE_DIFF_PCT = 45.0
        for act in auth.activities:
            if act.type != 5 or act.net <= 0:
                continue
            try:
                pkg_markup_str = res.get_pkg_markup(act.code)
            except Exception:
                continue
            if not pkg_markup_str:
                continue
            try:
                pkg_markup = float(pkg_markup_str)
            except ValueError:
                continue
            if pkg_markup <= 0:
                continue
            if act.quantity and act.quantity != 0:
                unit_net = act.net / act.quantity
                if abs(unit_net - pkg_markup) <= (pkg_markup / 100.0) * _ALLOWED_PRICE_DIFF_PCT:
                    return [self._inactive_err(379, f"Authorization '{auth.id}': Header.SenderID must be D001, D002, D003, or D004 when activities include UPP markup prices",
                        trace=(
                            f"Authorization.ID: '{auth.id}', Activity.Code: '{act.code}'",
                            f"SenderID: '{sender}' → not in D001-D004",
                            f"Unit Net: {unit_net:.4f}, Package Markup: {pkg_markup:.4f}, Tolerance: {_ALLOWED_PRICE_DIFF_PCT}%",
                            f"Unit net within UPP markup tolerance but sender not in allowed set → VIOLATION",
                        ))]
        return []


# ── PriorRequest rules ─────────────────────────────────────────────────────────

class _PriorRequestValidator(_BaseValidator):
    TRANSACTION = "Prior.Request"

    _RULE_DESCRIPTIONS = {
        "5":   "(INACTIVE) Resubmission exists but Attachment is missing",
        "9":   "Header.RecordCount is not 1 (Prior.Request always contains exactly one Authorization)",
        "15":  "ReceiverID is HAAD/TPA and Authorization.PayerID is not a valid active insurer",
        "30":  "Header.DispositionFlag is not PTE_SUBMIT, PTE_VALIDATE_ONLY, or PTE_RESPONSE",
        "34":  "Authorization.Type is not a valid Prior.Request type",
        "38":  "(INACTIVE) Authorization type is Authorization, TransactionDate >= 2014-06-01, Encounter.End is null, and Encounter.Type is 3 or 4",
        "40":  "Authorization.EmiratesIDNumber is empty or fails Luhn/format check",
        "44":  "(INACTIVE) Activity.Observation.Type is null",
        "45":  "Observation.Type='LOINC' and the code is not an active LOINC code",
        "48":  "(INACTIVE) Observation.Type is LOINC and Observation.Value is not numeric (optionally < or >)",
        "51":  "(INACTIVE) Diagnosis.Type is not a valid type",
        "52":  "(INACTIVE) Diagnosis.Code is not a valid ICD9/ICD10 code (various conditions)",
        "58":  "SenderID is not a valid provider, payer, or TPA",
        "61":  "Header.TransactionDate does not match today's date",
        "62":  "any Activity.Type is outside the allowed set {3,4,5,6,8,9}",
        "63":  "any Activity.Net < 0",
        "64":  "(INACTIVE) Activity.Code is not a valid ICD9 code",
        "65":  "Activity.Type is CPT/HCPCS-compatible but code is not a valid CPT or HCPCS code",
        "66":  "Activity.Type=2 (Drug) and code is not a valid trade or generic drug code",
        "67":  "Activity.Type=10 (Dental) and code is not a valid USCLS dental code",
        "68":  "Activity.ID is duplicated within the Authorization",
        "69":  "Activity.Quantity is present and <= 0",
        "70":  "Activity.Quantity is present and is not a whole number",
        "72":  "Encounter.Type is present but not a valid encounter type (1-13)",
        "75":  "Diagnosis.Type is not a valid diagnosis type",
        "76":  "(INACTIVE) Activity.Type != 10 and Activity.Net is null/empty",
        "80":  "(INACTIVE) TransactionDate >= 2013-06-01, Encounter.Type is 3 or 4, and Activity.Start is null",
        "88":  "Activity.Start is before Encounter.Start",
        "89":  "(INACTIVE) TransactionDate >= 2010-10-01 and Observation.Code is not in the tooth registry",
        "90":  "Observation.Type is not in the allowed observation type set",
        "91":  "any Activity.DenialCode is not a registered denial code",
        "104": "Encounter.Start or any Activity.Start is before 01/01/1900",
        "113": "Observation.Type='LOINC' and code is not a registered LOINC code",
        "120": "Activity.Type=5 (Service) and code is not a valid service code",
        "127": "Activity.Clinician is present but not a valid active clinician license",
        "138": "(INACTIVE) TransactionDate >= 2011-06-15 and Activity.Type=9 but Encounter.Type is not 3 or 4",
        "143": "(INACTIVE) TransactionDate >= 2011-06-15 and Encounter.End > TransactionDate",
        "144": "Activity.OrderingClinician is present but not a valid active clinician license",
        "146": "Encounter.End is before Encounter.Start",
        "147": "any Diagnosis.Code is not a valid ICD-10 code",
        "156": "Authorization type is Authorization or Extension but no Activities are present",
        "157": "(INACTIVE) TransactionDate >= 2011-01-01 and Authorization.PayerID != Header.ReceiverID",
        "160": "Authorization/Extension type has no Activities (alternate path check)",
        "161": "(INACTIVE) TransactionDate >= 2011-01-01 and Authorization.ID is a duplicate in the file",
        "162": "Authorization type is Cancellation but Activities are present",
        "167": "ReceiverID is not HAAD and not a valid TPA (from 2014-10-01)",
        "168": "SenderID is not a valid provider, payer, or TPA (from 2014-10-01)",
        "174": "(INACTIVE) TransactionDate >= 2011-06-15 and Resubmission.Type not Correction/Complaint but IDPayer is set",
        "175": "Cancellation type has no prior Authorization/Extension response",
        "176": "Extension type but no approved Prior.Authorization exists for this ID",
        "177": "Status Inquiry type but no Prior.Authorization response exists for this ID",
        "181": "Authorization.ID is already used by this sender (duplicate Prior.Request)",
        "182": "Authorization/Extension type has no Diagnoses",
        "186": "Authorization/Extension type has no or invalid Encounter.FacilityID",
        "201": "Activity.Type=6 and code is not a valid DRG code",
        "202": "DxInfo.Type is not in the valid DxInfo type set",
        "204": "Resubmission.Type is not a valid value (correction/internal complaint/legacy)",
        "213": "correction resubmission has no prior submission to correct",
        "238": "Activity.Type=8 and code is not a valid trade or generic drug code",
        "239": "(INACTIVE) TransactionDate >= 2014-12-01 and Diagnosis.DxInfo.Type is not POA or Year of Onset",
        "243": "Activity.Type=3 (CPT) and code is in CPT exclusion list 1",
        "244": "Activity.Type=4 (HCPCS) and code is in exclusion list 4",
        "245": "Activity.Type=5 (Service) and code is in service exclusion list 6",
        "248": "Activity.Type=9 and code is not a valid service code",
        "249": "(INACTIVE) Authorization.Type is Authorization and Encounter.Type is 7",
        "250": "Authorization.MemberID is empty",
        "251": "Authorization.PayerID is empty (from 2015-01-01)",
        "252": "Authorization.PayerID is not a valid payer license (non-@ values)",
        "253": "Authorization/Extension type has an Encounter but Encounter.Start is missing",
        "254": "Authorization/Extension type has an Encounter but Encounter.Type is missing",
        "255": "Activity.Start is after Encounter.End",
        "256": "Encounter.FacilityID is present but not a registered facility",
        "257": "Authorization/Extension type has no DateOrdered",
        "258": "Cancellation type but no existing Prior.Authorization found for this ID",
        "259": "Status Inquiry type but not all prior requests have been responded to",
        "260": "Prescription type has no Activities",
        "261": "Prescription type has Activities with types outside {2,3,8,9}",
        "262": "(INACTIVE) Type is Prescription/Authorization, Observation.Type is not Universal Dental/Flags, and Observation.Value is null/empty",
        "263": "(INACTIVE) Type is Prescription/Authorization, Observation.Type is not Universal Dental/Flags, and Observation.ValueType is null/empty",
        "265": "Eligibility type has Activities present",
        "296": "Activity.Type=3 (CPT) and code is in HCPCS exclusion list 2",
        "297": "Encounter.FacilityID is present but not an active facility",
        "298": "Activity.Clinician is present but not an active clinician",
        "299": "Activity.OrderingClinician is present but not an active clinician",
        "300": "Authorization/Extension Encounter.Type is not a valid encounter type",
        "302": "any Diagnosis.Code is not an active ICD-10 code (active-check variant)",
        "304": "a Resubmission is present but Resubmission.Comment is empty",
        "305": "Authorization type is Cancellation but no Resubmission element is present",
        "306": "(INACTIVE) TransactionDate >= 2021-11-01, Activity.Code is 89-93, and Encounter.Type is not 3 or 4",
        "307": "Observation.Type='Text' and Observation.Value is empty",
        "313": "Observation.Type='Universal Dental' and Observation.ValueDate is missing",
        "314": "Observation.Type='Universal Dental' and Observation.Value is missing",
        "322": "Authorization/Extension Encounter.Start is after TransactionDate (from 2021-01-01)",
        "324": "Authorization.DateOrdered is after TransactionDate (from 2021-01-01)",
        "344": "any Activity.DenialCode is not active on the transaction date (from 2023-01-01)",
        "345": "Extension type requires an approved PA before TransactionDate but none found (from 2023-01-01)",
        "357": "Activity.Type=4 (HCPCS) uses a pure CPT code (from 2023-07-01)",
        "358": "Activity.Type=3 (CPT) uses a pure HCPCS code (from 2023-07-01)",
        "359": "Universal Dental Observation.ValueDate is more than 1 day from Activity.Start (from 2023-07-01)",
        "363": "any Activity.Start is after TransactionDate (from 2023-10-01)",
        "364": "Authorization.DateOrdered is after Encounter.Start (from 2023-10-01)",
        "370": "(INACTIVE) Pilot DRG facility, Encounter.Type 5/6, Drug activity with net not 0 or > 500",
        "371": "(INACTIVE) Pilot DRG facility, Encounter.Type 5/6, Drug activity with net < 0",
        "372": "(INACTIVE) Pilot DRG facility, Encounter.Type 5/6, HCPCS activity net != (TotalAmount - 1500*qty)",
        "377": "(INACTIVE) TransactionDate >= 2025-06-01, Trade Drug activity with UPP markup within tolerance, but ReceiverID not in (D001-D004)",
        "378": "Authorization/Extension type has no Encounter element (from 2024-03-01)",
        "380": "(INACTIVE) TransactionDate >= 2025-06-01, Trade Drug activity where unit net >= both Package Markup and Price to Public",
        "382": "Encounter.Start is more than 365 days before TransactionDate (from 2024-06-01)",
        "383": "Authorization/Extension Encounter.Start is before 01/01/2006 (from 2024-06-01)",
    }

    _PQ_ALLOWED_FLAGS = frozenset({"PTE_SUBMIT", "PTE_VALIDATE_ONLY", "PTE_RESPONSE"})
    _PQ_ALLOWED_ACTIVITY_TYPES = frozenset({3, 4, 5, 6, 8, 9})
    _PQ_VALID_REQUEST_TYPES = frozenset({
        "Eligibility", "Authorization", "Cancellation", "Extension", "Status Inquiry", "Prescription"
    })
    _PQ_VALID_ENC_TYPES = frozenset(range(1, 14))
    _PQ_VALID_DX_TYPES  = frozenset({"Principal", "Secondary", "Admitting", "ReasonForVisit", "Discharge"})
    _PQ_RESUBMISSION_TYPES = frozenset({"correction", "internal complaint", "legacy"})

    def _rules(self):
        return [
            self._rule_5,   self._rule_9,   self._rule_15,  self._rule_30,  self._rule_34,
            self._rule_38,  self._rule_40,  self._rule_44,  self._rule_45,  self._rule_48,
            self._rule_51,  self._rule_52,  self._rule_58,  self._rule_61,  self._rule_62,
            self._rule_63,  self._rule_64,  self._rule_65,  self._rule_66,  self._rule_67,
            self._rule_68,  self._rule_69,  self._rule_70,  self._rule_72,  self._rule_75,
            self._rule_76,  self._rule_80,  self._rule_88,  self._rule_89,  self._rule_90,
            self._rule_91,  self._rule_104, self._rule_113, self._rule_120, self._rule_127,
            self._rule_138, self._rule_143, self._rule_144, self._rule_146, self._rule_147,
            self._rule_156, self._rule_157, self._rule_160, self._rule_161, self._rule_162,
            self._rule_167, self._rule_168, self._rule_174, self._rule_175, self._rule_176,
            self._rule_177, self._rule_181, self._rule_182, self._rule_186, self._rule_201,
            self._rule_202, self._rule_204, self._rule_213, self._rule_238, self._rule_239,
            self._rule_243, self._rule_244, self._rule_245, self._rule_248, self._rule_249,
            self._rule_250, self._rule_251, self._rule_252, self._rule_253, self._rule_254,
            self._rule_255, self._rule_256, self._rule_257, self._rule_258, self._rule_259,
            self._rule_260, self._rule_261, self._rule_262, self._rule_263, self._rule_265,
            self._rule_296, self._rule_297, self._rule_298, self._rule_299, self._rule_300,
            self._rule_302, self._rule_304, self._rule_305, self._rule_306, self._rule_307,
            self._rule_313, self._rule_314, self._rule_322, self._rule_324, self._rule_344,
            self._rule_345, self._rule_357, self._rule_358, self._rule_359, self._rule_363,
            self._rule_364, self._rule_370, self._rule_371, self._rule_372, self._rule_377,
            self._rule_378, self._rule_380, self._rule_382, self._rule_383,
        ]

    # Fires when: Header.RecordCount is not 1 (Prior.Request always contains exactly one Authorization)
    def _rule_9(self, model: pq.PriorRequest, res) -> list:
        if model.header.record_count != 1:
            return [self._err(9, f"Header.RecordCount is {model.header.record_count} but Prior.Request always contains 1 Authorization",
                trace=(
                    f"Header.RecordCount: {model.header.record_count}",
                    f"Expected: exactly 1 Authorization element",
                    f"Count mismatch → VIOLATION",
                ))]
        return []

    # Fires when: ReceiverID is HAAD/TPA and Authorization.PayerID is not a valid active insurer
    def _rule_15(self, model: pq.PriorRequest, res) -> list:
        receiver = model.header.receiver_id
        recv_is_tpa = res.is_haad_tpa(receiver)
        if receiver != _HAAD_RECEIVER_ID and not recv_is_tpa:
            return []
        payer_id = model.authorization.payer_id
        if not payer_id or payer_id.startswith("@"):
            return []
        payer_ok = res.is_active_insurer(payer_id)
        if not payer_ok:
            trace = (
                f"Condition 1 — ReceiverID: '{receiver}' → {'HAAD' if receiver == _HAAD_RECEIVER_ID else 'HAAD TPA'} ✓ → rule applies",
                f"Condition 2 — PayerID: '{payer_id}' → active insurer lookup → NOT FOUND or inactive → VIOLATION",
            )
            return [self._err(15, f"Authorization '{model.authorization.id}': PayerID '{payer_id}' is not a valid insurer license number", trace=trace)]
        return []

    # Fires when: Header.DispositionFlag is not PTE_SUBMIT, PTE_VALIDATE_ONLY, or PTE_RESPONSE
    def _rule_30(self, model: pq.PriorRequest, res) -> list:
        flag = model.header.disposition_flag
        if flag not in self._PQ_ALLOWED_FLAGS:
            return [self._err(30, f"DispositionFlag must be PTE_SUBMIT, PTE_VALIDATE_ONLY, or PTE_RESPONSE (got '{flag}')",
                trace=(
                    f"Header.DispositionFlag: '{flag}'",
                    f"Allowed values: {sorted(self._PQ_ALLOWED_FLAGS)}",
                    f"Value not in allowed set → VIOLATION",
                ))]
        return []

    # Fires when: Authorization.Type is not a valid Prior.Request type
    def _rule_34(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type not in self._PQ_VALID_REQUEST_TYPES:
            return [self._err(34, f"Authorization.Type '{auth.type}' is not a valid Prior.Request type",
                trace=(
                    f"Authorization.Type: '{auth.type}'",
                    f"Valid Prior.Request types: {sorted(self._PQ_VALID_REQUEST_TYPES)}",
                    f"Type not in valid set → VIOLATION",
                ))]
        return []

    # Fires when: Authorization.EmiratesIDNumber is empty or fails Luhn/format check
    def _rule_40(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if not auth.emirates_id_number or not auth.emirates_id_number.strip():
            return [self._err(40, f"Authorization '{auth.id}': EmiratesIDNumber may not be empty",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"EmiratesIDNumber: '{auth.emirates_id_number}' → empty or whitespace → VIOLATION",
                ))]
        if auth.emirates_id_number not in _DUMMY_EMIRATES_IDS and not _is_valid_emirates_id(auth.emirates_id_number):
            return [self._err(40, f"Authorization '{auth.id}': EmiratesIDNumber '{auth.emirates_id_number}' is not a valid Emirates ID",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"EmiratesIDNumber: '{auth.emirates_id_number}'",
                    f"Not in dummy IDs list and failed Luhn/format check → VIOLATION",
                ))]
        return []

    # Fires when: Observation.Type='LOINC' and the code is not an active LOINC code
    def _rule_45(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            for obs in act.observations:
                if obs.type == "LOINC":
                    loinc_ok = res.is_active_loinc_code(obs.code)
                    if not loinc_ok:
                        trace = (
                            f"Observation.Type: 'LOINC' ✓",
                            f"LOINC lookup: '{obs.code}' → NOT FOUND or inactive → VIOLATION",
                        )
                        errors.append(self._err(45,
                            f"Authorization '{auth.id}', Activity '{act.id}': "
                            f"Observation.Code '{obs.code}' does not exist as an active LOINC code", trace=trace))
        return errors

    # Fires when: SenderID is not a valid provider, payer, or TPA
    def _rule_58(self, model: pq.PriorRequest, res) -> list:
        sender = model.header.sender_id
        is_provider = res.is_any_provider(sender)
        is_payer = res.is_haad_payer(sender)
        is_tpa = res.is_haad_tpa(sender)
        if not (is_provider or is_payer or is_tpa):
            trace = (
                f"SenderID: '{sender}' → provider lookup → {'YES' if is_provider else 'NO'}",
                f"SenderID: '{sender}' → HAAD payer lookup → {'YES' if is_payer else 'NO'}",
                f"SenderID: '{sender}' → HAAD TPA lookup → {'YES' if is_tpa else 'NO'}",
                f"None of provider/payer/TPA matched → VIOLATION",
            )
            return [self._err(58, f"Header.SenderID '{sender}' must be a valid provider, payer, or TPA for Prior.Request", trace=trace)]
        return []

    # Fires when: Header.TransactionDate does not match today's date
    def _rule_61(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None:
            return []
        if tx.date() != datetime.now().date():
            return [self._err(61, f"Header.TransactionDate '{model.header.transaction_date}' must match today's date",
                trace=(
                    f"Header.TransactionDate: '{model.header.transaction_date}' → parsed date: {tx.date()}",
                    f"Today's date: {datetime.now().date()}",
                    f"Date mismatch → VIOLATION",
                ))]
        return []

    # Fires when: any Activity.Type is outside the allowed set {3,4,5,6,8,9}
    def _rule_62(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type not in self._PQ_ALLOWED_ACTIVITY_TYPES:
                errors.append(self._err(62, f"Authorization '{auth.id}', Activity '{act.id}': Type {act.type} is not allowed in Prior.Request",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Type: {act.type}",
                        f"Allowed activity types: {sorted(self._PQ_ALLOWED_ACTIVITY_TYPES)}",
                        f"Type not in allowed set → VIOLATION",
                    )))
        return errors

    # Fires when: any Activity.Net < 0
    def _rule_63(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.net < 0:
                errors.append(self._err(63, f"Authorization '{auth.id}', Activity '{act.id}': Net {act.net} must be >= 0",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Net: {act.net}",
                        f"Net is negative → VIOLATION",
                    )))
        return errors

    # Fires when: Activity.Type is CPT/HCPCS-compatible but code is not a valid CPT or HCPCS code
    def _rule_65(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type in (1, 3, 4, 5, 6, 8, 9):
                cpt_ok = res.is_valid_cpt_code(act.code)
                hcpcs_ok = res.is_valid_hcpcs_code(act.code)
                if not cpt_ok and not hcpcs_ok:
                    trace = (
                        f"Condition 1 — Activity.Type: {act.type} → CPT/HCPCS-compatible ✓",
                        f"Condition 2 — CPT lookup: '{act.code}' → {'FOUND ✓' if cpt_ok else 'NOT FOUND'}",
                        f"Condition 3 — HCPCS lookup: '{act.code}' → {'FOUND ✓' if hcpcs_ok else 'NOT FOUND'}",
                        f"Neither CPT nor HCPCS match → VIOLATION",
                    )
                    errors.append(self._err(65, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid CPT/HCPCS code", trace=trace))
        return errors

    # Fires when: Activity.Type=2 (Drug) and code is not a valid trade or generic drug code
    def _rule_66(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 2:
                trade_ok = res.is_valid_trade_drug(act.code)
                generic_ok = res.is_valid_generic_drug(act.code)
                if not trade_ok and not generic_ok:
                    trace = (
                        f"Condition 1 — Activity.Type: 2 (Drug) ✓",
                        f"Condition 2 — Trade drug lookup: '{act.code}' → {'FOUND ✓' if trade_ok else 'NOT FOUND'}",
                        f"Condition 3 — Generic drug lookup: '{act.code}' → {'FOUND ✓' if generic_ok else 'NOT FOUND'}",
                        f"Neither trade nor generic drug match → VIOLATION",
                    )
                    errors.append(self._err(66, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid drug code", trace=trace))
        return errors

    # Fires when: Activity.Type=10 (Dental) and code is not a valid USCLS dental code
    def _rule_67(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 10:
                dental_ok = res.is_valid_dental_code(act.code)
                if not dental_ok:
                    trace = (
                        f"Condition 1 — Activity.Type: 10 (Dental/USCLS) ✓",
                        f"Condition 2 — Dental (USCLS) code lookup: '{act.code}' → NOT FOUND → VIOLATION",
                    )
                    errors.append(self._err(67, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid dental code", trace=trace))
        return errors

    # Fires when: Activity.ID is duplicated within the Authorization
    def _rule_68(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        seen = set()
        for act in auth.activities:
            if act.id in seen:
                errors.append(self._err(68, f"Authorization '{auth.id}', Activity '{act.id}': Activity ID is duplicated",
                    trace=(
                        f"Authorization.ID: '{auth.id}'",
                        f"Activity.ID: '{act.id}' → already seen in this Authorization → VIOLATION",
                    )))
            seen.add(act.id)
        return errors

    # Fires when: Activity.Quantity is present and <= 0
    def _rule_69(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            qty = act.quantity
            if qty is not None and qty <= 0:
                errors.append(self._err(69, f"Authorization '{auth.id}', Activity '{act.id}': Quantity must be > 0",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Quantity: {qty}",
                        f"Quantity is present and <= 0 → VIOLATION",
                    )))
        return errors

    # Fires when: Activity.Quantity is present and is not a whole number
    def _rule_70(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            qty = act.quantity
            if qty is not None and qty != int(qty):
                errors.append(self._err(70, f"Authorization '{auth.id}', Activity '{act.id}': Quantity must be a whole number",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Quantity: {qty}",
                        f"Quantity has fractional part ({qty} ≠ {int(qty)}) → VIOLATION",
                    )))
        return errors

    # Fires when: Encounter.Type is present but not a valid encounter type (1-13)
    def _rule_72(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        enc = auth.encounter
        if enc is None:
            return []
        if enc.type is not None and enc.type not in self._PQ_VALID_ENC_TYPES:
            return [self._err(72, f"Authorization '{auth.id}': Encounter.Type {enc.type} is not a valid encounter type",
                trace=(
                    f"Authorization.ID: '{auth.id}', Encounter.Type: {enc.type}",
                    f"Valid encounter types: {sorted(self._PQ_VALID_ENC_TYPES)}",
                    f"Type not in valid set → VIOLATION",
                ))]
        return []

    # Fires when: Diagnosis.Type is not a valid diagnosis type
    def _rule_75(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for dx in auth.diagnoses:
            if dx.type not in self._PQ_VALID_DX_TYPES:
                errors.append(self._err(75, f"Authorization '{auth.id}': Diagnosis.Type '{dx.type}' is not a valid diagnosis type",
                    trace=(
                        f"Diagnosis.Code: '{dx.code}', Diagnosis.Type: '{dx.type}'",
                        f"Valid diagnosis types: {sorted(self._PQ_VALID_DX_TYPES)}",
                        f"Type not in valid set → VIOLATION",
                    )))
        return errors

    # Fires when: Activity.Start is before Encounter.Start
    def _rule_88(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            start = _parse_datetime(act.start) if act.start else None
            if start is None:
                continue
            enc_start = _parse_datetime(auth.encounter.start) if auth.encounter and auth.encounter.start else None
            if enc_start is not None and start < enc_start:
                errors.append(self._err(88, f"Authorization '{auth.id}', Activity '{act.id}': Start must be >= Encounter.Start",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Start: '{act.start}' → {start}",
                        f"Encounter.Start: '{auth.encounter.start}' → {enc_start}",
                        f"Activity.Start < Encounter.Start → VIOLATION",
                    )))
        return errors

    # Fires when: Observation.Type is not in the allowed observation type set
    def _rule_90(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            for obs in act.observations:
                if obs.type not in _VALID_OBSERVATION_TYPES:
                    errors.append(self._err(90, f"Authorization '{auth.id}', Activity '{act.id}': Observation.Type '{obs.type}' is not valid",
                        trace=(
                            f"Activity.ID: '{act.id}', Observation.Type: '{obs.type}'",
                            f"Valid observation types: {sorted(_VALID_OBSERVATION_TYPES)}",
                            f"Type not in valid set → VIOLATION",
                        )))
        return errors

    # Fires when: any Activity.DenialCode is not a registered denial code
    def _rule_91(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            dc = getattr(act, 'denial_code', None)
            if dc:
                code_ok = res.is_valid_denial_code(dc)
                if not code_ok:
                    trace = (
                        f"Activity DenialCode lookup: '{dc}' → NOT FOUND in denial code reference → VIOLATION",
                    )
                    errors.append(self._err(91, f"Authorization '{auth.id}', Activity '{act.id}': DenialCode '{dc}' is not a registered denial code", trace=trace))
        return errors

    # Fires when: Encounter.Start or any Activity.Start is before 01/01/1900
    def _rule_104(self, model: pq.PriorRequest, res) -> list:
        _min = datetime(1900, 1, 1)
        errors = []
        auth = model.authorization
        if auth.encounter:
            enc_start = _parse_datetime(auth.encounter.start) if auth.encounter.start else None
            if enc_start is not None and enc_start <= _min:
                errors.append(self._err(104, f"Authorization '{auth.id}': Encounter.Start cannot be before 01/01/1900",
                    trace=(
                        f"Authorization.ID: '{auth.id}', Encounter.Start: '{auth.encounter.start}' → {enc_start}",
                        f"Minimum allowed date: {_min.date()}",
                        f"Encounter.Start is on or before minimum → VIOLATION",
                    )))
        for act in auth.activities:
            act_start = _parse_datetime(act.start) if act.start else None
            if act_start is not None and act_start <= _min:
                errors.append(self._err(104, f"Authorization '{auth.id}', Activity '{act.id}': Start cannot be before 01/01/1900",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Start: '{act.start}' → {act_start}",
                        f"Minimum allowed date: {_min.date()}",
                        f"Activity.Start is on or before minimum → VIOLATION",
                    )))
        return errors

    # Fires when: Observation.Type='LOINC' and code is not a registered LOINC code
    def _rule_113(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            for obs in act.observations:
                if obs.type == "LOINC":
                    loinc_ok = res.is_valid_loinc_code(obs.code)
                    if not loinc_ok:
                        trace = (
                            f"Observation.Type: 'LOINC' ✓",
                            f"LOINC lookup: '{obs.code}' → NOT FOUND in LOINC reference → VIOLATION",
                        )
                        errors.append(self._err(113, f"Authorization '{auth.id}', Activity '{act.id}': Observation.Code '{obs.code}' is not a registered LOINC code", trace=trace))
        return errors

    # Fires when: Activity.Type=5 (Service) and code is not a valid service code
    def _rule_120(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 5:
                svc_ok = res.is_valid_service_code(act.code)
                if not svc_ok:
                    trace = (
                        f"Condition 1 — Activity.Type: 5 (Service) ✓",
                        f"Condition 2 — Service code lookup: '{act.code}' → NOT FOUND → VIOLATION",
                    )
                    errors.append(self._err(120, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid service code", trace=trace))
        return errors

    # Fires when: Activity.Clinician is present but not a valid active clinician license
    def _rule_127(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.clinician and act.clinician.strip():
                clin_ok = res.is_active_clinician(act.clinician)
                if not clin_ok:
                    trace = (
                        f"Clinician license lookup: '{act.clinician}' → NOT FOUND or inactive → VIOLATION",
                    )
                    errors.append(self._err(127, f"Authorization '{auth.id}', Activity '{act.id}': Clinician '{act.clinician}' is not a valid active clinician license", trace=trace))
        return errors

    # Fires when: Activity.OrderingClinician is present but not a valid active clinician license
    def _rule_144(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.ordering_clinician and act.ordering_clinician.strip():
                clin_ok = res.is_active_clinician(act.ordering_clinician)
                if not clin_ok:
                    trace = (
                        f"OrderingClinician license lookup: '{act.ordering_clinician}' → NOT FOUND or inactive → VIOLATION",
                    )
                    errors.append(self._err(144, f"Authorization '{auth.id}', Activity '{act.id}': OrderingClinician '{act.ordering_clinician}' is not a valid active clinician license", trace=trace))
        return errors

    # Fires when: Encounter.End is before Encounter.Start
    def _rule_146(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        enc = auth.encounter
        if enc is None:
            return []
        start = _parse_datetime(enc.start) if enc.start else None
        end   = _parse_datetime(enc.end)   if enc.end   else None
        if start is not None and end is not None and end < start:
            return [self._err(146, f"Authorization '{auth.id}': Encounter.End must be >= Encounter.Start",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"Encounter.Start: '{enc.start}' → {start}",
                    f"Encounter.End: '{enc.end}' → {end}",
                    f"End is before Start → VIOLATION",
                ))]
        return []

    # Fires when: any Diagnosis.Code is not a valid ICD-10 code
    def _rule_147(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for dx in auth.diagnoses:
            icd10_ok = res.is_valid_icd10_code(dx.code)
            if not icd10_ok:
                trace = (
                    f"ICD-10 lookup: '{dx.code}' → NOT FOUND or inactive → VIOLATION",
                    f"Note: codes are case-sensitive. Verify exact casing and IsActive flag in the DB.",
                )
                errors.append(self._err(147, f"Authorization '{auth.id}': Diagnosis.Code '{dx.code}' is not a valid ICD-10 code", trace=trace))
        return errors

    # Fires when: Authorization type is Authorization or Extension but no Activities are present
    def _rule_156(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type in ("Authorization", "Extension") and not auth.activities:
            return [self._err(156, f"Authorization '{auth.id}': Activities are required when type is '{auth.type}'",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                    f"Type requires Activities but none are present → VIOLATION",
                ))]
        return []

    # Fires when: Authorization/Extension type has no Activities (alternate path check)
    def _rule_160(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type not in ("Authorization", "Extension"):
            return []
        if not auth.activities:
            return [self._err(160, f"Authorization '{auth.id}': At least one Activity is required when type is '{auth.type}'",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                    f"Type requires at least one Activity but list is empty → VIOLATION",
                ))]
        return []

    # Fires when: Authorization type is Cancellation but Activities are present
    def _rule_162(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type != "Cancellation":
            return []
        if auth.activities:
            return [self._err(162, f"Authorization '{auth.id}': Activities must not be present when type is Cancellation",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: 'Cancellation'",
                    f"Activities count: {len(auth.activities)} → must be 0 for Cancellation → VIOLATION",
                ))]
        return []

    # Fires when: ReceiverID is not HAAD and not a valid TPA (from 2014-10-01)
    def _rule_167(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 10, 1):
            return []
        receiver = model.header.receiver_id
        is_tpa = res.is_haad_tpa(receiver)
        if receiver != _HAAD_RECEIVER_ID and not is_tpa:
            trace = (
                f"ReceiverID: '{receiver}' → not HAAD",
                f"HAAD TPA lookup: '{receiver}' → NOT FOUND → VIOLATION",
            )
            return [self._err(167, f"Header.ReceiverID '{receiver}' must be HAAD or a valid TPA for Prior.Request", trace=trace)]
        return []

    # Fires when: SenderID is not a valid provider, payer, or TPA (from 2014-10-01)
    def _rule_168(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 10, 1):
            return []
        sender = model.header.sender_id
        is_provider = res.is_any_provider(sender)
        is_payer = res.is_haad_payer(sender)
        is_tpa = res.is_haad_tpa(sender)
        if not (is_provider or is_payer or is_tpa):
            trace = (
                f"SenderID: '{sender}' → provider lookup → {'YES' if is_provider else 'NO'}",
                f"SenderID: '{sender}' → HAAD payer lookup → {'YES' if is_payer else 'NO'}",
                f"SenderID: '{sender}' → HAAD TPA lookup → {'YES' if is_tpa else 'NO'}",
                f"None of provider/payer/TPA matched → VIOLATION",
            )
            return [self._err(168, f"Header.SenderID '{sender}' is not a valid provider, payer, or TPA", trace=trace)]
        return []

    # Fires when: Cancellation type has no prior Authorization/Extension response
    def _rule_175(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type == "Cancellation" and not res.prior_request_has_response(auth.id, model.header.sender_id):
            return [self._err(175, f"Authorization '{auth.id}': Cancellation requires a previous Authorization/Extension response",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: 'Cancellation'",
                    f"SenderID: '{model.header.sender_id}'",
                    f"No prior Authorization/Extension response found → VIOLATION",
                ))]
        return []

    # Fires when: Extension type but no approved Prior.Authorization exists for this ID
    def _rule_176(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type != "Extension":
            return []
        if not res.prior_auth_exists_for_id(auth.id, model.header.receiver_id):
            return [self._err(176, f"Authorization '{auth.id}': Extension requires an existing approved Prior.Authorization",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: 'Extension'",
                    f"ReceiverID: '{model.header.receiver_id}'",
                    f"No approved Prior.Authorization found for this ID → VIOLATION",
                ))]
        return []

    # Fires when: Status Inquiry type but no Prior.Authorization response exists for this ID
    def _rule_177(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type == "Status Inquiry" and not res.prior_auth_exists_for_id(auth.id, model.header.receiver_id):
            return [self._err(177, f"Authorization '{auth.id}': Status Inquiry requires an existing Prior.Authorization response",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: 'Status Inquiry'",
                    f"ReceiverID: '{model.header.receiver_id}'",
                    f"No Prior.Authorization response found for this ID → VIOLATION",
                ))]
        return []

    # Fires when: Authorization.ID is already used by this sender (duplicate Prior.Request)
    def _rule_181(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if not res.is_pr_authorization_id_unique(auth.id, model.header.sender_id):
            return [self._err(181, f"Authorization '{auth.id}': Authorization.ID is already used by this sender",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"SenderID: '{model.header.sender_id}'",
                    f"ID already exists in submitted Prior.Requests from this sender → VIOLATION",
                ))]
        return []

    # Fires when: Authorization/Extension type has no Diagnoses
    def _rule_182(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type not in ("Authorization", "Extension"):
            return []
        if not auth.diagnoses:
            return [self._err(182, f"Authorization '{auth.id}': At least one Diagnosis is required when type is '{auth.type}'",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                    f"Type requires Diagnoses but list is empty → VIOLATION",
                ))]
        return []

    # Fires when: Authorization/Extension type has no or invalid Encounter.FacilityID
    def _rule_186(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type not in ("Authorization", "Extension"):
            return []
        enc = auth.encounter
        if enc is None or not enc.facility_id:
            return [self._err(186, f"Authorization '{auth.id}': Encounter.FacilityID is required when type is '{auth.type}'",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                    f"Encounter: {'None' if enc is None else 'present but FacilityID empty'} → VIOLATION",
                ))]
        fac_ok = res.is_any_provider(enc.facility_id)
        if not fac_ok:
            trace = (
                f"Condition 1 — Auth.Type: '{auth.type}' → Authorization/Extension ✓",
                f"Condition 2 — FacilityID: '{enc.facility_id}' → provider license lookup → NOT FOUND → VIOLATION",
            )
            return [self._err(186, f"Authorization '{auth.id}': Encounter.FacilityID '{enc.facility_id}' is not a valid facility license", trace=trace)]
        return []

    # Fires when: Activity.Type=6 and code is not a valid DRG code
    def _rule_201(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 6:
                drg_ok = res.is_valid_drg_code(act.code)
                if not drg_ok:
                    trace = (
                        f"Condition 1 — Activity.Type: 6 (DRG) ✓",
                        f"Condition 2 — DRG code lookup: '{act.code}' → NOT FOUND → VIOLATION",
                    )
                    errors.append(self._err(201, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid DRG code", trace=trace))
        return errors

    # Fires when: DxInfo.Type is not in the valid DxInfo type set
    def _rule_202(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for dx in auth.diagnoses:
            for dxi in dx.dx_info:
                if dxi.type not in _VALID_DX_INFO_TYPES:
                    errors.append(self._err(202, f"Authorization '{auth.id}': DxInfo.Type '{dxi.type}' is not a valid type",
                        trace=(
                            f"Diagnosis.Code: '{dx.code}', DxInfo.Type: '{dxi.type}'",
                            f"Valid DxInfo types: {sorted(_VALID_DX_INFO_TYPES)}",
                            f"Type not in valid set → VIOLATION",
                        )))
        return errors

    # Fires when: Resubmission.Type is not a valid value (correction/internal complaint/legacy)
    def _rule_204(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        resubmission = auth.resubmission
        if resubmission and resubmission.type not in self._PQ_RESUBMISSION_TYPES:
            return [self._err(204, f"Authorization '{auth.id}': Resubmission.Type '{resubmission.type}' is not valid",
                trace=(
                    f"Authorization.ID: '{auth.id}', Resubmission.Type: '{resubmission.type}'",
                    f"Valid resubmission types: {sorted(self._PQ_RESUBMISSION_TYPES)}",
                    f"Type not in valid set → VIOLATION",
                ))]
        return []

    # Fires when: correction resubmission has no prior submission to correct
    def _rule_213(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        resubmission = auth.resubmission
        if resubmission and resubmission.type == "correction":
            if not res.prior_auth_exists_for_request(auth.id, auth.id_payer, model.header.receiver_id, None):
                return [self._err(213, f"Authorization '{auth.id}': Resubmission correction requires a prior submission",
                    trace=(
                        f"Authorization.ID: '{auth.id}', Resubmission.Type: 'correction'",
                        f"IDPayer: '{auth.id_payer}', ReceiverID: '{model.header.receiver_id}'",
                        f"No prior submission found matching this Authorization → VIOLATION",
                    ))]
        return []

    # Fires when: Activity.Type=8 and code is not a valid trade or generic drug code
    def _rule_238(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 8:
                trade_ok = res.is_valid_trade_drug(act.code)
                generic_ok = res.is_valid_generic_drug(act.code)
                if not trade_ok and not generic_ok:
                    trace = (
                        f"Condition 1 — Activity.Type: 8 (Drug, type 8) ✓",
                        f"Condition 2 — Trade drug lookup: '{act.code}' → {'FOUND ✓' if trade_ok else 'NOT FOUND'}",
                        f"Condition 3 — Generic drug lookup: '{act.code}' → {'FOUND ✓' if generic_ok else 'NOT FOUND'}",
                        f"Neither trade nor generic drug match → VIOLATION",
                    )
                    errors.append(self._err(238, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid drug code (type 8)", trace=trace))
        return errors

    # Fires when: Activity.Type=3 (CPT) and code is in CPT exclusion list 1
    def _rule_243(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 3:
                in_excl = res.in_exclusion_list_1(act.code)
                if in_excl:
                    trace = (
                        f"Condition 1 — Activity.Type: 3 (CPT) ✓",
                        f"Condition 2 — CPT exclusion list 1 lookup: '{act.code}' → FOUND → VIOLATION",
                    )
                    errors.append(self._err(243, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is in CPT exclusion list", trace=trace))
        return errors

    # Fires when: Activity.Type=4 (HCPCS) and code is in exclusion list 4
    def _rule_244(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 4:
                in_excl = res.in_exclusion_list_4(act.code)
                if in_excl:
                    trace = (
                        f"Condition 1 — Activity.Type: 4 (HCPCS) ✓",
                        f"Condition 2 — Exclusion list 4 lookup: '{act.code}' → FOUND → VIOLATION",
                    )
                    errors.append(self._err(244, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is in exclusion list 4", trace=trace))
        return errors

    # Fires when: Activity.Type=5 (Service) and code is in service exclusion list 6
    def _rule_245(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 5:
                in_excl = res.in_exclusion_list_6(act.code)
                if in_excl:
                    trace = (
                        f"Condition 1 — Activity.Type: 5 (Service) ✓",
                        f"Condition 2 — Service exclusion list 6 lookup: '{act.code}' → FOUND → VIOLATION",
                    )
                    errors.append(self._err(245, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is in service exclusion list", trace=trace))
        return errors

    # Fires when: Activity.Type=9 and code is not a valid service code
    def _rule_248(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 9:
                svc_ok = res.is_valid_service_code(act.code)
                if not svc_ok:
                    trace = (
                        f"Condition 1 — Activity.Type: 9 (Service, type 9) ✓",
                        f"Condition 2 — Service code lookup: '{act.code}' → NOT FOUND → VIOLATION",
                    )
                    errors.append(self._err(248, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid service code (type 9)", trace=trace))
        return errors

    # Fires when: Authorization.MemberID is empty
    def _rule_250(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if not auth.member_id or not auth.member_id.strip():
            return [self._err(250, f"Authorization '{auth.id}': MemberID may not be empty",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"MemberID: '{auth.member_id}' → empty or whitespace → VIOLATION",
                ))]
        return []

    # Fires when: Authorization.PayerID is empty (from 2015-01-01)
    def _rule_251(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2015, 1, 1):
            return []
        payer = auth.payer_id
        if not payer or not payer.strip():
            return [self._err(251, f"Authorization '{auth.id}': PayerID may not be empty",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"TransactionDate: '{model.header.transaction_date}' → >= 2015-01-01, rule applies",
                    f"PayerID: '{payer}' → empty or whitespace → VIOLATION",
                ))]
        return []

    # Fires when: Authorization.PayerID is not a valid payer license (non-@ values)
    def _rule_252(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        payer = auth.payer_id
        if not payer or payer.startswith("@"):
            return []
        payer_ok = res.is_active_insurer_or_other(payer)
        if not payer_ok:
            trace = (
                f"PayerID: '{payer}' → insurer/other license lookup → NOT FOUND or inactive → VIOLATION",
            )
            return [self._err(252, f"Authorization '{auth.id}': PayerID '{payer}' is not a valid payer license", trace=trace)]
        return []

    # Fires when: Authorization/Extension type has an Encounter but Encounter.Start is missing
    def _rule_253(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type not in ("Authorization", "Extension") or not auth.encounter:
            return []
        enc = auth.encounter
        if not enc.start:
            return [self._err(253, f"Authorization '{auth.id}': Encounter.Start is required when type is '{auth.type}'",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                    f"Encounter is present but Encounter.Start is missing or empty → VIOLATION",
                ))]
        return []

    # Fires when: Authorization/Extension type has an Encounter but Encounter.Type is missing
    def _rule_254(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type not in ("Authorization", "Extension") or not auth.encounter:
            return []
        enc = auth.encounter
        if enc.type is None:
            return [self._err(254, f"Authorization '{auth.id}': Encounter.Type is required when type is '{auth.type}'",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                    f"Encounter is present but Encounter.Type is None → VIOLATION",
                ))]
        return []

    # Fires when: Activity.Start is after Encounter.End
    def _rule_255(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            start = _parse_datetime(act.start) if act.start else None
            if start is None:
                continue
            enc = auth.encounter
            enc_end = _parse_datetime(enc.end) if enc and enc.end else None
            if enc_end is not None and start > enc_end:
                errors.append(self._err(255, f"Authorization '{auth.id}', Activity '{act.id}': Start must be <= Encounter.End",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Start: '{act.start}' → {start}",
                        f"Encounter.End: '{enc.end}' → {enc_end}",
                        f"Activity.Start > Encounter.End → VIOLATION",
                    )))
        return errors

    # Fires when: Encounter.FacilityID is present but not a registered facility
    def _rule_256(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        enc = auth.encounter
        if enc is None or not enc.facility_id:
            return []
        fac_ok = res.is_any_provider(enc.facility_id)
        if not fac_ok:
            trace = (
                f"FacilityID: '{enc.facility_id}' → provider license lookup → NOT FOUND → VIOLATION",
            )
            return [self._err(256, f"Authorization '{auth.id}': Encounter.FacilityID '{enc.facility_id}' is not a registered facility", trace=trace)]
        return []

    # Fires when: Authorization/Extension type has no DateOrdered
    def _rule_257(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type not in ("Authorization", "Extension"):
            return []
        if not auth.date_ordered:
            return [self._err(257, f"Authorization '{auth.id}': DateOrdered is required when type is '{auth.type}'",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                    f"DateOrdered is missing or empty → VIOLATION",
                ))]
        return []

    # Fires when: Cancellation type but no existing Prior.Authorization found for this ID
    def _rule_258(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type != "Cancellation":
            return []
        if not res.prior_auth_exists_for_id(auth.id, model.header.receiver_id):
            return [self._err(258, f"Authorization '{auth.id}': Cancellation requires an existing Prior.Authorization",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: 'Cancellation'",
                    f"ReceiverID: '{model.header.receiver_id}'",
                    f"No existing Prior.Authorization found for this ID → VIOLATION",
                ))]
        return []

    # Fires when: Status Inquiry type but not all prior requests have been responded to
    def _rule_259(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type == "Status Inquiry":
            if not res.prior_auth_all_requests_responded(auth.id, model.header.sender_id):
                return [self._err(259, f"Authorization '{auth.id}': Status Inquiry requires all prior requests to have responses",
                    trace=(
                        f"Authorization.ID: '{auth.id}', Authorization.Type: 'Status Inquiry'",
                        f"SenderID: '{model.header.sender_id}'",
                        f"Not all prior requests have responses → VIOLATION",
                    ))]
        return []

    # Fires when: Prescription type has no Activities
    def _rule_260(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type != "Prescription":
            return []
        if not auth.activities:
            return [self._err(260, f"Authorization '{auth.id}': Activities are required when type is Prescription",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: 'Prescription'",
                    f"Type requires Activities but list is empty → VIOLATION",
                ))]
        return []

    # Fires when: Prescription type has Activities with types outside {2,3,8,9}
    def _rule_261(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        if auth.type == "Prescription":
            for act in auth.activities:
                if act.type not in (2, 3, 8, 9):
                    errors.append(self._err(261, f"Authorization '{auth.id}', Activity '{act.id}': Type {act.type} is not allowed in Prescription requests",
                        trace=(
                            f"Authorization.Type: 'Prescription', Activity.ID: '{act.id}', Activity.Type: {act.type}",
                            f"Allowed types for Prescription: {{2, 3, 8, 9}}",
                            f"Type not in allowed set → VIOLATION",
                        )))
        return errors

    # Fires when: Eligibility type has Activities present
    def _rule_265(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type == "Eligibility" and auth.activities:
            return [self._err(265, f"Authorization '{auth.id}': Activities must not be present when type is Eligibility",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: 'Eligibility'",
                    f"Activities count: {len(auth.activities)} → must be 0 for Eligibility → VIOLATION",
                ))]
        return []

    # Fires when: Activity.Type=3 (CPT) and code is in HCPCS exclusion list 2
    def _rule_296(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 3:
                in_excl = res.in_exclusion_list_2(act.code)
                if in_excl:
                    trace = (
                        f"Condition 1 — Activity.Type: 3 (CPT) ✓",
                        f"Condition 2 — HCPCS exclusion list 2 lookup: '{act.code}' → FOUND → VIOLATION",
                    )
                    errors.append(self._err(296, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is in HCPCS exclusion list", trace=trace))
        return errors

    # Fires when: Encounter.FacilityID is present but not an active facility
    def _rule_297(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        enc = auth.encounter
        if enc is None:
            return []
        facility = enc.facility_id
        if not facility or not facility.strip():
            return []
        fac_ok = res.is_active_provider(facility)
        if not fac_ok:
            trace = (
                f"FacilityID: '{facility}' → active provider lookup → NOT FOUND or inactive → VIOLATION",
            )
            return [self._err(297, f"Authorization '{auth.id}': Encounter.FacilityID '{facility}' is not an active facility", trace=trace)]
        return []

    # Fires when: Activity.Clinician is present but not an active clinician
    def _rule_298(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.clinician:
                clin_ok = res.is_active_clinician(act.clinician)
                if not clin_ok:
                    trace = (
                        f"Clinician license lookup: '{act.clinician}' → NOT FOUND or inactive → VIOLATION",
                    )
                    errors.append(self._err(298, f"Authorization '{auth.id}', Activity '{act.id}': Clinician '{act.clinician}' is not active", trace=trace))
        return errors

    # Fires when: Activity.OrderingClinician is present but not an active clinician
    def _rule_299(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.ordering_clinician:
                clin_ok = res.is_active_clinician(act.ordering_clinician)
                if not clin_ok:
                    trace = (
                        f"OrderingClinician license lookup: '{act.ordering_clinician}' → NOT FOUND or inactive → VIOLATION",
                    )
                    errors.append(self._err(299, f"Authorization '{auth.id}', Activity '{act.id}': OrderingClinician '{act.ordering_clinician}' is not active", trace=trace))
        return errors

    # Fires when: Authorization/Extension Encounter.Type is not a valid encounter type
    def _rule_300(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type not in ("Authorization", "Extension"):
            return []
        enc = auth.encounter
        if enc is None:
            return []
        etype = enc.type
        if etype is not None and etype not in self._PQ_VALID_ENC_TYPES:
            return [self._err(300, f"Authorization '{auth.id}': Encounter.Type {etype} is not valid",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                    f"Encounter.Type: {etype}",
                    f"Valid encounter types: {sorted(self._PQ_VALID_ENC_TYPES)}",
                    f"Type not in valid set → VIOLATION",
                ))]
        return []

    # Fires when: any Diagnosis.Code is not an active ICD-10 code (active-check variant)
    def _rule_302(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for dx in auth.diagnoses:
            icd10_ok = res.is_valid_icd10_code(dx.code)
            if not icd10_ok:
                trace = (
                    f"ICD-10 lookup: '{dx.code}' → NOT FOUND or inactive → VIOLATION",
                    f"Note: codes are case-sensitive. Verify exact casing and IsActive flag in the DB.",
                )
                errors.append(self._err(302, f"Authorization '{auth.id}': Diagnosis.Code '{dx.code}' is not a valid ICD-10 code (active check)", trace=trace))
        return errors

    # Fires when: a Resubmission is present but Resubmission.Comment is empty
    def _rule_304(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        resubmission = auth.resubmission
        if not resubmission:
            return []
        if not resubmission.comment or not resubmission.comment.strip():
            return [self._err(304, f"Authorization '{auth.id}': Resubmission.Comment may not be empty",
                trace=(
                    f"Authorization.ID: '{auth.id}', Resubmission.Type: '{resubmission.type}'",
                    f"Resubmission.Comment: '{resubmission.comment}' → empty or whitespace → VIOLATION",
                ))]
        return []

    # Fires when: Authorization type is Cancellation but no Resubmission element is present
    def _rule_305(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type == "Cancellation":
            resubmission = auth.resubmission
            if not resubmission:
                return [self._err(305, f"Authorization '{auth.id}': Resubmission is required when type is Cancellation",
                    trace=(
                        f"Authorization.ID: '{auth.id}', Authorization.Type: 'Cancellation'",
                        f"No Resubmission element found → VIOLATION",
                    ))]
        return []

    # Fires when: Observation.Type='Text' and Observation.Value is empty
    def _rule_307(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            for obs in act.observations:
                if obs.type == "Text" and (not obs.value or not obs.value.strip()):
                    errors.append(self._err(307, f"Authorization '{auth.id}', Activity '{act.id}': Observation.Value may not be empty when type is Text",
                        trace=(
                            f"Activity.ID: '{act.id}', Observation.Type: 'Text'",
                            f"Observation.Value: '{obs.value}' → empty or whitespace → VIOLATION",
                        )))
        return errors

    # Fires when: Observation.Type='Universal Dental' and Observation.ValueDate is missing
    def _rule_313(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            for obs in act.observations:
                if obs.type == "Universal Dental":
                    if not obs.value_date or not obs.value_date.strip():
                        errors.append(self._err(313, f"Authorization '{auth.id}', Activity '{act.id}': Observation.ValueDate is required when type is Universal Dental",
                            trace=(
                                f"Activity.ID: '{act.id}', Observation.Type: 'Universal Dental'",
                                f"Observation.ValueDate: '{obs.value_date}' → missing or empty → VIOLATION",
                            )))
        return errors

    # Fires when: Observation.Type='Universal Dental' and Observation.Value is missing
    def _rule_314(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            for obs in act.observations:
                if obs.type == "Universal Dental":
                    if not obs.value or not obs.value.strip():
                        errors.append(self._err(314, f"Authorization '{auth.id}', Activity '{act.id}': Observation.Value is required when type is Universal Dental",
                            trace=(
                                f"Activity.ID: '{act.id}', Observation.Type: 'Universal Dental'",
                                f"Observation.Value: '{obs.value}' → missing or empty → VIOLATION",
                            )))
        return errors

    # Fires when: Authorization/Extension Encounter.Start is after TransactionDate (from 2021-01-01)
    def _rule_322(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2021, 1, 1):
            return []
        auth = model.authorization
        if auth.type not in ("Authorization", "Extension"):
            return []
        enc = auth.encounter
        if enc is not None and enc.start:
            start = _parse_datetime(enc.start)
            if start is not None and start > tx:
                return [self._err(322, f"Authorization '{auth.id}': Encounter.Start must be <= TransactionDate",
                    trace=(
                        f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                        f"Encounter.Start: '{enc.start}' → {start}",
                        f"TransactionDate: '{model.header.transaction_date}' → {tx}",
                        f"Encounter.Start > TransactionDate → VIOLATION",
                    ))]
        return []

    # Fires when: Authorization.DateOrdered is after TransactionDate (from 2021-01-01)
    def _rule_324(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2021, 1, 1):
            return []
        auth = model.authorization
        if auth.date_ordered:
            do = _parse_date(auth.date_ordered)
            if do is not None and do > tx:
                return [self._err(324, f"Authorization '{auth.id}': DateOrdered must be <= TransactionDate",
                    trace=(
                        f"Authorization.ID: '{auth.id}'",
                        f"DateOrdered: '{auth.date_ordered}' → {do}",
                        f"TransactionDate: '{model.header.transaction_date}' → {tx}",
                        f"DateOrdered > TransactionDate → VIOLATION",
                    ))]
        return []

    # Fires when: any Activity.DenialCode is not active on the transaction date (from 2023-01-01)
    def _rule_344(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 1, 1):
            return []
        errors = []
        auth = model.authorization
        tx_str = tx.strftime("%d/%m/%Y")
        for act in auth.activities:
            dc = getattr(act, 'denial_code', None)
            if dc and dc.strip():
                if not res.is_denial_code_valid_on_date(dc, tx):
                    trace = (
                        f"Activity DenialCode date lookup: '{dc}' on {tx_str} → NOT FOUND or inactive → VIOLATION",
                    )
                    errors.append(self._err(344, f"Authorization '{auth.id}', Activity '{act.id}': DenialCode '{dc}' is not active on transaction date", trace=trace))
        return errors

    # Fires when: Extension type requires an approved PA before TransactionDate but none found (from 2023-01-01)
    def _rule_345(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 1, 1):
            return []
        auth = model.authorization
        if auth.type != "Extension":
            return []
        if not res.prior_auth_exists_for_request(auth.id, auth.id_payer, model.header.receiver_id, tx):
            return [self._err(345, f"Authorization '{auth.id}': Extension requires an existing approved Prior.Authorization before TransactionDate",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: 'Extension'",
                    f"IDPayer: '{auth.id_payer}', ReceiverID: '{model.header.receiver_id}'",
                    f"TransactionDate cutoff: {tx}",
                    f"No approved Prior.Authorization found before TransactionDate → VIOLATION",
                ))]
        return []

    # Fires when: Activity.Type=4 (HCPCS) uses a pure CPT code (from 2023-07-01)
    def _rule_357(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 7, 1):
            return []
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 4:
                is_cpt = res.is_valid_cpt_code(act.code)
                if is_cpt:
                    trace = (
                        f"Condition 1 — Activity.Type: 4 (HCPCS) ✓",
                        f"Condition 2 — CPT lookup: '{act.code}' → FOUND (pure CPT code) → Type 4 cannot use CPT codes → VIOLATION",
                    )
                    errors.append(self._err(357, f"Authorization '{auth.id}', Activity '{act.id}': HCPCS activity cannot use a CPT code", trace=trace))
        return errors

    # Fires when: Activity.Type=3 (CPT) uses a pure HCPCS code (from 2023-07-01)
    def _rule_358(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 7, 1):
            return []
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type == 3:
                is_hcpcs = res.is_valid_hcpcs_code(act.code)
                is_cpt = res.is_valid_cpt_code(act.code)
                if is_hcpcs and not is_cpt:
                    trace = (
                        f"Condition 1 — Activity.Type: 3 (CPT) ✓",
                        f"Condition 2 — HCPCS lookup: '{act.code}' → FOUND",
                        f"Condition 3 — CPT lookup: '{act.code}' → NOT FOUND → pure HCPCS code used in CPT activity → VIOLATION",
                    )
                    errors.append(self._err(358, f"Authorization '{auth.id}', Activity '{act.id}': CPT activity cannot use a pure HCPCS code", trace=trace))
        return errors

    # Fires when: Universal Dental Observation.ValueDate is more than 1 day from Activity.Start (from 2023-07-01)
    def _rule_359(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 7, 1):
            return []
        errors = []
        auth = model.authorization
        for act in auth.activities:
            for obs in act.observations:
                if obs.type == "Universal Dental":
                    vd = _parse_datetime(obs.value_date) if obs.value_date else None
                    act_start = _parse_datetime(act.start) if act.start else None
                    if vd is not None and act_start is not None and abs((vd - act_start).days) > 1:
                        errors.append(self._err(359, f"Authorization '{auth.id}', Activity '{act.id}': Universal Dental ValueDate must be within 1 day of Activity.Start",
                            trace=(
                                f"Activity.ID: '{act.id}', Observation.Type: 'Universal Dental'",
                                f"Activity.Start: '{act.start}' → {act_start.date()}",
                                f"Observation.ValueDate: '{obs.value_date}' → {vd.date()}",
                                f"Difference: {abs((vd - act_start).days)} days > 1 → VIOLATION",
                            )))
        return errors

    # Fires when: any Activity.Start is after TransactionDate (from 2023-10-01)
    def _rule_363(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 10, 1):
            return []
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.start:
                act_start = _parse_datetime(act.start)
                if act_start is not None and act_start > tx:
                    errors.append(self._err(363, f"Authorization '{auth.id}', Activity '{act.id}': Activity.Start must be <= TransactionDate",
                        trace=(
                            f"Activity.ID: '{act.id}', Activity.Start: '{act.start}' → {act_start}",
                            f"TransactionDate: '{model.header.transaction_date}' → {tx}",
                            f"Activity.Start > TransactionDate → VIOLATION",
                        )))
        return errors

    # Fires when: Authorization.DateOrdered is after Encounter.Start (from 2023-10-01)
    def _rule_364(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 10, 1):
            return []
        auth = model.authorization
        if auth.date_ordered:
            do = _parse_date(auth.date_ordered)
            enc = auth.encounter
            if enc and enc.start:
                enc_start = _parse_datetime(enc.start)
                if do is not None and enc_start is not None and do > enc_start:
                    return [self._err(364, f"Authorization '{auth.id}': DateOrdered must be <= Encounter.Start",
                        trace=(
                            f"Authorization.ID: '{auth.id}'",
                            f"DateOrdered: '{auth.date_ordered}' → {do}",
                            f"Encounter.Start: '{enc.start}' → {enc_start}",
                            f"DateOrdered > Encounter.Start → VIOLATION",
                        ))]
        return []

    # Fires when: Authorization/Extension type has no Encounter element (from 2024-03-01)
    def _rule_378(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2024, 3, 1):
            return []
        auth = model.authorization
        if auth.type not in ("Authorization", "Extension"):
            return []
        if not auth.encounter:
            return [self._err(378, f"Authorization '{auth.id}': Encounter is required when type is '{auth.type}'",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                    f"TransactionDate: '{model.header.transaction_date}' → >= 2024-03-01, rule applies",
                    f"No Encounter element found → VIOLATION",
                ))]
        return []

    # Fires when: Encounter.Start is more than 365 days before TransactionDate (from 2024-06-01)
    def _rule_382(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2024, 6, 1):
            return []
        auth = model.authorization
        enc = auth.encounter
        if enc is None or not enc.start:
            return []
        enc_start = _parse_datetime(enc.start)
        if enc_start is not None and tx is not None:
            days_diff = (tx - enc_start).days
            if days_diff > 365:
                return [self._err(382, f"Authorization '{auth.id}': Encounter.Start is more than 365 days before TransactionDate",
                    trace=(
                        f"Authorization.ID: '{auth.id}'",
                        f"Encounter.Start: '{enc.start}' → {enc_start.date()}",
                        f"TransactionDate: '{model.header.transaction_date}' → {tx.date()}",
                        f"Difference: {days_diff} days > 365 → VIOLATION",
                    ))]
        return []

    # Fires when: Authorization/Extension Encounter.Start is before 01/01/2006 (from 2024-06-01)
    def _rule_383(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2024, 6, 1):
            return []
        auth = model.authorization
        if auth.type not in ("Authorization", "Extension"):
            return []
        enc = auth.encounter
        if enc is not None and enc.start:
            enc_start = _parse_datetime(enc.start)
            if enc_start is not None and enc_start < datetime(2006, 1, 1):
                return [self._err(383, f"Authorization '{auth.id}': Encounter.Start must be >= 01/01/2006",
                    trace=(
                        f"Authorization.ID: '{auth.id}', Authorization.Type: '{auth.type}'",
                        f"Encounter.Start: '{enc.start}' → {enc_start.date()}",
                        f"Minimum allowed date: 2006-01-01",
                        f"Encounter.Start is before minimum → VIOLATION",
                    ))]
        return []

    # Fires when: (INACTIVE) Resubmission exists but Attachment is missing
    def _rule_5(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.resubmission is not None and not auth.resubmission.attachment:
            return [self._inactive_err(5, f"Authorization '{auth.id}': Resubmission Attachment must contain a PDF file",
                trace=(
                    f"Authorization.ID: '{auth.id}', Resubmission.Type: '{auth.resubmission.type}'",
                    f"Resubmission.Attachment is missing → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) Authorization type is Authorization, TransactionDate >= 2014-06-01, Encounter.End is null, and Encounter.Type is 3 or 4
    def _rule_38(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 6, 1):
            return []
        auth = model.authorization
        if auth.type != "Authorization":
            return []
        enc = auth.encounter
        if enc is None:
            return []
        if enc.type in (3, 4) and not enc.end:
            return [self._inactive_err(38, f"Authorization '{auth.id}': Encounter.End must be empty for outpatient encounter type {enc.type}",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: 'Authorization'",
                    f"Encounter.Type: {enc.type} (outpatient) → Encounter.End must be empty",
                    f"Encounter.End: '{enc.end}' → not provided → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) Activity.Observation.Type is null
    def _rule_44(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            for obs in act.observations:
                if not obs.type or not obs.type.strip():
                    errors.append(self._inactive_err(44, f"Authorization '{auth.id}', Activity '{act.id}': Observation.Type must have a value",
                        trace=(
                            f"Activity.ID: '{act.id}', Observation.Type: '{obs.type}' → empty or None → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Observation.Type is LOINC and Observation.Value is not numeric (optionally < or >)
    def _rule_48(self, model: pq.PriorRequest, res) -> list:
        import re as _re
        _loinc_val_pat = _re.compile(r'^[<>]?\s*\d+(\.\d+)?$')
        errors = []
        auth = model.authorization
        for act in auth.activities:
            for obs in act.observations:
                if obs.type == "LOINC" and obs.value is not None:
                    if not _loinc_val_pat.match(obs.value.strip()):
                        errors.append(self._inactive_err(48, f"Authorization '{auth.id}', Activity '{act.id}': Observation value for LOINC must be numeric",
                            trace=(
                                f"Activity.ID: '{act.id}', Observation.Type: 'LOINC'",
                                f"Observation.Value: '{obs.value}' → does not match numeric pattern (e.g. '5.5', '<10') → VIOLATION",
                            )))
        return errors

    # Fires when: (INACTIVE) Diagnosis.Type is not a valid type
    def _rule_51(self, model: pq.PriorRequest, res) -> list:
        _valid_dx_types = frozenset({"Principal", "Secondary", "Admitting", "ReasonForVisit", "Discharge"})
        errors = []
        auth = model.authorization
        for dx in auth.diagnoses:
            if dx.type not in _valid_dx_types:
                errors.append(self._inactive_err(51, f"Authorization '{auth.id}': Diagnosis.Type '{dx.type}' is not valid",
                    trace=(
                        f"Diagnosis.Code: '{dx.code}', Diagnosis.Type: '{dx.type}'",
                        f"Valid types: {sorted(_valid_dx_types)}",
                        f"Type not in valid set → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Diagnosis.Code is not a valid ICD9/ICD10 code (various conditions)
    def _rule_52(self, model: pq.PriorRequest, res) -> list:
        sender = model.header.sender_id
        auth = model.authorization
        enc = auth.encounter
        enc_start = _parse_datetime(enc.start) if enc and enc.start else None
        tx = _parse_datetime(model.header.transaction_date)
        errors = []
        for dx in auth.diagnoses:
            use_icd10 = (enc_start is not None and enc_start >= datetime(2016, 9, 15)) or \
                        (enc_start is None and tx is not None and tx >= datetime(2016, 9, 15))
            is_pf_mf = sender.startswith("PF") or sender.startswith("MF")
            if is_pf_mf:
                icd9_ok = res.is_valid_icd9_code(dx.code)
                icd10_ok = res.is_valid_icd10_code(dx.code)
                if not icd9_ok and not icd10_ok:
                    trace = (
                        f"SenderID prefix: PF/MF → both ICD9 and ICD10 checked",
                        f"ICD9 lookup: '{dx.code}' → {'FOUND ✓' if icd9_ok else 'NOT FOUND'}",
                        f"ICD10 lookup: '{dx.code}' → {'FOUND ✓' if icd10_ok else 'NOT FOUND'}",
                        f"Neither ICD9 nor ICD10 match → VIOLATION",
                    )
                    errors.append(self._inactive_err(52, f"Authorization '{auth.id}': Diagnosis.Code '{dx.code}' is not a valid ICD9/ICD10 code", trace=trace))
            elif use_icd10:
                icd10_ok = res.is_valid_icd10_code(dx.code)
                if not icd10_ok:
                    trace = (
                        f"Encounter/Tx date ≥ 2016-09-15 → ICD-10 required",
                        f"ICD-10 lookup: '{dx.code}' → NOT FOUND or inactive → VIOLATION",
                    )
                    errors.append(self._inactive_err(52, f"Authorization '{auth.id}': Diagnosis.Code '{dx.code}' is not a valid ICD10 code", trace=trace))
            else:
                icd9_ok = res.is_valid_icd9_code(dx.code)
                if not icd9_ok:
                    trace = (
                        f"Encounter/Tx date < 2016-09-15 → ICD-9 required",
                        f"ICD9 lookup: '{dx.code}' → NOT FOUND in HIB_MDM.ICD09 (or IsActive ≠ 1) → VIOLATION",
                        f"Note: codes are case-sensitive. Verify exact casing and IsActive flag in the DB.",
                    )
                    errors.append(self._inactive_err(52, f"Authorization '{auth.id}': Diagnosis.Code '{dx.code}' is not a valid ICD9 code", trace=trace))
        return errors

    # Fires when: (INACTIVE) Activity.Code is not a valid ICD9 code
    def _rule_64(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            icd9_ok = res.is_valid_icd9_code(act.code)
            if not icd9_ok:
                trace = (
                    f"ICD9 lookup: code = '{act.code}' → NOT FOUND in HIB_MDM.ICD09 (or IsActive ≠ 1) → VIOLATION",
                    f"Note: codes are case-sensitive. Verify exact casing and IsActive flag in the DB.",
                )
                errors.append(self._inactive_err(64, f"Authorization '{auth.id}', Activity '{act.id}': Code '{act.code}' is not a valid ICD9 code", trace=trace))
        return errors

    # Fires when: (INACTIVE) Activity.Type != 10 and Activity.Net is null/empty
    def _rule_76(self, model: pq.PriorRequest, res) -> list:
        errors = []
        auth = model.authorization
        for act in auth.activities:
            if act.type != 10 and act.net is None:
                errors.append(self._inactive_err(76, f"Authorization '{auth.id}', Activity '{act.id}': Net may not be null",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Type: {act.type} (not 10)",
                        f"Activity.Net is None → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2013-06-01, Encounter.Type is 3 or 4, and Activity.Start is null
    def _rule_80(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2013, 6, 1):
            return []
        auth = model.authorization
        enc = auth.encounter
        if enc is None or enc.type not in (3, 4):
            return []
        errors = []
        for act in auth.activities:
            if not act.start:
                errors.append(self._inactive_err(80, f"Authorization '{auth.id}', Activity '{act.id}': Start may not be null for inpatient encounter type",
                    trace=(
                        f"Activity.ID: '{act.id}', Encounter.Type: {enc.type} (inpatient)",
                        f"Activity.Start is None or empty → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2010-10-01 and Observation.Code is not in the tooth registry
    def _rule_89(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2010, 10, 1):
            return []
        errors = []
        auth = model.authorization
        for act in auth.activities:
            for obs in act.observations:
                if obs.type == "Universal Dental":
                    try:
                        tooth_ok = res.is_valid_tooth_code(obs.code)
                        if not tooth_ok:
                            trace = (
                                f"TransactionDate ≥ 2010-10-01 ✓",
                                f"Observation.Type = 'Universal Dental' ✓",
                                f"Tooth code lookup: '{obs.code}' → NOT FOUND in tooth registry → VIOLATION",
                            )
                            errors.append(self._inactive_err(89, f"Authorization '{auth.id}', Activity '{act.id}': Observation.Code '{obs.code}' is not a valid tooth code", trace=trace))
                    except Exception:
                        pass
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2011-06-15 and Activity.Type=9 but Encounter.Type is not 3 or 4
    def _rule_138(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        auth = model.authorization
        enc = auth.encounter
        if enc is None:
            return []
        errors = []
        for act in auth.activities:
            if act.type == 9 and enc.type not in (3, 4):
                errors.append(self._inactive_err(138, f"Authorization '{auth.id}', Activity '{act.id}': Type 9 (DRG) is only allowed for inpatient encounter (type 3 or 4)",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Type: 9 (DRG)",
                        f"Encounter.Type: {enc.type} → not inpatient (3 or 4) → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2011-06-15 and Encounter.End > TransactionDate
    def _rule_143(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        auth = model.authorization
        enc = auth.encounter
        if enc is None or not enc.end:
            return []
        enc_end = _parse_datetime(enc.end)
        if enc_end is not None and enc_end > tx:
            return [self._inactive_err(143, f"Authorization '{auth.id}': Encounter.End '{enc.end}' must be <= Header.TransactionDate",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"Encounter.End: '{enc.end}' → {enc_end}",
                    f"TransactionDate: '{model.header.transaction_date}' → {tx}",
                    f"Encounter.End > TransactionDate → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) TransactionDate >= 2011-01-01 and Authorization.PayerID != Header.ReceiverID
    def _rule_157(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 1, 1):
            return []
        auth = model.authorization
        if auth.payer_id != model.header.receiver_id:
            return [self._inactive_err(157, f"Authorization '{auth.id}': PayerID must equal Header.ReceiverID",
                trace=(
                    f"Authorization.ID: '{auth.id}'",
                    f"Authorization.PayerID: '{auth.payer_id}'",
                    f"Header.ReceiverID: '{model.header.receiver_id}'",
                    f"PayerID ≠ ReceiverID → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) TransactionDate >= 2011-01-01 and Authorization.ID is a duplicate in the file
    def _rule_161(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 1, 1):
            return []
        auth = model.authorization
        try:
            if not res.is_pr_authorization_id_unique(auth.id, model.header.sender_id):
                return [self._inactive_err(161, f"Authorization ID '{auth.id}' must be unique within a file",
                    trace=(
                        f"Authorization.ID: '{auth.id}'",
                        f"SenderID: '{model.header.sender_id}'",
                        f"ID already exists in submitted file → VIOLATION",
                    ))]
        except Exception:
            pass
        return []

    # Fires when: (INACTIVE) TransactionDate >= 2011-06-15 and Resubmission.Type not Correction/Complaint but IDPayer is set
    def _rule_174(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        auth = model.authorization
        if auth.resubmission is None:
            return []
        if auth.resubmission.type in ("correction", "internal complaint"):
            return []
        if auth.id_payer and auth.id_payer.strip():
            return [self._inactive_err(174, f"Authorization '{auth.id}': IDPayer should be null for Resubmission.Type '{auth.resubmission.type}'",
                trace=(
                    f"Authorization.ID: '{auth.id}', Resubmission.Type: '{auth.resubmission.type}'",
                    f"IDPayer: '{auth.id_payer}' → present (should be null for this type) → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) TransactionDate >= 2014-12-01 and Diagnosis.DxInfo.Type is not POA or Year of Onset
    def _rule_239(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 12, 1):
            return []
        _valid_dxinfo = frozenset({"POA", "Year of Onset"})
        errors = []
        auth = model.authorization
        for dx in auth.diagnoses:
            for dxi in dx.dx_info:
                if dxi.type not in _valid_dxinfo:
                    errors.append(self._inactive_err(239, f"Authorization '{auth.id}': DxInfo.Type '{dxi.type}' must be 'POA' or 'Year of Onset'",
                        trace=(
                            f"Diagnosis.Code: '{dx.code}', DxInfo.Type: '{dxi.type}'",
                            f"Valid types: {{'POA', 'Year of Onset'}}",
                            f"Type not in valid set → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Authorization.Type is Authorization and Encounter.Type is 7
    def _rule_249(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type != "Authorization":
            return []
        enc = auth.encounter
        if enc is not None and enc.type == 7:
            return [self._inactive_err(249, f"Authorization '{auth.id}': Type 'Authorization' is not allowed for Encounter.Type 7",
                trace=(
                    f"Authorization.ID: '{auth.id}', Authorization.Type: 'Authorization'",
                    f"Encounter.Type: 7 → not allowed with Authorization type → VIOLATION",
                ))]
        return []

    # Fires when: (INACTIVE) Type is Prescription/Authorization, Activity.Observation.Type is not Universal Dental/Flags, and Observation.Value is null/empty
    def _rule_262(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type not in ("Prescription", "Authorization"):
            return []
        errors = []
        for act in auth.activities:
            for obs in act.observations:
                if obs.type in ("Universal Dental", "Flags"):
                    continue
                if not obs.value or not obs.value.strip():
                    errors.append(self._inactive_err(262, f"Authorization '{auth.id}', Activity '{act.id}': Observation.Value may not be empty for type '{obs.type}'",
                        trace=(
                            f"Activity.ID: '{act.id}', Observation.Type: '{obs.type}'",
                            f"Observation.Value: '{obs.value}' → empty or whitespace → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Type is Prescription/Authorization, Observation.Type is not Universal Dental/Flags, and Observation.ValueType is null/empty
    def _rule_263(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        if auth.type not in ("Prescription", "Authorization"):
            return []
        errors = []
        for act in auth.activities:
            for obs in act.observations:
                if obs.type in ("Universal Dental", "Flags"):
                    continue
                if not obs.value_type or not obs.value_type.strip():
                    errors.append(self._inactive_err(263, f"Authorization '{auth.id}', Activity '{act.id}': Observation.ValueType may not be empty for type '{obs.type}'",
                        trace=(
                            f"Activity.ID: '{act.id}', Observation.Type: '{obs.type}'",
                            f"Observation.ValueType: '{obs.value_type}' → empty or whitespace → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2021-11-01, Activity.Code is 89-93, and Encounter.Type is not 3 or 4
    def _rule_306(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2021, 11, 1):
            return []
        _svc_codes = frozenset({"89", "90", "91", "92", "93"})
        auth = model.authorization
        enc = auth.encounter
        enc_type = enc.type if enc else None
        errors = []
        for act in auth.activities:
            if act.code in _svc_codes and enc_type not in (3, 4):
                errors.append(self._inactive_err(306, f"Authorization '{auth.id}', Activity '{act.id}': Service codes 89-93 can only be used with Encounter.Type 3 or 4",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Code: '{act.code}' (in 89-93 set)",
                        f"Encounter.Type: {enc_type} → not inpatient (3 or 4) → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) Pilot DRG facility, Encounter.Type 5/6, Drug activity with net not 0 or > 500
    def _rule_370(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        enc = auth.encounter
        if enc is None or enc.type not in (5, 6):
            return []
        try:
            if not res.is_orthopedic_drg_provider(enc.facility_id):
                return []
        except Exception:
            return []
        errors = []
        for act in auth.activities:
            try:
                included = res.is_included_drg_activity_code(act.code)
                excluded = res.is_excluded_drg_activity_code(act.code)
                if act.type == 5 and included and not excluded:
                    if act.net != 0 and act.net <= 500:
                        trace = (
                            f"FacilityID '{enc.facility_id}' → orthopedic DRG pilot provider ✓",
                            f"Encounter.Type = {enc.type} (5 or 6) ✓",
                            f"Activity.Type = 5 (Drug) ✓",
                            f"DRG included code: '{act.code}' → FOUND ✓",
                            f"DRG excluded code: '{act.code}' → NOT FOUND (not excluded) ✓",
                            f"Activity.Net = {act.net} → not 0 and ≤ 500 → VIOLATION (must be 0 or > 500)",
                        )
                        errors.append(self._inactive_err(370, f"Authorization '{auth.id}', Activity '{act.id}': Net must be 0 or > 500 for DRG Drug activity in pilot facility", trace=trace))
            except Exception:
                pass
        return errors

    # Fires when: (INACTIVE) Pilot DRG facility, Encounter.Type 5/6, Drug activity with net < 0
    def _rule_371(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        enc = auth.encounter
        if enc is None or enc.type not in (5, 6):
            return []
        try:
            if not res.is_orthopedic_drg_provider(enc.facility_id):
                return []
        except Exception:
            return []
        errors = []
        for act in auth.activities:
            try:
                included = res.is_included_drg_activity_code(act.code)
                excluded = res.is_excluded_drg_activity_code(act.code)
                if act.type == 9 and included and not excluded and act.net < 0:
                    trace = (
                        f"FacilityID '{enc.facility_id}' → orthopedic DRG pilot provider ✓",
                        f"Encounter.Type = {enc.type} (5 or 6) ✓",
                        f"Activity.Type = 9 (DRG) ✓",
                        f"DRG included code: '{act.code}' → FOUND ✓",
                        f"DRG excluded code: '{act.code}' → NOT FOUND (not excluded) ✓",
                        f"Activity.Net = {act.net} → negative → VIOLATION (must be ≥ 0)",
                    )
                    errors.append(self._inactive_err(371, f"Authorization '{auth.id}', Activity '{act.id}': Net must be >= 0 for DRG activity in pilot facility", trace=trace))
            except Exception:
                pass
        return errors

    # Fires when: (INACTIVE) Pilot DRG facility, Encounter.Type 5/6, HCPCS activity net != (TotalAmount - 1500*qty)
    def _rule_372(self, model: pq.PriorRequest, res) -> list:
        auth = model.authorization
        enc = auth.encounter
        if enc is None or enc.type not in (5, 6):
            return []
        try:
            if not res.is_orthopedic_drg_provider(enc.facility_id):
                return []
        except Exception:
            return []
        errors = []
        for act in auth.activities:
            try:
                included = res.is_included_drg_activity_code(act.code)
                excluded = res.is_excluded_drg_activity_code(act.code)
                if not (act.type == 4 and included and not excluded):
                    continue
                total_amount_obs = next((obs for obs in act.observations if obs.code == "TotalAmount" and obs.value), None)
                if total_amount_obs is None:
                    continue
                try:
                    total_amount = float(total_amount_obs.value)
                except (ValueError, TypeError):
                    continue
                qty = act.quantity if act.quantity else 0
                expected_net = total_amount - (1500 * qty)
                if abs(act.net - expected_net) > 0.001:
                    trace = (
                        f"FacilityID '{enc.facility_id}' → orthopedic DRG pilot provider ✓",
                        f"Encounter.Type = {enc.type} (5 or 6) ✓",
                        f"Activity.Type = 4 (HCPCS) ✓",
                        f"DRG included code: '{act.code}' → FOUND ✓",
                        f"DRG excluded code: '{act.code}' → NOT FOUND (not excluded) ✓",
                        f"TotalAmount observation = {total_amount}, Quantity = {qty}",
                        f"Expected Net = {total_amount} − (1500 × {qty}) = {expected_net:.4f}, Actual Net = {act.net} → mismatch → VIOLATION",
                    )
                    errors.append(self._inactive_err(372, f"Authorization '{auth.id}', Activity '{act.id}': Net must be (TotalAmount - 1500 * Quantity)", trace=trace))
            except Exception:
                pass
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2025-06-01, Trade Drug activity with UPP markup within tolerance, but ReceiverID not in (D001-D004)
    def _rule_377(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2025, 6, 1):
            return []
        receiver = model.header.receiver_id
        if receiver in ("D001", "D002", "D003", "D004"):
            return []
        auth = model.authorization
        if auth.resubmission and auth.resubmission.type == "internal complaint":
            return []
        _ALLOWED_PRICE_DIFF_PCT = 45.0
        for act in auth.activities:
            if act.type != 5 or act.net <= 0:
                continue
            try:
                pkg_markup_str = res.get_pkg_markup(act.code)
            except Exception:
                continue
            if not pkg_markup_str:
                continue
            try:
                pkg_markup = float(pkg_markup_str)
            except ValueError:
                continue
            if pkg_markup <= 0:
                continue
            qty = act.quantity if act.quantity else 0
            if qty == 0:
                continue
            unit_net = act.net / qty
            if abs(unit_net - pkg_markup) <= (pkg_markup / 100.0) * _ALLOWED_PRICE_DIFF_PCT:
                return [self._inactive_err(377, f"Authorization '{auth.id}': Header.ReceiverID must be in (D001, D002, D003, D004) when activities include UPP markup prices",
                    trace=(
                        f"Authorization.ID: '{auth.id}', Activity code: '{act.code}'",
                        f"ReceiverID: '{receiver}' → not in D001-D004",
                        f"Unit Net: {unit_net:.4f}, Package Markup: {pkg_markup:.4f}, Tolerance: {_ALLOWED_PRICE_DIFF_PCT}%",
                        f"Unit net within UPP markup tolerance but receiver not in allowed set → VIOLATION",
                    ))]
        return []

    # Fires when: (INACTIVE) TransactionDate >= 2025-06-01, Trade Drug activity where unit net >= both Package Markup and Price to Public
    def _rule_380(self, model: pq.PriorRequest, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2025, 6, 1):
            return []
        receiver = model.header.receiver_id
        if receiver not in ("D001", "D002", "D003", "D004"):
            return []
        auth = model.authorization
        if auth.resubmission and auth.resubmission.type == "internal complaint":
            return []
        errors = []
        for act in auth.activities:
            if act.type != 5 or act.net <= 0:
                continue
            try:
                pkg_markup_str = res.get_pkg_markup(act.code)
            except Exception:
                continue
            if not pkg_markup_str:
                continue
            try:
                pkg_markup = float(pkg_markup_str)
            except ValueError:
                continue
            if pkg_markup <= 0:
                continue
            qty = act.quantity if act.quantity else 0
            if qty == 0:
                continue
            unit_net = act.net / qty
            try:
                pkg_ptp_str = res.get_pkg_price_to_public(act.code)
                pkg_ptp = float(pkg_ptp_str) if pkg_ptp_str else None
            except Exception:
                pkg_ptp = None
            ptp_ok = pkg_ptp is not None and unit_net < pkg_ptp
            markup_ok = unit_net < pkg_markup
            if not ptp_ok and not markup_ok:
                errors.append(self._inactive_err(380, f"Authorization '{auth.id}', Activity '{act.id}': Quantity must be consistent with Net and Package Markup/Price to Public",
                    trace=(
                        f"Activity.ID: '{act.id}', Activity.Code: '{act.code}'",
                        f"Unit Net: {unit_net:.4f}, Package Markup: {pkg_markup:.4f}, Price to Public: {pkg_ptp}",
                        f"Unit Net >= Package Markup and Unit Net >= Price to Public → VIOLATION",
                    )))
        return errors


# ── RemittanceAdvice rules ─────────────────────────────────────────────────────

class _RemittanceAdviceValidator(_BaseValidator):
    TRANSACTION = "Remittance.Advice"

    _RULE_DESCRIPTIONS = {
        "9":   "Header.RecordCount does not match the actual number of Claim elements",
        "18":  "Activity.Type=2 (drug) code is not a valid Trade Drug or Generic Drug",
        "21":  "TransactionDate is before 2010-10-01 and a Claim.DenialCode is not registered",
        "30":  "DispositionFlag is not in the allowed set for Remittance.Advice (shadow flags are allowed)",
        "31":  "any Activity.Gross is negative",
        "34":  "(INACTIVE) Encounter.FacilityID is not in HAAD/DHA/MOH provider registry",
        "56":  "Header.SenderID is not a valid payer or TPA",
        "61":  "Header.TransactionDate does not match today's date",
        "62":  "any Activity.Type is outside allowed set {3,4,5,6,8,9}",
        "63":  "any Activity.Net is negative",
        "64":  "(INACTIVE) Activity.Start >= 2014-09-01 and Activity.Code is not a valid ICD9 code",
        "65":  "Activity.Type in {1,3,4,5,6,8,9} and code is not a valid CPT or HCPCS code",
        "66":  "Activity.Type=2 (drug) code is not a valid Trade Drug or Generic Drug",
        "67":  "Activity.Type=10 (dental) code is not a valid dental code",
        "68":  "Activity.ID is duplicated within a claim",
        "69":  "any Activity.Quantity is <= 0",
        "70":  "any Activity.Quantity is not a whole number",
        "71":  "any Activity.PaymentAmount is negative",
        "72":  "(INACTIVE) Activity.Clinician does not exist in HAAD/DHA/MOH registry or is inactive",
        "73":  "Activity.Start is before the Encounter.Start",
        "74":  "Activity.PaymentAmount exceeds Activity.Net",
        "75":  "Activity.DenialCode is present but not registered in master data",
        "76":  "(INACTIVE) Activity.Net is null",
        "77":  "(INACTIVE) Activity.PaymentAmount is null",
        "78":  "a DenialCode is present at Claim level (only allowed at Activity level in RA)",
        "79":  "Activity.Net ≠ PaymentAmount (after rounding to 2 dp) and no DenialCode is present",
        "80":  "(INACTIVE) Activity.Start is null",
        "87":  "Activity.Type=5 (service) code is not a valid Service code",
        "93":  "never fires — RA Activity has no Observation elements",
        "96":  "any Activity.PatientShare is negative",
        "98":  "no matching submitted Claim.Submission exists in the DB for this claim",
        "106": "RA activity details (type/net/quantity/clinicians) don't match the submitted Claim.Submission activity",
        "107": "Claim.IDPayer is missing or blank",
        "108": "IDPayer is duplicated within the same Remittance.Advice (per receiver)",
        "110": "Activity.Type=6 code is not a valid DRG code",
        "111": "never fires — RA Activity has no Observation elements",
        "113": "(INACTIVE) Activity.Type=3 and Activity.Code contains '-'",
        "114": "Claim.DenialCode is present but not registered in master data",
        "117": "Activity.Type=8 (drug) code is not a valid Trade Drug or Generic Drug",
        "123": "Claim.ProviderID is present but not a recognised facility license",
        "124": "(INACTIVE) TransactionDate >= 2014-06-01, sumActNet == sumPayAmt, but individual Activity.Net != Activity.PaymentAmount",
        "131": "(INACTIVE) TransactionDate >= 2011-06-15, Activity.Net=0 but Activity.DenialCode is set",
        "133": "Activity.Clinician is present but not an active clinician license",
        "134": "Activity.OrderingClinician is present but not an active clinician license",
        "135": "Encounter.FacilityID is present but not a recognised facility license",
        "137": "Claim.ID is missing or blank",
        "146": "Claim.DateSettlement is after TransactionDate",
        "147": "Activity.Start is after Claim.DateSettlement",
        "148": "Activity.PatientShare exceeds Activity.Gross",
        "151": "(INACTIVE) TransactionDate >= 2011-06-15 and Activity count <= 0",
        "187": "Activity.Type=9 code is not a valid Service code",
        "196": "RA takeback data lookup (currently a stub — no-op pending resource_provider fix)",
        "200": "Activity.Type=3 (CPT) code is in CPT exclusion list",
        "203": "Activity.Type=4 (HCPCS) code is in exclusion list 4",
        "204": "(INACTIVE) TransactionDate >= 2014-06-01, Activity.OrderingClinician is set but not in clinician registry",
        "205": "Activity.Type=5 (service) code is in service exclusion list 6",
        "206": "Activity.Type=3 (CPT) code is in HCPCS exclusion list 2",
        "207": "(INACTIVE) TransactionDate >= 2014-09-01, Activity.Start >= 2014-09-01, OrderingClinician is a pharmacist",
        "232": "Claim.IDPayer doesn't match the IDPayer stored on the original submitted claim",
        "235": "IDPayer is already used by another claim from the same payer",
        "293": "Activity.Type=4 (HCPCS) uses a CPT code (CPT/HCPCS separation, from 2020-06-01)",
        "294": "Activity.Type=3 (CPT) uses a pure HCPCS code (CPT/HCPCS separation, from 2020-06-01)",
        "311": "Claim.DenialCode is not active on the transaction date (from 2023-01-30)",
        "312": "Activity.DenialCode is not active on the transaction date (from 2023-01-30)",
        "379": "(INACTIVE) TransactionDate >= 2025-06-01, Trade Drug activity with UPP markup within tolerance, but SenderID not in (D001-D004, A001)",
    }

    _RA_ALLOWED_FLAGS = frozenset({
        "PTE_SUBMIT", "PTE_VALIDATE_ONLY", "PTE_RESPONSE",
        "PTE_SHADOW_NOT_FOR_PAYMENT_SUBMIT", "PTE_SHADOW_NOT_FOR_PAYMENT_VALIDATE_ONLY",
        "SHADOW_NOT_FOR_PAYMENT_SUBMIT", "SHADOW_NOT_FOR_PAYMENT_VALIDATE_ONLY",
    })
    _RA_ALLOWED_ACTIVITY_TYPES = frozenset({3, 4, 5, 6, 8, 9})
    _RA_VALID_DX_TYPES = frozenset({"Principal", "Secondary", "Admitting", "ReasonForVisit", "Discharge"})

    def _rules(self):
        return [
            self._rule_9,   self._rule_18,  self._rule_21,  self._rule_30,  self._rule_31,
            self._rule_34,  self._rule_56,  self._rule_61,  self._rule_62,  self._rule_63,
            self._rule_64,  self._rule_65,  self._rule_66,  self._rule_67,  self._rule_68,
            self._rule_69,  self._rule_70,  self._rule_71,  self._rule_72,  self._rule_73,
            self._rule_74,  self._rule_75,  self._rule_76,  self._rule_77,  self._rule_78,
            self._rule_79,  self._rule_80,  self._rule_87,  self._rule_93,  self._rule_96,
            self._rule_98,  self._rule_106, self._rule_107, self._rule_108, self._rule_110,
            self._rule_111, self._rule_113, self._rule_114, self._rule_117, self._rule_123,
            self._rule_124, self._rule_131, self._rule_133, self._rule_134, self._rule_135,
            self._rule_137, self._rule_146, self._rule_147, self._rule_148, self._rule_151,
            self._rule_187, self._rule_196, self._rule_200, self._rule_203, self._rule_204,
            self._rule_205, self._rule_206, self._rule_207, self._rule_232, self._rule_235,
            self._rule_293, self._rule_294, self._rule_311, self._rule_312, self._rule_379,
        ]

    # Fires when: Header.RecordCount does not match the actual number of Claim elements
    def _rule_9(self, model: ra.RemittanceAdvice, res) -> list:
        actual = len(model.claims)
        if model.header.record_count != actual:
            return [self._err(9, f"Header.RecordCount is {model.header.record_count} but {actual} Claim element(s) found",
                trace=(
                    f"Header.RecordCount: {model.header.record_count}",
                    f"Actual Claim elements found: {actual}",
                    f"Count mismatch → VIOLATION",
                ))]
        return []

    # Fires when: Activity.Type=2 (drug) code is not a valid Trade Drug or Generic Drug
    def _rule_18(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 2:
                    trade_ok = res.is_valid_trade_drug(act.code)
                    generic_ok = res.is_valid_generic_drug(act.code)
                    if not trade_ok and not generic_ok:
                        trace = (
                            f"Activity.Type = 2 (Drug) ✓",
                            f"Trade drug lookup: '{act.code}' → NOT FOUND",
                            f"Generic drug lookup: '{act.code}' → NOT FOUND",
                            f"Neither trade nor generic match → VIOLATION",
                        )
                        errors.append(self._err(18, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is not a valid drug code", trace=trace))
        return errors

    # Fires when: TransactionDate is before 2010-10-01 and a Claim.DenialCode is not registered
    def _rule_21(self, model: ra.RemittanceAdvice, res) -> list:
        tx_date = _parse_datetime(model.header.transaction_date)
        if tx_date is None or tx_date >= _RULE_21_CUTOFF:
            return []
        errors = []
        for claim in model.claims:
            if claim.denial_code:
                code_ok = res.is_valid_denial_code(claim.denial_code)
                if not code_ok:
                    trace = (
                        f"TransactionDate < 2010-10-01 ✓",
                        f"DenialCode present: '{claim.denial_code}'",
                        f"DenialCode lookup: NOT FOUND in denial code registry → VIOLATION",
                    )
                    errors.append(self._err(21, f"Claim '{claim.id}': DenialCode '{claim.denial_code}' is not a registered denial code", trace=trace))
        return errors

    # Fires when: DispositionFlag is not in the allowed set for Remittance.Advice (shadow flags are allowed)
    def _rule_30(self, model: ra.RemittanceAdvice, res) -> list:
        flag = model.header.disposition_flag
        if flag not in self._RA_ALLOWED_FLAGS:
            return [self._err(30, f"DispositionFlag '{flag}' is not an allowed value for Remittance.Advice",
                trace=(
                    f"Header.DispositionFlag: '{flag}'",
                    f"Allowed values: {sorted(self._RA_ALLOWED_FLAGS)}",
                    f"Value not in allowed set → VIOLATION",
                ))]
        return []

    # Fires when: any Activity.Gross is negative
    def _rule_31(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.gross is not None and act.gross < 0:
                    errors.append(self._err(31, f"Claim '{claim.id}', Activity '{act.id}': Gross must be >= 0",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.Gross: {act.gross} → negative → VIOLATION",
                        )))
        return errors

    # Fires when: Header.SenderID is not a valid payer or TPA
    def _rule_56(self, model: ra.RemittanceAdvice, res) -> list:
        sender = model.header.sender_id
        is_payer = res.is_haad_payer(sender)
        is_tpa = res.is_haad_tpa(sender)
        if not (is_payer or is_tpa):
            trace = (
                f"SenderID: '{sender}'",
                f"HAAD payer lookup: → {'YES ✓' if is_payer else 'NO'}",
                f"HAAD TPA lookup: → {'YES ✓' if is_tpa else 'NO'}",
                f"Neither payer nor TPA → VIOLATION",
            )
            return [self._err(56, f"Header.SenderID '{sender}' must be a valid payer or TPA for Remittance.Advice", trace=trace)]
        return []

    # Fires when: Header.TransactionDate does not match today's date
    def _rule_61(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None:
            return []
        if tx.date() != datetime.now().date():
            return [self._err(61, f"Header.TransactionDate '{model.header.transaction_date}' must match today's date",
                trace=(
                    f"Header.TransactionDate: '{model.header.transaction_date}' → parsed date: {tx.date()}",
                    f"Today's date: {datetime.now().date()}",
                    f"Date mismatch → VIOLATION",
                ))]
        return []

    # Fires when: any Activity.Type is outside allowed set {3,4,5,6,8,9}
    def _rule_62(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type not in self._RA_ALLOWED_ACTIVITY_TYPES:
                    errors.append(self._err(62, f"Claim '{claim.id}', Activity '{act.id}': Type {act.type} is not allowed in Remittance.Advice",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}', Activity.Type: {act.type}",
                            f"Allowed activity types: {sorted(self._RA_ALLOWED_ACTIVITY_TYPES)}",
                            f"Type not in allowed set → VIOLATION",
                        )))
        return errors

    # Fires when: any Activity.Net is negative
    def _rule_63(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.net < 0:
                    errors.append(self._err(63, f"Claim '{claim.id}', Activity '{act.id}': Net must be >= 0",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.Net: {act.net} → negative → VIOLATION",
                        )))
        return errors

    # Fires when: Activity.Type in {1,3,4,5,6,8,9} and code is not a valid CPT or HCPCS code
    def _rule_65(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type in (1, 3, 4, 5, 6, 8, 9):
                    cpt_ok = res.is_valid_cpt_code(act.code)
                    hcpcs_ok = res.is_valid_hcpcs_code(act.code)
                    if not cpt_ok and not hcpcs_ok:
                        trace = (
                            f"Activity.Type = {act.type} → CPT/HCPCS-compatible type ✓",
                            f"CPT lookup: '{act.code}' → NOT FOUND",
                            f"HCPCS lookup: '{act.code}' → NOT FOUND",
                            f"Neither CPT nor HCPCS match → VIOLATION",
                        )
                        errors.append(self._err(65, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is not a valid CPT/HCPCS code", trace=trace))
        return errors

    # Fires when: Activity.Type=2 (drug) code is not a valid Trade Drug or Generic Drug
    def _rule_66(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 2:
                    trade_ok = res.is_valid_trade_drug(act.code)
                    generic_ok = res.is_valid_generic_drug(act.code)
                    if not trade_ok and not generic_ok:
                        trace = (
                            f"Activity.Type = 2 (Drug) ✓",
                            f"Trade drug lookup: '{act.code}' → NOT FOUND",
                            f"Generic drug lookup: '{act.code}' → NOT FOUND",
                            f"Neither trade nor generic match → VIOLATION",
                        )
                        errors.append(self._err(66, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is not a valid drug code", trace=trace))
        return errors

    # Fires when: Activity.Type=10 (dental) code is not a valid dental code
    def _rule_67(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 10:
                    dental_ok = res.is_valid_dental_code(act.code)
                    if not dental_ok:
                        trace = (
                            f"Activity.Type = 10 (Dental) ✓",
                            f"Dental code lookup: '{act.code}' → NOT FOUND → VIOLATION",
                        )
                        errors.append(self._err(67, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is not a valid dental code", trace=trace))
        return errors

    # Fires when: Activity.ID is duplicated within a claim
    def _rule_68(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            seen = set()
            for act in claim.activities:
                if act.id in seen:
                    errors.append(self._err(68, f"Claim '{claim.id}', Activity '{act.id}': Activity ID is duplicated",
                        trace=(
                            f"Claim.ID: '{claim.id}'",
                            f"Activity.ID: '{act.id}' → already seen in this Claim → VIOLATION",
                        )))
                seen.add(act.id)
        return errors

    # Fires when: any Activity.Quantity is <= 0
    def _rule_69(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.quantity <= 0:
                    errors.append(self._err(69, f"Claim '{claim.id}', Activity '{act.id}': Quantity must be > 0",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.Quantity: {act.quantity} → must be > 0 → VIOLATION",
                        )))
        return errors

    # Fires when: any Activity.Quantity is not a whole number
    def _rule_70(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.quantity != int(act.quantity):
                    errors.append(self._err(70, f"Claim '{claim.id}', Activity '{act.id}': Quantity must be a whole number",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.Quantity: {act.quantity} → has fractional part ({act.quantity} ≠ {int(act.quantity)}) → VIOLATION",
                        )))
        return errors

    # Fires when: any Activity.PaymentAmount is negative
    def _rule_71(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.payment_amount < 0:
                    errors.append(self._err(71, f"Claim '{claim.id}', Activity '{act.id}': PaymentAmount must be >= 0",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.PaymentAmount: {act.payment_amount} → negative → VIOLATION",
                        )))
        return errors

    # Fires when: Activity.Start is before the Encounter.Start
    def _rule_73(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                start = _parse_datetime(act.start)
                if start is None:
                    continue
                enc = next((e for e in claim.encounters), None)
                if enc is None:
                    continue
                if hasattr(enc, 'start') and enc.start:
                    enc_start = _parse_datetime(enc.start)
                    if enc_start is not None and start < enc_start:
                        errors.append(self._err(73, f"Claim '{claim.id}', Activity '{act.id}': Start must be >= Encounter.Start",
                            trace=(
                                f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                                f"Activity.Start: '{act.start}' → {start}",
                                f"Encounter.Start: '{enc.start}' → {enc_start}",
                                f"Activity.Start < Encounter.Start → VIOLATION",
                            )))
        return errors

    # Fires when: Activity.PaymentAmount exceeds Activity.Net
    def _rule_74(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.payment_amount > act.net:
                    errors.append(self._err(74, f"Claim '{claim.id}', Activity '{act.id}': PaymentAmount {act.payment_amount} must be <= Net {act.net}",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.PaymentAmount: {act.payment_amount}, Activity.Net: {act.net}",
                            f"PaymentAmount > Net → VIOLATION",
                        )))
        return errors

    # Fires when: Activity.DenialCode is present but not registered in master data
    def _rule_75(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.denial_code:
                    code_ok = res.is_valid_denial_code(act.denial_code)
                    if not code_ok:
                        trace = (
                            f"Activity.DenialCode present: '{act.denial_code}'",
                            f"DenialCode lookup: NOT FOUND in denial code registry → VIOLATION",
                        )
                        errors.append(self._err(75, f"Claim '{claim.id}', Activity '{act.id}': DenialCode '{act.denial_code}' is not a registered denial code", trace=trace))
        return errors

    # Fires when: a DenialCode is present at Claim level (only allowed at Activity level in RA)
    def _rule_78(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            if claim.denial_code and claim.denial_code.strip():
                errors.append(self._err(78, f"Claim '{claim.id}': DenialCode at claim level must not be present in Remittance.Advice",
                    trace=(
                        f"Claim.ID: '{claim.id}', Claim.DenialCode: '{claim.denial_code}'",
                        f"DenialCode must only be on Activity elements in RA, not on Claim → VIOLATION",
                    )))
        return errors

    # Fires when: Activity.Net ≠ PaymentAmount (after rounding to 2 dp) and no DenialCode is present
    def _rule_79(self, model: ra.RemittanceAdvice, res) -> list:
        import decimal
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                net = decimal.Decimal(str(act.net)).quantize(
                    decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP)
                pmt = decimal.Decimal(str(act.payment_amount)).quantize(
                    decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP)
                if net != pmt and (not act.denial_code or not act.denial_code.strip()):
                    errors.append(self._err(79, f"Claim '{claim.id}', Activity '{act.id}': DenialCode is required when Net ({net}) != PaymentAmount ({pmt})",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.Net (rounded): {net}, Activity.PaymentAmount (rounded): {pmt}",
                            f"Net ≠ PaymentAmount and no DenialCode present → VIOLATION",
                        )))
        return errors

    # Fires when: Activity.Type=5 (service) code is not a valid Service code
    def _rule_87(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 5:
                    svc_ok = res.is_valid_service_code(act.code)
                    if not svc_ok:
                        trace = (
                            f"Activity.Type = 5 (Service) ✓",
                            f"Service code lookup: '{act.code}' → NOT FOUND → VIOLATION",
                        )
                        errors.append(self._err(87, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is not a valid service code", trace=trace))
        return errors

    # Fires when: never — RA Activity has no Observation elements; always returns []
    def _rule_93(self, model: ra.RemittanceAdvice, res) -> list:
        return []  # RA Activity has no Observation elements

    # Fires when: any Activity.PatientShare is negative
    def _rule_96(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.patient_share is not None and act.patient_share < 0:
                    errors.append(self._err(96, f"Claim '{claim.id}', Activity '{act.id}': PatientShare must be >= 0",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.PatientShare: {act.patient_share} → negative → VIOLATION",
                        )))
        return errors

    # Fires when: no matching submitted Claim.Submission exists in the DB for this claim
    def _rule_98(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            submitted = res.get_submitted_claim_for_ra(claim.id, claim.provider_id, model.header.sender_id)
            if submitted is None:
                errors.append(self._err(98, f"Claim '{claim.id}': No matching submitted claim found for this Remittance.Advice",
                    trace=(
                        f"Claim.ID: '{claim.id}', ProviderID: '{claim.provider_id}'",
                        f"SenderID: '{model.header.sender_id}'",
                        f"DB lookup for submitted claim → NOT FOUND → VIOLATION",
                    )))
        return errors

    # Fires when: RA activity details (type/net/quantity/clinicians) don't match the submitted Claim.Submission activity
    def _rule_106(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                submitted = res.get_submitted_claim_for_ra(claim.id, claim.provider_id, model.header.sender_id)
                if submitted is None:
                    continue
                if not res.ra_claim_activity_match_exists(
                        claim.id, claim.provider_id, act.id, act.type,
                        act.net, act.quantity, act.clinician, act.ordering_clinician):
                    errors.append(self._err(106, f"Claim '{claim.id}', Activity '{act.id}': activity details do not match submitted claim",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.Type: {act.type}, Net: {act.net}, Quantity: {act.quantity}",
                            f"Clinician: '{act.clinician}', OrderingClinician: '{act.ordering_clinician}'",
                            f"No matching activity found in submitted claim → VIOLATION",
                        )))
        return errors

    # Fires when: Claim.IDPayer is missing or blank
    def _rule_107(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            if not claim.id_payer or not claim.id_payer.strip():
                errors.append(self._err(107, f"Claim '{claim.id}': IDPayer may not be empty",
                    trace=(
                        f"Claim.ID: '{claim.id}'",
                        f"Claim.IDPayer: '{claim.id_payer}' → empty or whitespace → VIOLATION",
                    )))
        return errors

    # Fires when: IDPayer is duplicated within the same Remittance.Advice (per receiver)
    def _rule_108(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        seen = set()
        for claim in model.claims:
            idk = (claim.id_payer, model.header.receiver_id)
            if idk in seen:
                errors.append(self._err(108, f"Claim '{claim.id}': IDPayer '{claim.id_payer}' is duplicated in this Remittance.Advice",
                    trace=(
                        f"Claim.ID: '{claim.id}', IDPayer: '{claim.id_payer}'",
                        f"ReceiverID: '{model.header.receiver_id}'",
                        f"This (IDPayer, ReceiverID) pair already seen earlier → VIOLATION",
                    )))
            seen.add(idk)
        return errors

    # Fires when: Activity.Type=6 code is not a valid DRG code
    def _rule_110(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 6:
                    drg_ok = res.is_valid_drg_code(act.code)
                    if not drg_ok:
                        trace = (
                            f"Activity.Type = 6 (DRG) ✓",
                            f"DRG code lookup: '{act.code}' → NOT FOUND → VIOLATION",
                        )
                        errors.append(self._err(110, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is not a valid DRG code", trace=trace))
        return errors

    # Fires when: never — RA Activity has no Observation elements; always returns []
    def _rule_111(self, model: ra.RemittanceAdvice, res) -> list:
        return []  # RA Activity has no Observation elements

    # Fires when: Claim.DenialCode is present but not registered in master data
    def _rule_114(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            if claim.denial_code:
                code_ok = res.is_valid_denial_code(claim.denial_code)
                if not code_ok:
                    trace = (
                        f"Claim.DenialCode present: '{claim.denial_code}'",
                        f"DenialCode lookup: NOT FOUND in denial code registry → VIOLATION",
                    )
                    errors.append(self._err(114, f"Claim '{claim.id}': DenialCode '{claim.denial_code}' is not a registered denial code", trace=trace))
        return errors

    # Fires when: Activity.Type=8 (drug) code is not a valid Trade Drug or Generic Drug
    def _rule_117(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 8:
                    trade_ok = res.is_valid_trade_drug(act.code)
                    generic_ok = res.is_valid_generic_drug(act.code)
                    if not trade_ok and not generic_ok:
                        trace = (
                            f"Activity.Type = 8 (Drug) ✓",
                            f"Trade drug lookup: '{act.code}' → NOT FOUND",
                            f"Generic drug lookup: '{act.code}' → NOT FOUND",
                            f"Neither trade nor generic match → VIOLATION",
                        )
                        errors.append(self._err(117, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is not a valid drug code (type 8)", trace=trace))
        return errors

    # Fires when: Claim.ProviderID is present but not a recognised facility license
    def _rule_123(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            if claim.provider_id:
                fac_ok = res.is_any_provider(claim.provider_id)
                if not fac_ok:
                    trace = (
                        f"Claim.ProviderID present: '{claim.provider_id}'",
                        f"Provider registry lookup: NOT FOUND → VIOLATION",
                    )
                    errors.append(self._err(123, f"Claim '{claim.id}': ProviderID '{claim.provider_id}' is not a valid provider license", trace=trace))
        return errors

    # Fires when: Activity.Clinician is present but not an active clinician license
    def _rule_133(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.clinician:
                    clin_ok = res.is_active_clinician(act.clinician)
                    if not clin_ok:
                        trace = (
                            f"Activity.Clinician present: '{act.clinician}'",
                            f"Clinician registry lookup: NOT FOUND or inactive → VIOLATION",
                        )
                        errors.append(self._err(133, f"Claim '{claim.id}', Activity '{act.id}': Clinician '{act.clinician}' is not an active clinician", trace=trace))
        return errors

    # Fires when: Activity.OrderingClinician is present but not an active clinician license
    def _rule_134(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.ordering_clinician:
                    clin_ok = res.is_active_clinician(act.ordering_clinician)
                    if not clin_ok:
                        trace = (
                            f"Activity.OrderingClinician present: '{act.ordering_clinician}'",
                            f"Clinician registry lookup: NOT FOUND or inactive → VIOLATION",
                        )
                        errors.append(self._err(134, f"Claim '{claim.id}', Activity '{act.id}': OrderingClinician '{act.ordering_clinician}' is not an active clinician", trace=trace))
        return errors

    # Fires when: Encounter.FacilityID is present but not a recognised facility license
    def _rule_135(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for enc in claim.encounters:
                if enc.facility_id:
                    fac_ok = res.is_any_provider(enc.facility_id)
                    if not fac_ok:
                        trace = (
                            f"Encounter.FacilityID present: '{enc.facility_id}'",
                            f"Provider registry lookup: NOT FOUND → VIOLATION",
                        )
                        errors.append(self._err(135, f"Claim '{claim.id}': Encounter.FacilityID '{enc.facility_id}' is not a valid facility", trace=trace))
        return errors

    # Fires when: Claim.ID is missing or blank
    def _rule_137(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            if not claim.id or not claim.id.strip():
                errors.append(self._err(137, f"Claim ID may not be empty",
                    trace=(
                        f"Claim.ID: '{claim.id}' → empty or whitespace → VIOLATION",
                    )))
        return errors

    # Fires when: Claim.DateSettlement is after TransactionDate
    def _rule_146(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            start = _parse_datetime(claim.date_settlement) if claim.date_settlement else None
            if start is None:
                continue
            tx = _parse_datetime(model.header.transaction_date)
            if tx is not None and start > tx:
                errors.append(self._err(146, f"Claim '{claim.id}': DateSettlement must be <= TransactionDate",
                    trace=(
                        f"Claim.ID: '{claim.id}'",
                        f"Claim.DateSettlement: '{claim.date_settlement}' → {start}",
                        f"Header.TransactionDate: '{model.header.transaction_date}' → {tx}",
                        f"DateSettlement > TransactionDate → VIOLATION",
                    )))
        return errors

    # Fires when: Activity.Start is after Claim.DateSettlement
    def _rule_147(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                start = _parse_datetime(act.start)
                ds = _parse_datetime(claim.date_settlement) if claim.date_settlement else None
                if start is not None and ds is not None and start > ds:
                    errors.append(self._err(147, f"Claim '{claim.id}', Activity '{act.id}': Start must be <= DateSettlement",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.Start: '{act.start}' → {start}",
                            f"Claim.DateSettlement: '{claim.date_settlement}' → {ds}",
                            f"Activity.Start > DateSettlement → VIOLATION",
                        )))
        return errors

    # Fires when: Activity.PatientShare exceeds Activity.Gross
    def _rule_148(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.patient_share is not None and act.patient_share > act.gross if act.gross is not None else False:
                    errors.append(self._err(148, f"Claim '{claim.id}', Activity '{act.id}': PatientShare must be <= Gross",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.PatientShare: {act.patient_share}, Activity.Gross: {act.gross}",
                            f"PatientShare > Gross → VIOLATION",
                        )))
        return errors

    # Fires when: Activity.Type=9 code is not a valid Service code
    def _rule_187(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 9:
                    svc_ok = res.is_valid_service_code(act.code)
                    if not svc_ok:
                        trace = (
                            f"Activity.Type = 9 (Service) ✓",
                            f"Service code lookup: '{act.code}' → NOT FOUND → VIOLATION",
                        )
                        errors.append(self._err(187, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is not a valid service code (type 9)", trace=trace))
        return errors

    # Fires when: RA takeback data lookup returns None (currently a stub — no-op)
    def _rule_196(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            takeback = res.get_ra_takeback_data(claim.id, claim.provider_id, None)
            if takeback is None:
                continue
        return errors

    # Fires when: Activity.Type=3 (CPT) code is in CPT exclusion list
    def _rule_200(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 3:
                    in_excl = res.in_exclusion_list_1(act.code)
                    if in_excl:
                        trace = (
                            f"Activity.Type = 3 (CPT) ✓",
                            f"CPT exclusion list 1: '{act.code}' → FOUND → VIOLATION",
                        )
                        errors.append(self._err(200, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is in CPT exclusion list", trace=trace))
        return errors

    # Fires when: Activity.Type=4 (HCPCS) code is in exclusion list 4
    def _rule_203(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 4:
                    in_excl = res.in_exclusion_list_4(act.code)
                    if in_excl:
                        trace = (
                            f"Activity.Type = 4 (HCPCS) ✓",
                            f"HCPCS exclusion list 4: '{act.code}' → FOUND → VIOLATION",
                        )
                        errors.append(self._err(203, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is in exclusion list 4", trace=trace))
        return errors

    # Fires when: Activity.Type=5 (service) code is in service exclusion list 6
    def _rule_205(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 5:
                    in_excl = res.in_exclusion_list_6(act.code)
                    if in_excl:
                        trace = (
                            f"Activity.Type = 5 (Service) ✓",
                            f"Service exclusion list 6: '{act.code}' → FOUND → VIOLATION",
                        )
                        errors.append(self._err(205, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is in service exclusion list", trace=trace))
        return errors

    # Fires when: Activity.Type=3 (CPT) code is in HCPCS exclusion list 2
    def _rule_206(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 3:
                    in_excl = res.in_exclusion_list_2(act.code)
                    if in_excl:
                        trace = (
                            f"Activity.Type = 3 (CPT) ✓",
                            f"HCPCS exclusion list 2: '{act.code}' → FOUND → VIOLATION",
                        )
                        errors.append(self._err(206, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is in HCPCS exclusion list", trace=trace))
        return errors

    # Fires when: Claim.IDPayer doesn't match the IDPayer stored on the original submitted claim
    def _rule_232(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            submitted = res.get_submitted_claim_for_ra(claim.id, claim.provider_id, model.header.sender_id)
            if submitted is None:
                continue
            created_on = res.get_submitted_claim_created_on(claim.id, claim.provider_id, model.header.sender_id)
            if created_on is None:
                continue
            id_payer_in_cs = res.get_submitted_claim_id_payer(claim.id, claim.provider_id, model.header.sender_id, created_on)
            if id_payer_in_cs and id_payer_in_cs != claim.id_payer:
                errors.append(self._err(232, f"Claim '{claim.id}': IDPayer '{claim.id_payer}' does not match the IDPayer in submitted claim",
                    trace=(
                        f"Claim.ID: '{claim.id}', ProviderID: '{claim.provider_id}'",
                        f"RA Claim.IDPayer: '{claim.id_payer}'",
                        f"Submitted Claim IDPayer: '{id_payer_in_cs}'",
                        f"IDPayer mismatch between RA and original submission → VIOLATION",
                    )))
        return errors

    # Fires when: IDPayer is already used by another claim from the same payer
    def _rule_235(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            if res.is_id_payer_used_by_other_claim(claim.id_payer, model.header.receiver_id, claim.id):
                errors.append(self._err(235, f"Claim '{claim.id}': IDPayer '{claim.id_payer}' is already used by another claim from this payer",
                    trace=(
                        f"Claim.ID: '{claim.id}', IDPayer: '{claim.id_payer}'",
                        f"ReceiverID (payer): '{model.header.receiver_id}'",
                        f"Another claim already uses this IDPayer for this payer → VIOLATION",
                    )))
        return errors

    # Fires when: Activity.Type=4 (HCPCS) uses a CPT code (CPT/HCPCS separation, from 2020-06-01)
    def _rule_293(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2020, 6, 1):
            return []
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 4:
                    is_cpt = res.is_valid_cpt_code(act.code)
                    if is_cpt:
                        trace = (
                            f"TransactionDate ≥ 2020-06-01 ✓",
                            f"Activity.Type = 4 (HCPCS) ✓",
                            f"CPT lookup: '{act.code}' → FOUND → CPT code cannot be used in a HCPCS activity → VIOLATION",
                        )
                        errors.append(self._err(293, f"Claim '{claim.id}', Activity '{act.id}': HCPCS activity cannot use a CPT code", trace=trace))
        return errors

    # Fires when: Activity.Type=3 (CPT) uses a pure HCPCS code (CPT/HCPCS separation, from 2020-06-01)
    def _rule_294(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2020, 6, 1):
            return []
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 3:
                    is_hcpcs = res.is_valid_hcpcs_code(act.code)
                    is_cpt = res.is_valid_cpt_code(act.code)
                    if is_hcpcs and not is_cpt:
                        trace = (
                            f"TransactionDate ≥ 2020-06-01 ✓",
                            f"Activity.Type = 3 (CPT) ✓",
                            f"HCPCS lookup: '{act.code}' → FOUND",
                            f"CPT lookup: '{act.code}' → NOT FOUND",
                            f"Pure HCPCS code in a CPT activity → VIOLATION",
                        )
                        errors.append(self._err(294, f"Claim '{claim.id}', Activity '{act.id}': CPT activity cannot use a pure HCPCS code", trace=trace))
        return errors

    # Fires when: Claim.DenialCode is not active on the transaction date (from 2023-01-30)
    def _rule_311(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 1, 30):
            return []
        tx_str = tx.strftime("%Y-%m-%d")
        errors = []
        for claim in model.claims:
            if claim.denial_code and claim.denial_code.strip():
                code_ok = res.is_denial_code_valid_on_date(claim.denial_code, tx)
                if not code_ok:
                    trace = (
                        f"TransactionDate = {tx_str} ≥ 2023-01-30 ✓",
                        f"Claim.DenialCode present: '{claim.denial_code}'",
                        f"DenialCode on {tx_str}: NOT FOUND or not active → VIOLATION",
                    )
                    errors.append(self._err(311, f"Claim '{claim.id}': DenialCode '{claim.denial_code}' is not active on transaction date", trace=trace))
        return errors

    # Fires when: Activity.DenialCode is not active on the transaction date (from 2023-01-30)
    def _rule_312(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2023, 1, 30):
            return []
        tx_str = tx.strftime("%Y-%m-%d")
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.denial_code and act.denial_code.strip():
                    code_ok = res.is_denial_code_valid_on_date(act.denial_code, tx)
                    if not code_ok:
                        trace = (
                            f"TransactionDate = {tx_str} ≥ 2023-01-30 ✓",
                            f"Activity.DenialCode present: '{act.denial_code}'",
                            f"DenialCode on {tx_str}: NOT FOUND or not active → VIOLATION",
                        )
                        errors.append(self._err(312, f"Claim '{claim.id}', Activity '{act.id}': DenialCode '{act.denial_code}' is not active on transaction date", trace=trace))
        return errors

    # Fires when: (INACTIVE) Encounter.FacilityID is not in HAAD/DHA/MOH provider registry
    def _rule_34(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for enc in claim.encounters:
                fid = enc.facility_id
                if fid and fid.strip() and not fid.startswith("@"):
                    fac_ok = res.is_any_provider(fid)
                    if not fac_ok:
                        trace = (
                            f"Encounter.FacilityID present and not placeholder: '{fid}'",
                            f"Provider registry lookup: NOT FOUND → VIOLATION",
                        )
                        errors.append(self._inactive_err(34, f"Claim '{claim.id}': Encounter.FacilityID '{fid}' is not a valid HAAD/DHA/MOH facility", trace=trace))
        return errors

    # Fires when: (INACTIVE) Activity.Start >= 2014-09-01 and Activity.Code is not a valid ICD9 code
    def _rule_64(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                act_start = _parse_datetime(act.start)
                if act_start is None or act_start < datetime(2014, 9, 1):
                    continue
                icd9_ok = res.is_valid_icd9_code(act.code)
                if not icd9_ok:
                    trace = (
                        f"Activity.Start = '{act.start}' ≥ 2014-09-01 ✓",
                        f"ICD9 lookup: code = '{act.code}' → NOT FOUND in HIB_MDM.ICD09 (or IsActive ≠ 1) → VIOLATION",
                        f"Note: codes are case-sensitive. Verify exact casing and IsActive flag in the DB.",
                    )
                    errors.append(self._inactive_err(64, f"Claim '{claim.id}', Activity '{act.id}': Code '{act.code}' is not a valid ICD9 code", trace=trace))
        return errors

    # Fires when: (INACTIVE) Activity.Clinician does not exist in HAAD/DHA/MOH registry or is inactive
    def _rule_72(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.clinician and act.clinician.strip():
                    try:
                        clin_ok = res.is_active_clinician(act.clinician)
                        if not clin_ok:
                            trace = (
                                f"Activity.Clinician present: '{act.clinician}'",
                                f"Clinician registry lookup: NOT FOUND or inactive → VIOLATION",
                            )
                            errors.append(self._inactive_err(72, f"Claim '{claim.id}', Activity '{act.id}': Clinician '{act.clinician}' is not a valid or active clinician", trace=trace))
                    except Exception:
                        pass
        return errors

    # Fires when: (INACTIVE) Activity.Net is null
    def _rule_76(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.net is None:
                    errors.append(self._inactive_err(76, f"Claim '{claim.id}', Activity '{act.id}': Net may not be null",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.Net is None → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Activity.PaymentAmount is null
    def _rule_77(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.payment_amount is None:
                    errors.append(self._inactive_err(77, f"Claim '{claim.id}', Activity '{act.id}': PaymentAmount may not be null",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.PaymentAmount is None → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Activity.Start is null
    def _rule_80(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if not act.start or not act.start.strip():
                    errors.append(self._inactive_err(80, f"Claim '{claim.id}', Activity '{act.id}': Start may not be null",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.Start: '{act.start}' → empty or None → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) Activity.Type=3 and Activity.Code contains '-'
    def _rule_113(self, model: ra.RemittanceAdvice, res) -> list:
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type == 3 and "-" in act.code:
                    errors.append(self._inactive_err(113, f"Claim '{claim.id}', Activity '{act.id}': Code must not contain modifier when Activity.Type=3 (CPT)",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}', Activity.Type: 3 (CPT)",
                            f"Activity.Code: '{act.code}' → contains '-' modifier → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2014-06-01, sumActNet == sumPayAmt, but individual Activity.Net != Activity.PaymentAmount
    def _rule_124(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 6, 1):
            return []
        errors = []
        for claim in model.claims:
            sum_net = sum(act.net for act in claim.activities)
            sum_pay = sum(act.payment_amount for act in claim.activities)
            if abs(sum_net - sum_pay) > 0.001:
                continue
            for act in claim.activities:
                act_start = _parse_datetime(act.start)
                if act_start is not None and act_start >= datetime(2014, 6, 1):
                    if abs(act.net - act.payment_amount) > 0.001:
                        errors.append(self._inactive_err(124, f"Claim '{claim.id}', Activity '{act.id}': PaymentAmount must equal Net when claim totals match",
                            trace=(
                                f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                                f"Claim sum(Net) = {sum_net:.4f}, sum(PaymentAmount) = {sum_pay:.4f} → totals match",
                                f"Activity.Net: {act.net}, Activity.PaymentAmount: {act.payment_amount} → mismatch → VIOLATION",
                            )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2011-06-15, Activity.Net=0 but Activity.DenialCode is set
    def _rule_131(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.net == 0 and act.denial_code and act.denial_code.strip():
                    errors.append(self._inactive_err(131, f"Claim '{claim.id}', Activity '{act.id}': DenialCode must be empty when Net is zero",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}'",
                            f"Activity.Net: 0, Activity.DenialCode: '{act.denial_code}' → DenialCode present → VIOLATION",
                        )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2011-06-15 and Activity count <= 0
    def _rule_151(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2011, 6, 15):
            return []
        errors = []
        for claim in model.claims:
            if len(claim.activities) <= 0:
                errors.append(self._inactive_err(151, f"Claim '{claim.id}': Activity list must have at least one entry",
                    trace=(
                        f"Claim.ID: '{claim.id}'",
                        f"Activity count: 0 → must be > 0 → VIOLATION",
                    )))
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2014-06-01, Encounter.Start >= 2014-06-01, Activity.OrderingClinician is set but not in clinician registry
    def _rule_204(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 6, 1):
            return []
        errors = []
        for claim in model.claims:
            for enc in claim.encounters:
                pass
            for act in claim.activities:
                act_start = _parse_datetime(act.start)
                if act_start is None or act_start < datetime(2014, 6, 1):
                    continue
                if not act.ordering_clinician or not act.ordering_clinician.strip():
                    continue
                try:
                    clin_ok = res.is_active_clinician(act.ordering_clinician)
                    if not clin_ok:
                        trace = (
                            f"TransactionDate ≥ 2014-06-01 ✓",
                            f"Activity.Start = '{act.start}' ≥ 2014-06-01 ✓",
                            f"Activity.OrderingClinician present: '{act.ordering_clinician}'",
                            f"Clinician registry lookup: NOT FOUND or inactive → VIOLATION",
                        )
                        errors.append(self._inactive_err(204, f"Claim '{claim.id}', Activity '{act.id}': OrderingClinician '{act.ordering_clinician}' is not a valid clinician", trace=trace))
                except Exception:
                    pass
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2014-09-01, Activity.Start >= 2014-09-01, OrderingClinician is a pharmacist
    def _rule_207(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2014, 9, 1):
            return []
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                act_start = _parse_datetime(act.start)
                if act_start is None or act_start < datetime(2014, 9, 1):
                    continue
                if not act.ordering_clinician or not act.ordering_clinician.strip():
                    continue
                try:
                    clin_ok = res.is_active_clinician(act.ordering_clinician)
                    is_pharm = res.is_clinician_pharmacist(act.ordering_clinician)
                    if clin_ok and is_pharm:
                        trace = (
                            f"TransactionDate ≥ 2014-09-01 ✓",
                            f"Activity.Start = '{act.start}' ≥ 2014-09-01 ✓",
                            f"Activity.OrderingClinician present: '{act.ordering_clinician}'",
                            f"Clinician registry lookup: FOUND and active ✓",
                            f"Pharmacist check: '{act.ordering_clinician}' → IS a pharmacist → VIOLATION",
                        )
                        errors.append(self._inactive_err(207, f"Claim '{claim.id}', Activity '{act.id}': OrderingClinician '{act.ordering_clinician}' must not be a pharmacist", trace=trace))
                except Exception:
                    pass
        return errors

    # Fires when: (INACTIVE) TransactionDate >= 2025-06-01, Trade Drug activity with UPP markup within tolerance, but SenderID not in (D001-D004, A001)
    def _rule_379(self, model: ra.RemittanceAdvice, res) -> list:
        tx = _parse_datetime(model.header.transaction_date)
        if tx is None or tx < datetime(2025, 6, 1):
            return []
        sender = model.header.sender_id
        if sender in ("D001", "D002", "D003", "D004", "A001"):
            return []
        _ALLOWED_PRICE_DIFF_PCT = 45.0
        errors = []
        for claim in model.claims:
            for act in claim.activities:
                if act.type != 5 or act.net <= 0:
                    continue
                try:
                    pkg_markup_str = res.get_pkg_markup(act.code)
                except Exception:
                    continue
                if not pkg_markup_str:
                    continue
                try:
                    pkg_markup = float(pkg_markup_str)
                except ValueError:
                    continue
                if pkg_markup <= 0:
                    continue
                if act.quantity == 0:
                    continue
                unit_net = act.net / act.quantity
                try:
                    pkg_ptp_str = res.get_pkg_price_to_public(act.code)
                    pkg_ptp = float(pkg_ptp_str) if pkg_ptp_str else None
                except Exception:
                    pkg_ptp = None
                ptp_valid = pkg_ptp is not None and abs(unit_net - pkg_ptp) <= (pkg_ptp / 100.0) * _ALLOWED_PRICE_DIFF_PCT
                markup_valid = abs(unit_net - pkg_markup) <= (pkg_markup / 100.0) * _ALLOWED_PRICE_DIFF_PCT
                if not ptp_valid and markup_valid:
                    errors.append(self._inactive_err(379, f"Claim '{claim.id}', Activity '{act.id}': Header.SenderID must be D001-D004 or A001 when activities include UPP markup prices",
                        trace=(
                            f"Claim.ID: '{claim.id}', Activity.ID: '{act.id}', Activity.Code: '{act.code}'",
                            f"SenderID: '{sender}' → not in D001-D004/A001",
                            f"Unit Net: {unit_net:.4f}, Package Markup: {pkg_markup:.4f}, Tolerance: {_ALLOWED_PRICE_DIFF_PCT}%",
                            f"Unit net within UPP markup tolerance but sender not in allowed set → VIOLATION",
                        )))
        return errors


# ── Register validators ────────────────────────────────────────────────────────

RulesValidator._VALIDATORS = {
    cs.ClaimSubmission:    _ClaimSubmissionValidator,
    pr.PersonRegister:     _PersonRegisterValidator,
    pa.PriorAuthorization: _PriorAuthorizationValidator,
    pq.PriorRequest:       _PriorRequestValidator,
    ra.RemittanceAdvice:   _RemittanceAdviceValidator,
}

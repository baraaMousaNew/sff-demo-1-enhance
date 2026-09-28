"""
DB resource provider — parameterized EXISTS queries, per-value cached.

Every check method issues one parameterized query the first time a value is looked up,
then caches the boolean result. Subsequent calls for the same value are free.
Call clear() between validation sessions to reset the cache.
"""

from datetime import datetime


def _parse_db_date(val) -> "datetime | None":
    """Coerce a DB column value (str, date, datetime, or None) to datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if hasattr(val, "year"):          # datetime.date
        return datetime(val.year, val.month, val.day)
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

# ── Hardcoded value sets (no DB queries needed) ───────────────────────────────

_TWIN_ICD10_CODES = frozenset({
    "Z38.30", "Z38.31", "Z38.4",  "Z38.5",  "Z38.61", "Z38.62", "Z38.63",
    "Z38.64", "Z38.65", "Z38.66", "Z38.68", "Z38.69", "Z38.7",  "Z38.8",
})

_TWIN_ICD9_CODES = frozenset({
    "V31.00", "V31.01", "V31.1", "V31.2",
    "V32.00", "V32.01", "V32.1", "V32.2",
    "V33.00", "V33.01", "V33.1", "V33.2",
    "V34.00", "V34.01", "V34.1", "V34.2",
    "V35.00", "V35.01", "V35.1", "V35.2",
    "V36.00", "V36.01", "V36.1", "V36.2",
    "V37.00", "V37.01", "V37.1", "V37.2",
})


class ResourceProvider:

    def __init__(self, db_client):
        self._db = db_client
        self._cache: dict = {}

    def clear(self):
        self._cache.clear()

    # ── Internal helper ───────────────────────────────────────────────────────

    def _exists(self, key: str, sql: str, params: list) -> bool:
        """Run a parameterized query; cache the bool result by (key, *params)."""
        cache_key = (key, *params)
        if cache_key not in self._cache:
            rows = self._db.execute_query(sql, params)
            self._cache[cache_key] = len(rows) > 0
        return self._cache[cache_key]

    def _row(self, key: str, sql: str, params: list) -> "dict | None":
        """Fetch first row dict; cache result. Returns None if no rows."""
        cache_key = ("_row", key, *params)
        if cache_key not in self._cache:
            rows = self._db.execute_query(sql, params)
            self._cache[cache_key] = rows[0] if rows else None
        return self._cache[cache_key]

    def _is_tariff_row_valid_on_date(self, row: "dict | None", activity_start: datetime) -> bool:
        """Return True if a MandatoryTariff row covers activity_start."""
        if row is None:
            return False
        eff = _parse_db_date(row.get("EffectiveDate"))
        if eff is None:
            return False
        if activity_start < eff:
            return False
        exp = _parse_db_date(row.get("ExpiryDate"))
        if exp is not None and activity_start > exp:
            return False
        return True

    # ── 1. Provider / Payer classification lists ──────────────────────────────

    def is_haad_provider(self, license_id: str) -> bool:
        return self._exists("haad_provider",
            "SELECT 1 FROM HIB_MDM.LicenseFacilities WHERE FacilityLicenseId = ?",
            [license_id])

    def is_dha_provider(self, license_id: str) -> bool:
        return self._exists("dha_provider",
            "SELECT 1 FROM HIB_MDM.LicenseDHA WHERE FacilityLicense = ?",
            [license_id])

    def is_moh_provider(self, license_id: str) -> bool:
        return self._exists("moh_provider",
            "SELECT 1 FROM HIB_MDM.LicenseMOH WHERE FacilityLicense = ?",
            [license_id])

    def is_any_provider(self, license_id: str) -> bool:
        """True if license_id belongs to HAAD, DHA, or MOH provider."""
        return (self.is_haad_provider(license_id)
                or self.is_dha_provider(license_id)
                or self.is_moh_provider(license_id))

    def is_haad_payer(self, license_id: str) -> bool:
        return self._exists("haad_payer",
            "SELECT 1 FROM HIB_MDM.InsurancePayers WHERE Classification = 'Insurance' AND AuthNumber = ?",
            [license_id])

    def is_haad_tpa(self, license_id: str) -> bool:
        return self._exists("haad_tpa",
            "SELECT 1 FROM HIB_MDM.InsurancePayers WHERE Classification = 'TPA' AND AuthNumber = ?",
            [license_id])

    # ── 2. Live registry lookups ───────────────────────────────────────────────

    def is_active_provider(self, license_id: str) -> bool:
        return self._exists("active_provider",
            "SELECT 1 FROM HIB_MDM.LicenseFacilities WHERE IsActive > 0 AND FacilityLicenseId = ?",
            [license_id])

    def is_active_insurer(self, license_id: str) -> bool:
        return self._exists("active_insurer",
            "SELECT 1 FROM HIB_MDM.InsurancePayers WHERE Classification = 'Insurance' AND IsActive > 0 AND AuthNumber = ?",
            [license_id])

    def is_active_tpa(self, license_id: str) -> bool:
        return self._exists("active_tpa",
            "SELECT 1 FROM HIB_MDM.InsurancePayers WHERE Classification = 'TPA' AND IsActive > 0 AND AuthNumber = ?",
            [license_id])

    def is_dha_moh_provider(self, license_id: str) -> bool:
        return self._exists("dha_moh_provider",
            "SELECT 1 FROM HIB_MDM.LicenseDHA WHERE FacilityLicense = ?"
            " UNION "
            "SELECT 1 FROM HIB_MDM.LicenseMOH WHERE FacilityLicense = ?",
            [license_id, license_id])

    def is_active_clinician(self, clinician_id: str) -> bool:
        # ClinicianLicenseHistory has one row per status change; active = most-recent row is 'Active'.
        return self._exists("active_clinician",
            "SELECT 1 FROM HIB_MDM.ClinicianLicenseHistory"
            " WHERE ClinicianLicense = ? AND Description = 'Active'"
            " AND EffectiveDate = ("
            "   SELECT MAX(EffectiveDate) FROM HIB_MDM.ClinicianLicenseHistory"
            "   WHERE ClinicianLicense = ?)",
            [clinician_id, clinician_id])

    def is_valid_payer(self, license_id: str) -> bool:
        """True if license_id is a HAAD payer, HAAD TPA, or active insurer."""
        return (self.is_haad_payer(license_id)
                or self.is_haad_tpa(license_id)
                or self.is_active_insurer(license_id))

    # ── 3. Tariff / medical code lists ────────────────────────────────────────

    def is_valid_cpt_code(self, code: str) -> bool:
        return self._exists("cpt_code",
            "SELECT 1 FROM HIB_MDM.MandatoryTariff WHERE \"Type\" = 'CPT' AND Code = ?",
            [code])

    def is_valid_hcpcs_code(self, code: str) -> bool:
        return self._exists("hcpcs_code",
            "SELECT 1 FROM HIB_MDM.MandatoryTariff WHERE \"Type\" = 'HCPCS' AND Code = ?",
            [code])

    def is_valid_trade_drug(self, code: str) -> bool:
        # A drug is active as long as it has no DeleteEffectiveDate set.
        return self._exists("trade_drug",
            "SELECT 1 FROM HIB_MDM.Drugs WHERE DrugCode = ? AND DeleteEffectiveDate IS NULL",
            [code])

    def is_valid_dental_code(self, code: str) -> bool:
        return self._exists("dental_code",
            "SELECT 1 FROM HIB_MDM.MandatoryTariff WHERE \"Type\" = 'USCLS' AND Code = ?",
            [code])

    def is_valid_service_code(self, code: str) -> bool:
        return self._exists("service_code",
            "SELECT 1 FROM HIB_MDM.MandatoryTariff WHERE \"Type\" = 'Service' AND Code = ?",
            [code])

    def is_valid_generic_drug(self, code: str) -> bool:
        # A drug is active as long as it has no DeleteEffectiveDate set.
        return self._exists("generic_drug",
            "SELECT 1 FROM HIB_MDM.Drugs WHERE OldDrugCode = ? AND DeleteEffectiveDate IS NULL",
            [code])

    def is_valid_drg_code(self, code: str) -> bool:
        return self._exists("drg_code",
            "SELECT 1 FROM HIB_MDM.MandatoryTariff WHERE \"Type\" = 'DRG' AND Code = ?",
            [code])

    # ── 4. Diagnosis codes ────────────────────────────────────────────────────

    def is_valid_icd9_code(self, code: str) -> bool:
        return self._exists("icd9_code",
            "SELECT 1 FROM HIB_MDM.ICD09 WHERE DiagnosisCode = ? AND IsActive > 0",
            [code])

    def is_valid_icd10_code(self, code: str) -> bool:
        return self._exists("icd10_code",
            "SELECT 1 FROM HIB_MDM.ICD10 WHERE DiagnosisCodeId = ? AND IsActive > 0",
            [code])

    def is_twin_icd10_code(self, code: str) -> bool:
        return code in _TWIN_ICD10_CODES

    def is_twin_icd9_code(self, code: str) -> bool:
        return code in _TWIN_ICD9_CODES

    # ── 5. LOINC ──────────────────────────────────────────────────────────────

    def is_loinc_code(self, code: str) -> bool:
        """Existence check only — used by Claim.Submission Rule 45."""
        return self._exists("loinc_code",
            "SELECT 1 FROM HIB_MDM.LOINC WHERE LoincNum = ?",
            [code])

    def is_active_loinc_code(self, code: str) -> bool:
        """Existence + active status — used by Prior.Request Rule 45."""
        return self._exists("loinc_code_active",
            "SELECT 1 FROM HIB_MDM.LOINC WHERE LoincNum = ? AND IsActive > 0",
            [code])

    # ── 6. Other registries ───────────────────────────────────────────────────

    def is_valid_benefit_package(self, package_name: str) -> bool:
        return self._exists("benefit_package",
            "SELECT 1 FROM HIB_MDM.BenefitPackages WHERE PackageName = ?",
            [package_name])

    def is_valid_denial_code(self, code: str) -> bool:
        return self._exists("denial_code",
            "SELECT 1 FROM HIB_MDM.DenialReasons WHERE DenialCode = ?",
            [code])

    def is_valid_nationality(self, nationality: str) -> bool:
        return self._exists("nationality",
            "SELECT 1 FROM HIB_MDM.NationalitiesList WHERE NationalityCode = ?",
            [nationality])

    def is_ipc_provider(self, license_id: str) -> bool:
        return self._exists("ipc_provider",
            "SELECT 1 FROM HIB_MDM.IpcProviders WHERE LicenseId = ?",
            [license_id])

    # ── 7. Exclusion lists ────────────────────────────────────────────────────

    def in_exclusion_list_1(self, sender_id: str) -> bool:
        # Senders exempt from tariff code validation (Rules 31, 65-69)
        return self._exists("exclusion_1",
            "SELECT 1 FROM HIB_MDM.ExclusionList WHERE ListID = 1 AND Code = ?",
            [sender_id])

    def in_exclusion_list_2(self, sender_id: str) -> bool:
        # Senders exempt from TransferSource/TransferDestination checks (Rules 42, 43)
        return self._exists("exclusion_2",
            "SELECT 1 FROM HIB_MDM.ExclusionList WHERE ListID = 2 AND Code = ?",
            [sender_id])

    def in_exclusion_list_4(self, sender_id: str) -> bool:
        # Senders exempt from tariff checks in Prior.Authorization / Prior.Request
        return self._exists("exclusion_4",
            "SELECT 1 FROM HIB_MDM.ExclusionList WHERE ListID = 4 AND Code = ?",
            [sender_id])

    def in_exclusion_list_6(self, sender_id: str) -> bool:
        # Additional exclusions for Prior.Request activity checks (Rule 69)
        return self._exists("exclusion_6",
            "SELECT 1 FROM HIB_MDM.ExclusionList WHERE ListID = 6 AND Code = ?",
            [sender_id])

    def in_exclusion_list_7(self, sender_id: str) -> bool:
        return self._exists("exclusion_7",
            "SELECT 1 FROM HIB_MDM.ExclusionList WHERE ListID = 7 AND Code = ?",
            [sender_id])

    def in_exclusion_list_8(self, sender_id: str) -> bool:
        return self._exists("exclusion_8",
            "SELECT 1 FROM HIB_MDM.ExclusionList WHERE ListID = 8 AND Code = ?",
            [sender_id])

    def in_exclusion_list_9(self, sender_id: str) -> bool:
        return self._exists("exclusion_9",
            "SELECT 1 FROM HIB_MDM.ExclusionList WHERE ListID = 9 AND Code = ?",
            [sender_id])

    # ── 8. Extended payer registry ────────────────────────────────────────────

    def is_active_insurer_or_other(self, license_id: str) -> bool:
        """Insurance or Other classification — used by Rule 15."""
        return self._exists("active_insurer_or_other",
            "SELECT 1 FROM HIB_MDM.InsurancePayers WHERE Classification IN ('Insurance', 'Other') AND IsActive > 0 AND AuthNumber = ?",
            [license_id])

    # ── 9. Date-aware tariff code checks ──────────────────────────────────────

    def is_cpt_code_valid_on_date(self, code: str, activity_start: datetime) -> bool:
        row = self._row("tariff_cpt", 'SELECT EffectiveDate, ExpiryDate FROM HIB_MDM.MandatoryTariff WHERE "Type" = \'CPT\' AND Code = ?', [code])
        return self._is_tariff_row_valid_on_date(row, activity_start)

    def is_hcpcs_code_valid_on_date(self, code: str, activity_start: datetime) -> bool:
        row = self._row("tariff_hcpcs", 'SELECT EffectiveDate, ExpiryDate FROM HIB_MDM.MandatoryTariff WHERE "Type" = \'HCPCS\' AND Code = ?', [code])
        return self._is_tariff_row_valid_on_date(row, activity_start)

    def is_dental_code_valid_on_date(self, code: str, activity_start: datetime) -> bool:
        row = self._row("tariff_uscls", 'SELECT EffectiveDate, ExpiryDate FROM HIB_MDM.MandatoryTariff WHERE "Type" = \'USCLS\' AND Code = ?', [code])
        return self._is_tariff_row_valid_on_date(row, activity_start)

    def is_service_code_valid_on_date(self, code: str, activity_start: datetime) -> bool:
        row = self._row("tariff_svc", 'SELECT EffectiveDate, ExpiryDate FROM HIB_MDM.MandatoryTariff WHERE "Type" = \'Service\' AND Code = ?', [code])
        return self._is_tariff_row_valid_on_date(row, activity_start)

    def is_drg_code_valid_on_date(self, code: str, activity_start: datetime) -> bool:
        row = self._row("tariff_drg", 'SELECT EffectiveDate, ExpiryDate FROM HIB_MDM.MandatoryTariff WHERE "Type" = \'DRG\' AND Code = ?', [code])
        return self._is_tariff_row_valid_on_date(row, activity_start)

    def is_trade_drug_valid_on_date(self, code: str, activity_start: datetime) -> bool:
        row = self._row("drug_trade_date", "SELECT DeleteEffectiveDate FROM HIB_MDM.Drugs WHERE DrugCode = ?", [code])
        if row is None:
            return False
        del_date = _parse_db_date(row.get("DeleteEffectiveDate"))
        if del_date is not None and activity_start >= del_date:
            return False
        return True

    def is_dental_tariff_tooth_required(self, code: str) -> bool:
        """True if the USCLS tariff entry requires a Universal Dental observation."""
        return self._exists("dental_tooth_required",
            "SELECT 1 FROM HIB_MDM.MandatoryTariff WHERE \"Type\" = 'USCLS' AND Code = ? AND ToothNumberRequired = 'yes'",
            [code])

    def is_valid_tooth_code(self, code: str) -> bool:
        return self._exists("tooth_code",
            "SELECT 1 FROM HIB_MDM.UNI_TOOTH_NUMBERING WHERE ToothCode = ?",
            [code])

    def is_icd10_code_valid_on_date(self, code: str, encounter_start: datetime) -> bool:
        row = self._row("icd10_date",
            "SELECT EffectiveDate, ExpiryDate FROM HIB_MDM.ICD10 WHERE DiagnosisCodeId = ?",
            [code])
        if row is None:
            return False
        eff = _parse_db_date(row.get("EffectiveDate"))
        if eff is None:
            return False
        if encounter_start < eff:
            return False
        exp = _parse_db_date(row.get("ExpiryDate"))
        if exp is not None and encounter_start >= exp:
            return False
        return True

    # ── 10. Clinician extended checks ─────────────────────────────────────────

    def is_clinician_pharmacist(self, clinician_id: str) -> bool:
        return self._exists("clinician_pharmacist",
            "SELECT 1 FROM HIB_MDM.ClinicianLicenses WHERE ClinicianLicense = ? AND (LOWER(Profession) LIKE 'pharma%' OR LOWER(Major) LIKE 'pharma%' OR LOWER(Category) LIKE 'pharma%')",
            [clinician_id])

    def is_clinician_invalid_hpl_on_date(self, clinician_id: str, activity_start: datetime) -> bool:
        """True if clinician has an HPL invalid/inactive record covering activity_start."""
        rows = self._db.execute_query(
            "SELECT STATUS_FLAG, EFFECTIVE_DATE, END_DATE FROM HAAD_SH_CLINICIAN_TRACKING WHERE CLINICIAN_LICENSE = ? AND DATASOURCE = 'HPL' AND STATUS_FLAG LIKE '%0%' AND EFFECTIVE_DATE <= ? AND (END_DATE IS NULL OR ? <= END_DATE)",
            [clinician_id, activity_start, activity_start])
        return len(rows) > 0

    def is_clinician_excluded_hsf_on_date(self, clinician_id: str, activity_start: datetime) -> bool:
        """True if clinician is on the HSF insurance exclusion list on activity_start."""
        rows = self._db.execute_query(
            "SELECT 1 FROM HAAD_SH_CLINICIAN_TRACKING WHERE CLINICIAN_LICENSE = ? AND DATASOURCE = 'HSF' AND STATUS_FLAG = '0' AND EFFECTIVE_DATE <= ? AND (END_DATE IS NULL OR ? <= END_DATE)",
            [clinician_id, activity_start, activity_start])
        return len(rows) > 0

    # ── 11. Member / benefit package extended checks ──────────────────────────

    def is_member_registered_for_payer(self, member_id: str, payer_id: str) -> bool:
        return self._exists("member_payer",
            "SELECT 1 FROM HAAD_SH_PERSON_REGISTER WHERE MEMBER_ID = ? AND SENDER_ID = ?",
            [member_id, payer_id])

    def is_valid_benefit_package_for_payer(self, package_name: str, payer_id: str) -> bool:
        return self._exists("benefit_pkg_payer",
            "SELECT 1 FROM HIB_MDM.BenefitPackages WHERE PackageName = ? AND PayerID = ? AND IsActive > 0",
            [package_name, payer_id])

    # ── 12. Shadow / PTE provider and payer lists ─────────────────────────────

    def is_shadow_provider(self, license_id: str) -> bool:
        return self._exists("shadow_provider",
            "SELECT 1 FROM HIB_MDM.ShadowProviders WHERE LicenseId = ? AND IsActive > 0",
            [license_id])

    def is_shadow_insurer(self, license_id: str) -> bool:
        return self._exists("shadow_insurer",
            "SELECT 1 FROM HIB_MDM.ShadowInsurers WHERE LicenseId = ? AND IsActive > 0",
            [license_id])

    # ── 13. DRG pilot / CAHMS lists ───────────────────────────────────────────

    def is_orthopedic_drg_provider(self, facility_id: str) -> bool:
        return self._exists("ortho_drg_provider",
            "SELECT 1 FROM HIB_MDM.OrthopedicDRGProviders WHERE FacilityId = ? AND IsActive > 0",
            [facility_id])

    def is_included_drg_activity_code(self, code: str) -> bool:
        return self._exists("drg_included",
            "SELECT 1 FROM HIB_MDM.IncludedDRGActivityCodes WHERE Code = ? AND IsActive > 0",
            [code])

    def is_excluded_drg_activity_code(self, code: str) -> bool:
        return self._exists("drg_excluded",
            "SELECT 1 FROM HIB_MDM.ExcludedDRGActivityCodes WHERE Code = ? AND IsActive > 0",
            [code])

    def is_drg_cahms_code(self, code: str) -> bool:
        return self._exists("drg_cahms",
            "SELECT 1 FROM HIB_MDM.DRG_CAHMS WHERE Code = ?",
            [code])

    # ── 14. Under-supply code list ────────────────────────────────────────────

    def is_undersupply_code(self, code: str) -> bool:
        return self._exists("undersupply",
            "SELECT 1 FROM HAAD_SH_UNDERSUPPLY WHERE UPPER(TRIM(CODE)) = UPPER(TRIM(?)) AND IS_ACTIVE > 0",
            [code])

    # ── 15. Year of Onset required list ──────────────────────────────────────

    def is_yearofonset_required(self, diag_code: str) -> bool:
        return self._exists("yearofonset_req",
            "SELECT 1 FROM HAAD_SH_YEAROFONSET_NEW WHERE UPPER(CODE) = UPPER(?) AND IS_ACTIVE > 0",
            [diag_code])

    # ── 16. Historical / transactional data lookups ───────────────────────────

    def has_remittance_for_claim(self, receiver_id: str, claim_id: str, id_payer: str) -> bool:
        return self._exists("remittance_claim",
            "SELECT 1 FROM HAAD_SH_CLAIM WHERE CLAIM_ID = ? AND ID_PAYER = ? AND SENDER_ID = ? AND ADV_TRANS_ID IS NOT NULL",
            [claim_id, id_payer, receiver_id])

    def has_submitted_claim(self, sender_id: str, claim_id: str) -> bool:
        """True if this claim was already submitted (Rule 118 — duplicate submission)."""
        return self._exists("submitted_claim",
            "SELECT 1 FROM HAAD_SH_CLAIM WHERE SENDER_ID = ? AND CLAIM_ID = ?",
            [sender_id, claim_id])

    def get_previous_claim_fields(self, sender_id: str, claim_id: str) -> "dict | None":
        """Return fields of a previous submission for resubmission consistency checks."""
        return self._row("prev_claim",
            "SELECT MEMBER_ID, PAYER_ID, PROVIDER_ID, EMIRATES_ID, PACKAGE_NAME FROM HAAD_SH_CLAIM WHERE SENDER_ID = ? AND CLAIM_ID = ? ORDER BY CREATED_ON DESC",
            [sender_id, claim_id])

    def find_duplicate_claim_id(self, provider_id: str, member_id: str, payer_id: str,
                                 receiver_id: str, act_start: datetime, act_type: int,
                                 act_code: str, act_qty: float, act_ordering: str) -> "str | None":
        """Return existing Claim.ID if a matching duplicate activity exists (Rule 233)."""
        rows = self._db.execute_query(
            "SELECT CLAIM_ID FROM HAAD_SH_CLAIM_ACTIVITY WHERE PROVIDER_ID = ? AND MEMBER_ID = ? AND PAYER_ID = ? AND RECEIVER_ID = ? AND ACT_START = ? AND ACT_TYPE = ? AND ACT_CODE = ? AND ACT_QTY = ? AND ORDERING_CLINICIAN = ? FETCH FIRST 1 ROWS ONLY",
            [provider_id, member_id, payer_id, receiver_id, act_start, act_type, act_code, act_qty, act_ordering])
        return rows[0]["CLAIM_ID"] if rows else None

    # ── 17. Denial-code date-aware check ─────────────────────────────────────

    def get_denial_code_row(self, code: str) -> "dict | None":
        return self._row("denial_code_row",
            "SELECT EffectiveDate, ExpiryDate FROM HIB_MDM.DenialReasons WHERE DenialCode = ?",
            [code])

    def is_denial_code_valid_on_date(self, code: str, tx_date: datetime) -> bool:
        """True if the denial code exists AND is in-effect on tx_date."""
        row = self.get_denial_code_row(code)
        if row is None:
            return False
        eff = _parse_db_date(row.get("EffectiveDate"))
        if eff is None:
            return False
        if tx_date < eff:
            return False
        exp = _parse_db_date(row.get("ExpiryDate"))
        if exp is not None and tx_date >= exp:
            return False
        return True

    # ── 18. Prior.Authorization / Prior.Request cross-lookups ─────────────────

    def get_prior_request_type(self, auth_id: str, sender_id: str) -> "str | None":
        """Return Auth.Type of the most recent Prior.Request for this auth_id (PA sender = PR receiver)."""
        row = self._row("pr_type",
            "SELECT AUTH_TYPE FROM HAAD_SH_PRIOR_REQUEST WHERE AUTHORIZATION_ID = ? AND RECEIVER_ID = ? ORDER BY CREATED_ON DESC",
            [auth_id, sender_id])
        return row.get("AUTH_TYPE") if row else None

    def prior_request_has_response(self, auth_id: str, sender_id: str) -> bool:
        """True if the Prior.Request already has an associated PA (AUTH_TRANS_ID not null)."""
        return self._exists("pr_has_response",
            "SELECT 1 FROM HAAD_SH_PRIOR_REQUEST WHERE AUTHORIZATION_ID = ? AND RECEIVER_ID = ? AND AUTH_TRANS_ID IS NOT NULL",
            [auth_id, sender_id])

    def get_pr_min_activity_start(self, auth_id: str, sender_id: str) -> "datetime | None":
        """Return minimum Activity.Start from the corresponding Prior.Request (for PA Rule 178)."""
        rows = self._db.execute_query(
            "SELECT MIN(ACTIVITY_START) AS min_start FROM HAAD_SH_PRIOR_REQUEST_ACTIVITY WHERE AUTHORIZATION_ID = ? AND RECEIVER_ID = ?",
            [auth_id, sender_id])
        if not rows:
            return None
        return _parse_db_date(rows[0].get("min_start"))

    def prior_auth_exists_for_id(self, auth_id: str, receiver_id: str) -> bool:
        """True if a PA exists where Authorization.ID=auth_id and PA.ReceiverID=receiver_id."""
        return self._exists("pa_exists_for_id",
            "SELECT 1 FROM HAAD_SH_PRIOR_AUTH WHERE AUTHORIZATION_ID = ? AND RECEIVER_ID = ?",
            [auth_id, receiver_id])

    def prior_auth_all_requests_responded(self, auth_id: str, sender_id: str) -> bool:
        """Rule 242: True if ALL matching PRs for this auth_id already have a PA."""
        rows = self._db.execute_query(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN AUTH_TRANS_ID IS NOT NULL THEN 1 ELSE 0 END) AS responded"
            " FROM HAAD_SH_PRIOR_REQUEST WHERE AUTHORIZATION_ID = ? AND RECEIVER_ID = ?",
            [auth_id, sender_id])
        if not rows:
            return False
        total    = rows[0].get("total", 0) or 0
        responded = rows[0].get("responded", 0) or 0
        return total > 0 and int(total) == int(responded)

    def prior_auth_exists_for_request(self, auth_id: str, id_payer: str,
                                       receiver_id: str, cutoff: datetime) -> bool:
        """PR Rule 175: check if a PA was issued for this authorization within 6 months."""
        return self._exists("pa_for_pr",
            "SELECT 1 FROM HAAD_SH_PRIOR_AUTH WHERE AUTHORIZATION_ID = ? AND ID_PAYER = ? AND SENDER_ID = ? AND CREATED_ON >= ?",
            [auth_id, id_payer, receiver_id, cutoff])

    def get_pr_historical_activity_ids(self, auth_id: str, sender_id: str) -> "set | None":
        """PR Rule 201: Return set of activity IDs from the historical Prior.Request."""
        rows = self._db.execute_query(
            "SELECT ACTIVITY_ID FROM HAAD_SH_PRIOR_REQUEST_ACTIVITY WHERE AUTHORIZATION_ID = ? AND SENDER_ID = ?",
            [auth_id, sender_id])
        if not rows:
            return None
        return {r.get("ACTIVITY_ID") for r in rows}

    def is_pr_authorization_id_unique(self, auth_id: str, sender_id: str) -> bool:
        """PR Rule 213: True if auth_id doesn't already exist for this sender."""
        return not self._exists("pr_auth_id_dup",
            "SELECT 1 FROM HAAD_SH_PRIOR_REQUEST WHERE AUTHORIZATION_ID = ? AND SENDER_ID = ?",
            [auth_id, sender_id])

    # ── 19. Person.Register history lookups ──────────────────────────────────

    def has_person_register_member(self, member_id: str, sender_id: str) -> bool:
        """PR Rule 329, 336: check if member already has a record under this sender."""
        return self._exists("pr_member_exists",
            "SELECT 1 FROM HAAD_SH_PERSON_REGISTER_DETAIL WHERE MEMBER_ID = ? AND SENDER_ID = ?"
            " AND (CONTRACT_STATUS != 'Gap Enrollment' OR CONTRACT_STATUS IS NULL)",
            [member_id, sender_id])

    def get_latest_person_register_contract(self, member_id: str, sender_id: str) -> "dict | None":
        """PR Rules 332, 333, 334, 353: latest non-GapEnrollment contract row."""
        return self._row("pr_latest_contract",
            "SELECT CONTRACT_STATUS, START_DATE, RENEWAL_DATE, EXPIRY_DATE"
            " FROM HAAD_SH_PERSON_REGISTER_DETAIL WHERE MEMBER_ID = ? AND SENDER_ID = ?"
            " AND (CONTRACT_STATUS != 'Gap Enrollment' OR CONTRACT_STATUS IS NULL)"
            " ORDER BY CREATED_ON DESC",
            [member_id, sender_id])

    def is_principal_relation_known(self, relation_to: str, sender_id: str) -> bool:
        """PR Rule 136: check if relation_to member ID exists as a principal under sender."""
        return self._exists("pr_principal",
            "SELECT 1 FROM HAAD_SH_PERSON_REGISTER_DETAIL WHERE MEMBER_ID = ? AND SENDER_ID = ?",
            [relation_to, sender_id])

    def is_valid_nationality_description(self, description: str) -> bool:
        """PR Rule 284: validate CountryOfResidence against the Description column."""
        return self._exists("nat_desc",
            "SELECT 1 FROM HIB_MDM.NationalitiesList WHERE Description = ?",
            [description])

    def get_moi_record(self, unified_number: str) -> "dict | None":
        """MOI web service lookup — returns None (stub) until real integration is added."""
        return None

    # ── 20. Remittance.Advice transactional lookups ───────────────────────────

    def get_submitted_claim_for_ra(self, claim_id: str, provider_id: str,
                                    sender_id: str) -> "dict | None":
        """RA Rules 117, 133: return latest CS claim matching (claim_id, provider=provider_id)."""
        return self._row("ra_cs_claim",
            "SELECT CLAIM_ID, ID_PAYER, NET, CREATED_ON, ADV_TRANS_ID, ADV_DENIAL_CODE"
            " FROM HAAD_SH_CLAIM WHERE CLAIM_ID = ? AND SENDER_ID = ? AND RECEIVER_ID = ?"
            " ORDER BY CREATED_ON DESC",
            [claim_id, provider_id, sender_id])

    def ra_claim_activity_match_exists(self, claim_id: str, provider_id: str,
                                        activity_id: str, act_type: int,
                                        net: float, qty: float,
                                        clinician: "str | None",
                                        ordering: "str | None") -> bool:
        """RA Rule 111: check for a matching CS activity."""
        rows = self._db.execute_query(
            "SELECT 1 FROM HAAD_SH_CLAIM_ACTIVITY"
            " WHERE CLAIM_ID = ? AND PROVIDER_ID = ? AND ACTIVITY_ID = ? AND ACT_TYPE = ?"
            " AND ROUND(ACT_NET) = ROUND(?) AND ROUND(ACT_QTY) = ROUND(?)"
            " AND (CLINICIAN IS NULL AND ? IS NULL OR TRIM(CLINICIAN) = TRIM(?))"
            " AND (ORDERING_CLINICIAN IS NULL AND ? IS NULL OR TRIM(ORDERING_CLINICIAN) = TRIM(?))"
            " FETCH FIRST 1 ROWS ONLY",
            [claim_id, provider_id, activity_id, act_type, net, qty,
             clinician, clinician, ordering, ordering])
        return len(rows) > 0

    def get_ra_takeback_data(self, claim_id: str, provider_id: str,
                              activity_id: str) -> "dict | None":
        """RA Rule 235: get takeback count and resubmission info for an activity."""
        return self._row("ra_takeback",
            "SELECT TAKEBACK_COUNT, RESUBMISSION_TYPE, ADV_TRANS_ID"
            " FROM HAAD_SH_CLAIM_ACTIVITY WHERE CLAIM_ID = ? AND PROVIDER_ID = ? AND ACTIVITY_ID = ?"
            " ORDER BY CREATED_ON DESC",
            [claim_id, provider_id, activity_id])

    def is_id_payer_used_by_other_claim(self, id_payer: str, receiver_id: str,
                                         claim_id: str) -> bool:
        """RA Rule 137: IDPayer must be unique per payer context."""
        return self._exists("id_payer_other",
            "SELECT 1 FROM HAAD_SH_CLAIM WHERE ID_PAYER = ? AND RECEIVER_ID = ? AND CLAIM_ID != ?",
            [id_payer, receiver_id, claim_id])

    def get_submitted_claim_created_on(self, claim_id: str, provider_id: str,
                                        sender_id: str) -> "datetime | None":
        """RA Rule 311: return CreatedOn of the latest matching CS claim."""
        row = self._row("ra_cs_created_on",
            "SELECT CREATED_ON FROM HAAD_SH_CLAIM WHERE CLAIM_ID = ? AND SENDER_ID = ? AND RECEIVER_ID = ?"
            " ORDER BY CREATED_ON DESC",
            [claim_id, provider_id, sender_id])
        return _parse_db_date(row.get("CREATED_ON")) if row else None

    def get_submitted_claim_id_payer(self, claim_id: str, provider_id: str,
                                      sender_id: str, after: datetime) -> "str | None":
        """RA Rule 312: return IDPayer of the latest CS claim submitted after a cutoff date."""
        rows = self._db.execute_query(
            "SELECT ID_PAYER FROM HAAD_SH_CLAIM WHERE CLAIM_ID = ? AND SENDER_ID = ? AND RECEIVER_ID = ?"
            " AND CREATED_ON > ? ORDER BY CREATED_ON DESC",
            [claim_id, provider_id, sender_id, after])
        return rows[0].get("ID_PAYER") if rows else None

    # ── 21. UPP drug pricing lookups ─────────────────────────────────────────────

    def get_pkg_markup(self, drug_code: str) -> "str | None":
        """UPP drug package markup price (Rules 377, 379, 380)."""
        row = self._row("pkg_markup",
            "SELECT PKG_MARKUP FROM HIB_MDM.Drugs WHERE DrugCode = ? AND DeleteEffectiveDate IS NULL",
            [drug_code])
        if row and row.get("PKG_MARKUP") is not None:
            return str(row["PKG_MARKUP"]).strip()
        return None

    def get_pkg_price_to_public(self, drug_code: str) -> "str | None":
        """UPP drug package price-to-public (Rule 380)."""
        row = self._row("pkg_price_pub",
            "SELECT PKG_PRICE_TO_PUBLIC FROM HIB_MDM.Drugs WHERE DrugCode = ? AND DeleteEffectiveDate IS NULL",
            [drug_code])
        if row and row.get("PKG_PRICE_TO_PUBLIC") is not None:
            return str(row["PKG_PRICE_TO_PUBLIC"]).strip()
        return None

    # ── 22. Consultation / DateOrdered cross-claim lookups ────────────────────────

    def claim_has_consultation_with_date_ordered(self, member_id: str, sender_id: str) -> bool:
        """Rule 289: True if a previous claim for this member/sender has a consultation activity with DateOrdered + OrderingClinician."""
        return self._exists("consult_date_ordered",
            "SELECT 1 FROM HAAD_SH_CLAIM_ACTIVITY ca"
            " JOIN HAAD_SH_CLAIM c ON c.CLAIM_ID = ca.CLAIM_ID AND c.SENDER_ID = ca.PROVIDER_ID"
            " WHERE c.MEMBER_ID = ? AND c.SENDER_ID = ?"
            " AND ca.ACT_DATE_ORDERED IS NOT NULL AND ca.ORDERING_CLINICIAN IS NOT NULL"
            " AND EXISTS ("
            "   SELECT 1 FROM HIB_MDM.MandatoryTariff mt"
            "   WHERE mt.CODE = ca.ACT_CODE AND mt.CODE_TYPE = 'Consultation')",
            [member_id, sender_id])

    # ── 23. Person.Register EID / Unified Number existence ───────────────────────

    def person_register_eid_exists(self, emirates_id_number: str) -> bool:
        """Rule 350: True if a Person.Register record with this EmiratesIDNumber exists."""
        return self._exists("pr_eid_exists",
            "SELECT 1 FROM HAAD_SH_PERSON_REGISTER WHERE EMIRATES_ID_NUMBER = ?",
            [emirates_id_number])

    def person_register_unified_number_exists(self, unified_number: str) -> bool:
        """Rule 351: True if a Person.Register record with this UnifiedNumber exists."""
        return self._exists("pr_uid_exists",
            "SELECT 1 FROM HAAD_SH_PERSON_REGISTER WHERE UNIFIED_NUMBER = ?",
            [unified_number])

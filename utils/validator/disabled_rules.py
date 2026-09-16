"""
Rules disabled pending verification/fixes to transactional queries in resource_provider.py.

These rules involve lookups against historical transaction tables (HAAD_SH_*) or
external services (MOI).  They are skipped entirely during validation — no result
is produced for them (contrast with is_active=False rules, which still run and
return a ValidationResult so callers know the rule exists but is inactive).

HOW TO RE-ENABLE A RULE
  1. Verify / fix the corresponding method(s) in resource_provider.py.
  2. Remove the rule ID string from the set below.
  3. Done — the validator picks it up automatically on the next run.

Keys are the TRANSACTION string from each validator class.
Values are frozensets of rule ID strings (matching the method suffix, e.g. "_rule_292_1" → "292_1").
"""

DISABLED_RULES: dict[str, frozenset] = {

    # ── Claim.Submission ──────────────────────────────────────────────────────
    # Waiting on: has_remittance_for_claim, has_submitted_claim,
    #             get_previous_claim_fields (missing activity_ids column),
    #             find_duplicate_claim_id, claim_has_consultation_with_date_ordered,
    #             person_register_eid_exists, get_pkg_markup, get_pkg_price_to_public
    "Claim.Submission": frozenset({
        "112",    # has_remittance_for_claim
        "118",    # has_submitted_claim
        "197",    # get_previous_claim_fields
        "233",    # find_duplicate_claim_id
        "289",    # claim_has_consultation_with_date_ordered
        "292_1",  # get_previous_claim_fields
        "292_2",  # get_previous_claim_fields
        "292_3",  # get_previous_claim_fields
        "292_4",  # get_previous_claim_fields
        "292_5",  # get_previous_claim_fields
        "292_6",  # get_previous_claim_fields
        "341",    # person_register_eid_exists
        "377",    # get_pkg_markup
        "380",    # get_pkg_markup + get_pkg_price_to_public
    }),

    # ── Person.Register ───────────────────────────────────────────────────────
    # Waiting on: is_principal_relation_known, get_moi_record (stub — MOI not integrated),
    #             is_valid_nationality_description, has_person_register_member,
    #             get_latest_person_register_contract, person_register_eid_exists,
    #             person_register_unified_number_exists
    "Person.Register": frozenset({
        "136",    # is_principal_relation_known
        "272",    # get_moi_record (stub)
        "277",    # get_moi_record (stub) — via _moi_name_check
        "278",    # get_moi_record (stub)
        "279",    # get_moi_record (stub)
        "280",    # get_moi_record (stub)
        "284",    # is_valid_nationality_description
        "286",    # get_moi_record (stub)
        "329",    # has_person_register_member
        "332",    # get_latest_person_register_contract
        "333",    # get_latest_person_register_contract
        "334",    # get_latest_person_register_contract
        "336",    # has_person_register_member
        "350",    # person_register_eid_exists
        "351",    # person_register_unified_number_exists
        "353",    # get_latest_person_register_contract
        "400",    # get_moi_record (stub)
    }),

    # ── Prior.Authorization ───────────────────────────────────────────────────
    # Waiting on: get_prior_request_type, is_pr_authorization_id_unique,
    #             is_id_payer_used_by_other_claim (verify correct table),
    #             prior_request_has_response, get_pr_min_activity_start,
    #             get_pr_historical_activity_ids, prior_auth_exists_for_id,
    #             get_pkg_markup, get_pkg_price_to_public
    "Prior.Authorization": frozenset({
        "159",    # get_prior_request_type
        "160",    # get_prior_request_type
        "161",    # is_pr_authorization_id_unique
        "164",    # get_prior_request_type
        "166",    # is_id_payer_used_by_other_claim (verify: HAAD_SH_CLAIM vs HAAD_SH_PRIOR_AUTH)
        "181",    # prior_request_has_response
        "236",    # get_pr_min_activity_start
        "237",    # get_pkg_markup
        "257",    # get_prior_request_type
        "258",    # get_prior_request_type + get_pr_historical_activity_ids
        "259",    # prior_auth_exists_for_id + is_pr_authorization_id_unique
        "264",    # get_prior_request_type
        "266",    # get_prior_request_type
        "267",    # get_prior_request_type
        "268",    # get_prior_request_type
        "269",    # get_prior_request_type
        "270",    # get_prior_request_type
        "379",    # get_pkg_markup + get_pkg_price_to_public
    }),

    # ── Prior.Request ─────────────────────────────────────────────────────────
    # Waiting on: is_pr_authorization_id_unique, prior_request_has_response,
    #             prior_auth_exists_for_id, prior_auth_all_requests_responded,
    #             prior_auth_exists_for_request (fix cutoff=None in rule 213),
    #             get_pkg_markup, get_pkg_price_to_public
    "Prior.Request": frozenset({
        "161",    # is_pr_authorization_id_unique
        "175",    # prior_request_has_response
        "176",    # prior_auth_exists_for_id
        "177",    # prior_auth_exists_for_id
        "181",    # is_pr_authorization_id_unique
        "213",    # prior_auth_exists_for_request — cutoff=None makes query always false
        "258",    # prior_auth_exists_for_id
        "259",    # prior_auth_all_requests_responded
        "345",    # prior_auth_exists_for_request
        "377",    # get_pkg_markup
        "380",    # get_pkg_markup + get_pkg_price_to_public
    }),

    # ── Remittance.Advice ─────────────────────────────────────────────────────
    # Waiting on: get_submitted_claim_for_ra, ra_claim_activity_match_exists,
    #             get_ra_takeback_data (fix activity_id=None),
    #             get_submitted_claim_created_on, get_submitted_claim_id_payer,
    #             is_id_payer_used_by_other_claim, get_pkg_markup, get_pkg_price_to_public
    "Remittance.Advice": frozenset({
        "98",     # get_submitted_claim_for_ra
        "106",    # get_submitted_claim_for_ra + ra_claim_activity_match_exists
        "196",    # get_ra_takeback_data — activity_id=None makes query always false
        "232",    # get_submitted_claim_for_ra + get_submitted_claim_created_on + get_submitted_claim_id_payer
        "235",    # is_id_payer_used_by_other_claim
        "379",    # get_pkg_markup + get_pkg_price_to_public
    }),
}

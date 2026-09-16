# Request Mapper Transaction Flows

This document describes the request/response flow implemented by each `AbstractRequestMapper` subclass in
`utils/request_mapper/request_mapper.py`. It is meant as a reference for understanding what prerequisite
(pre-condition) requests are sent before the "request under test," and how live data flows through the chain.

## How to read this document

Each transaction class implements `do_request(system, live_data=None)`. Two execution modes exist, controlled by the
`SOAP_EXECUTION_SEQUENCE` environment variable (`_should_use_single_request()`):

- **Full scenario** (`SOAP_EXECUTION_SEQUENCE == "full_scenario"`): `do_request` builds and sends every prerequisite
  step in the chain (person register, prior request, prior authorization, claim submission, remittance advice, etc.)
  before building and sending the final "request under test." If the templates were already built in a previous call
  (`self.xxx_template is not None`), it re-sends the cached prerequisite templates instead of rebuilding them (the
  `else` branch), which lets the same object be reused across a scenario without re-generating requests.
- **Single/isolated request** (any other value, the default): `_do_single_request` skips all prerequisite steps and
  sends only a self-contained "isolated" template for the request under test (e.g. `claim_checker_isolated`), which
  already embeds the data it needs without requiring the live upstream chain.

**Live data wiring**: `live_data` is the dynamic substitution data supplied by the caller for the request under test.
Some classes (the `ClaimChecker` family) additionally support per-step live data via
`extract_step_live_data(prerequisites, prefix)`, which parses `'{StepPrefix}.path=value'` entries out of the
semicolon-delimited `Precondition` string using `RequestPrefix` enum values (`PersonRegister`, `PriorRequest`,
`PriorAuthorization`, `ClaimSubmission`, `RemittanceAdvice`). This lets a single Precondition column drive dynamic
values into a specific step of a multi-step chain, not just the final request under test. Classes outside the
`ClaimChecker` family do not use this mechanism — their prerequisite steps are always sent with `live_data=None`.
For a bare (1st-occurrence) prefix, `StepPrefix[1].path=value` is also accepted as an alias for
`StepPrefix.path=value`.

`extract_step_live_data` returns a `(step_live_data, remaining_prerequisites)` tuple: `remaining_prerequisites` is
the input string with this step's entries stripped out, and is threaded as the `prerequisites` argument into the
*next* `extract_step_live_data` call in the chain. Each `ClaimChecker`-family class chains all of its steps this
way and, after the last extraction, checks whatever is still left in `remaining`: if non-empty, it means the
`Precondition` string had an entry whose prefix matched none of this flow's known steps (e.g. a `ClaimSubmission.`
entry inside a `ClaimChecker` flow, which has no claim submission step), and the class raises
`Exception(f"Unconsumed precondition entries (no matching step in this flow): {remaining}")` immediately, instead of
silently dropping the entry. This only happens on the "build a fresh chain" path (when the relevant
`self.xxx_template` attributes are still `None`) — not on the cached resend path.

**`variables`**: a dict of values threaded through the chain via `get_template_request(..., variables=...)`, letting
later steps reference identifiers produced by earlier steps (e.g. a member/person ID from Person Register feeding
into Prior Request).

Each flow below lists prerequisite steps in order, then the final request under test.

---

## Core building blocks

### PersonRegister
- **Chain**: Person Register (request under test).
- No prerequisites; both full-scenario and single-request modes just send `person_register`.

### PersonRegisterResubmission
- **Chain**: Person Register → Person Register Resubmission (request under test).
- Full scenario builds and sends a plain `person_register` first (live_data always `None`), then builds
  `person_register_resubmission` with the caller's `live_data`.

### PersonRegisterTPA
- **Chain**: Person Register TPA (request under test).
- No prerequisites.

### PriorRequest
- **Chain**: Person Register → Prior Request (request under test).
- Isolated mode uses `prior_request_isolated`.

### PriorRequestToTPA
- **Chain**: Person Register (TPA) → Prior Request to TPA (request under test).

### PriorRequestMultipleXmls
- **Chain**: Person Register → Prior Request → sent again wrapped as `SendPriorRequestMultipleXmls` (request under test).

### PriorRequestGreaterThan6MB
- **Chain**: Person Register → Prior Request → Prior Authorization → Prior Request Resubmission (>6MB) (request under test).

### PriorRequestResubmission
- **Chain**: Person Register → Prior Request → Prior Authorization → Prior Request Resubmission (request under test).

### PriorRequestZipped
- **Chain**: Person Register → Prior Request → sent zipped via `SendPriorRequestZipped` (request under test).

### PriorAuthorizationPrescription / PriorAuthorizationCancellation / PriorAuthorizationExtension / PriorAuthorizationEligibility / PriorAuthorizationLarge
- **Chain** (all five follow the same shape): Person Register → Prior Request (variant-specific: prescription /
  cancellation / extension / eligibility / plain) → Prior Authorization (matching variant) (request under test).

### PriorAuthorization
- **Chain**: Person Register → Prior Request → Prior Authorization (request under test).

### PriorAuthorizationTPA
- **Chain**: Person Register TPA → Prior Request to TPA → Prior Authorization TPA (request under test).

### ClaimSubmission
- **Chain**: Person Register → Prior Request → Claim Submission (request under test).

### ClaimChecker
- **Chain**: Person Register → Prior Request → Prior Authorization → Claim Checker (request under test).
- Uses per-step live data extraction: `person_register_live_data`, `prior_request_live_data`,
  `prior_authorization_live_data` are each pulled from `self.prerequisites` via `extract_step_live_data` with
  `RequestPrefix.person_register` / `.prior_request` / `.prior_authorization`, and passed into their respective
  `get_template_request` + `Send*` calls. The final Claim Checker step still uses the top-level `live_data` argument.
- Uses `claim_checker_template.xml`. The Activity's `PriorAuthorizationID` is set to
  `{{VAR.facility_id}}-{{VAR.id_payer}}`, mirroring the `IDPayer` generated by the prior authorization step
  (`prior_authorization_template.xml`), since `id_payer` is generated once in that step and carried forward through
  the shared `variables` dict.
- Isolated mode uses `claim_checker_isolated` → `claim_checker_template_isolated.xml`, whose `PriorAuthorizationID` is
  instead a self-generated `MF3505-{{CUSTOM.generate_numbers_id()}}` (isolated mode never runs a real prior
  authorization step, so there's no `id_payer` variable to reference).

### PersonCorrectedClaimChecker
- **Chain**: Person Register → Person Register Resubmission (2nd, "correction") → Prior Request → Prior Authorization →
  Claim Checker (request under test).
- Structurally identical to `ClaimChecker`, except the person register step is sent twice in a row: a plain
  `person_register` first, then a 2nd registration using the `person_register_resubmission` template
  (`person_register_resubmission_template.xml`) with `variables=variables` carried over from the first call, so the
  2nd registration reuses/corrects the same generated identifiers instead of generating a fresh, unrelated person.
  Cached separately as `self.second_person_register_template` (distinct from `self.person_register_template`) so both
  calls can be re-sent independently in the cached (`else`) branch.
- Uses the same per-step live data extraction pattern as `ClaimChecker` for `person_register` (1st call),
  `prior_request`, and `prior_authorization`. The 2nd person register call is wired via
  `RequestPrefix.person_register.value + "[2]"` (i.e. `PersonRegister[2].path=value` entries in the Precondition
  string), following the same `[2]`-suffix convention used elsewhere (e.g. `ClaimCheckerSecondResubmission`) to
  disambiguate a repeated step of the same type.
- `_do_single_request` explicitly raises `Exception("Please use full scenario for this transaction type")` — this
  transaction cannot run in isolated/single-request mode at all.

### ClaimCheckerNoPriorAuthorization
- **Chain**: Person Register → Prior Request → Claim Checker (no prior authorization step) (request under test).
- Same per-step live data extraction pattern as `ClaimChecker`, minus the prior authorization step (only
  `person_register_live_data` and `prior_request_live_data` are extracted/wired).
- Uses a dedicated `claim_checker_no_prior_authorization_template.xml` (previously reused `claim_checker_template.xml`,
  but that broke once `ClaimChecker`'s `PriorAuthorizationID` started referencing `{{VAR.id_payer}}` — a variable this
  flow never generates since it skips the prior authorization step). `PriorAuthorizationID` is left empty here.
- Isolated mode uses `claim_checker_no_prior_authorization_isolated` → `claim_checker_no_prior_authorization_template_isolated.xml`
  (also with empty `PriorAuthorizationID`).

### ClaimCheckerResubmission
- **Chain**: Person Register → Prior Request → Claim Submission → Remittance Advice → Claim Checker Resubmission (request under test).
- Extracts and wires per-step live data for all four prerequisite steps via `RequestPrefix.person_register`,
  `.prior_request`, `.claim_submission`, `.remittance_advice`.
- Isolated mode uses `claim_checker_resubmission_isolated`.

### ClaimCheckerNoRemittance
- **Chain**: Person Register → Prior Request → Claim Submission → Claim Checker (no remittance advice step) (request under test).
- The "claim checker" counterpart of `SecondClaimNoRemittance`: same chain, but the final request is sent via
  `SendClaimChecker` against `claim_checker_no_remittance_template.xml` instead of `SendClaimSubmission`.
- Joins the `ClaimChecker` family's live-data pattern: extracts/wires `person_register_live_data`,
  `prior_request_live_data`, `claim_submission_live_data` via `RequestPrefix`, and raises on any unconsumed
  precondition entry (e.g. a `RemittanceAdvice.` entry, since this flow has no remittance advice step).
- Since there's no remittance advice step, `claim_checker_no_remittance_template.xml` self-generates
  `IDPayer` via `{{VAR(remittance_id_payer).CUSTOM.generate_numbers_id(T001_Malaffi)}}` instead of referencing
  `{{VAR.remittance_id_payer}}` (which only `ClaimCheckerResubmission`'s remittance advice step produces).
- Isolated mode uses `claim_checker_no_remittance_isolated` → `claim_checker_no_remittance_template_isolated.xml`.

### ClaimCheckerConsultationNoRemittance
- **Chain**: Person Register → Prior Request Consultation → Claim Submission → Claim Checker (no prior authorization, no
  remittance advice step) (request under test).
- The "claim checker" counterpart of `ClaimResubmissionConsultationNoRemittance`: same chain (using
  `prior_request_consultation` for the Prior Request step instead of the plain `prior_request` template), but the
  final request is sent via `SendClaimChecker` instead of `SendClaimSubmission`.
- Reuses `claim_checker_no_remittance_template.xml` / `claim_checker_no_remittance_isolated` unchanged for the final
  step — same as how `ClaimResubmissionConsultationNoRemittance` reuses the plain `claim_resubmission_no_remittance`
  template unchanged; the consultation variant only swaps the Prior Request step, not the final claim template.
- Joins the `ClaimChecker` family's live-data pattern: extracts/wires `person_register_live_data`,
  `prior_request_live_data`, `claim_submission_live_data` via `RequestPrefix` (the generic `prior_request` prefix is
  used even though the underlying template is the consultation variant), and raises on any unconsumed precondition
  entry.

### ClaimCheckerSelfPay
- **Chain**: Person Register (self pay) → Claim Checker (self pay) (request under test). No Prior Request, Prior
  Authorization, or Remittance Advice step — mirrors `ClaimSubmissionSelfPay`'s short chain exactly.
- The "claim checker" counterpart of `ClaimSubmissionSelfPay`: the person register step is sent via
  `SendPersonRegisterProvider` (self-pay registrations use the provider endpoint, same as
  `ClaimSubmissionSelfPay`), and the final request is sent via `SendClaimChecker` against
  `claim_checker_selfpay_template.xml` instead of `SendClaimSubmission` against
  `claim_submission_selfpay_template.xml`.
- `claim_checker_selfpay_template.xml` is an unmodified copy of `claim_submission_selfpay_template.xml` — since the
  self-pay chain has no preceding Prior Request/Prior Authorization/Remittance Advice step either way, there was no
  content for a "claim checker" variant to differ on, so it's a dedicated file kept in lockstep by convention rather
  than by necessity.
- Joins the `ClaimChecker` family's live-data pattern: extracts/wires `person_register_live_data` via
  `RequestPrefix`, and raises on any unconsumed precondition entry (e.g. any `PriorRequest.`/`RemittanceAdvice.`
  entry, since this flow has neither step).
- Isolated mode uses `claim_checker_self_pay_isolated` → `claim_checker_selfpay_template_isolated.xml`, which
  hardcodes `patient_id`/`facility_id`/`clinician_license` (normally sourced from the Person Register/Prior Request
  steps) since isolated mode has no preceding step to generate them.

### ClaimCheckerMultipleClaimsZipped
- **Chain**: Person Register → Prior Request → Prior Authorization → Claim Checker (multiple claims), sent zipped
  via `SendClaimCheckerZipped` (request under test).
- Joins the `ClaimChecker` family (same prerequisite shape as plain `ClaimChecker`), not `ClaimSubmissionMultipleClaimsZipped`
  — uses the same per-step live data extraction pattern: `person_register_live_data`, `prior_request_live_data`,
  `prior_authorization_live_data` are each pulled from `self.prerequisites` via `extract_step_live_data` with
  `RequestPrefix.person_register` / `.prior_request` / `.prior_authorization`, and passed into their respective
  `get_template_request` + `Send*` calls. The final Claim Checker step still uses the top-level `live_data` argument,
  and any unconsumed `Precondition` entry raises `Exception(f"Unconsumed precondition entries (no matching step in
  this flow): {remaining}")`. The cached (`else`) resend path re-sends all three prerequisites, matching `ClaimChecker`.
- Uses `claim_checker_multiple_template.xml` / `_isolated.xml`, which are unmodified copies of
  `claim_submission_multiple_template.xml` / `_isolated.xml` (same convention as `ClaimCheckerSelfPay`'s templates —
  no content actually differs for the "claim checker" variant, only the endpoint it's sent to).
- The final request is sent via `SendClaimCheckerZipped` (posts to the `claim_checker` endpoints in
  `system_defaults.json`, zipped payload) instead of `SendClaimSubmissionZipped`.

### ClaimSubmissionMultipleActivities
- **Chain**: Person Register → Prior Request (multiple activities) → Claim Submission (multiple activities) (request under test).

### ClaimSubmissionSelfPay
- **Chain**: Person Register (self pay, sent via `SendPersonRegisterProvider`) → Claim Submission (self pay) (request under test).
- No Prior Request step (self-pay claims don't require prior authorization/request).

### PreconditionClaimSubmission
- **Chain**: Person Register → Prior Request → Claim Submission (request under test).
- `live_data` is always overridden to `self.prerequisites` (this class is instantiated from a
  `'claim submission (<precondition>)'` regex match in `request_mapper_context.py`, so the parenthesized precondition
  text becomes the live data for the claim submission step directly, bypassing the normal `live_data` argument).

### SecondClaimNoRemittance
- **Chain**: Person Register → Prior Request → Claim Submission → Claim Resubmission (no remittance) (request under test).

### ClaimSubmissionToTPA
- **Chain**: Person Register (TPA) → Prior Request to TPA → Claim Submission to TPA (request under test).

### ClaimSubmissionMultipleClaims
- **Chain**: Person Register → Prior Request → Prior Authorization → Claim Submission (multiple claims) (request under test).

### ClaimSubmissionMultipleClaimsZipped
- **Chain**: Person Register → Prior Request → Prior Authorization → Claim Submission (multiple claims), sent zipped
  via `SendClaimSubmissionZipped` (request under test).

### ClaimResubmissionToTakeBack
- **Chain**: Person Register → Prior Request → Claim Submission → Remittance Advice (takeback) → Claim Resubmission
  (correction) (request under test).

### ClaimResubmission
- **Chain**: Person Register → Prior Request → Claim Submission → Remittance Advice → Claim Resubmission (request under test).
- Does **not** use per-step live data extraction (all prerequisite steps always send `live_data=None`); only the
  final resubmission step receives the caller's `live_data`. This is the "plain" resubmission flow that
  `ClaimCheckerResubmission` mirrors structurally but with live-data wiring added.

### ClaimResubmissionConsultation
- **Chain**: Person Register → Prior Request (consultation) → Claim Submission → Remittance Advice → Claim
  Resubmission (request under test).

### ClaimResubmissionConsultationNoRemittance
- **Chain**: Person Register → Prior Request (consultation) → Claim Submission → Claim Resubmission (no remittance)
  (request under test). No Remittance Advice step.

### ClaimSecondResubmission
- **Chain**: Person Register → Prior Request → Claim Submission → Claim Resubmission (1st) → Claim Submission (2nd
  resubmission) (request under test).
- Isolated mode sends only the single self-contained 2nd-resubmission template (`claim submission second
  resubmission isolated`), like every other isolated-mode implementation.

### RemittanceAdvice
- **Chain**: Person Register → Prior Request → Claim Submission → Remittance Advice (request under test).

### RemittanceAdviceMultipleActivities
- **Chain**: Person Register → Prior Request (multiple activities) → Claim Submission (multiple activities) →
  Remittance Advice (multiple activities) (request under test).

### RemittanceAdviceTPA
- **Chain**: Person Register (TPA) → Prior Request to TPA → Claim Submission to TPA → Remittance Advice TPA
  (request under test).

### CostSubmission
- **Chain**: Person Register → Prior Request → Claim Submission → Cost Submission (request under test).

### CostSubmissionMultipleClaims
- **Chain**: Person Register → Prior Request → Claim Submission (multiple claims) → Cost Submission (multiple
  claims) (request under test).

### CostSubmissionZipped
- **Chain**: Person Register → Prior Request → Claim Submission → Cost Submission, sent zipped via
  `SendCostSubmissionZipped` (request under test).

### CostResubmission
- **Chain**: Person Register → Prior Request → Claim Submission → Cost Submission → Cost Resubmission (request
  under test).

### RemittanceAdviceMultipleClaims
- **Chain**: Person Register → Prior Request → Claim Submission (multiple claims) → Remittance Advice (multiple
  claims) (request under test).

### SecondRemittanceAdvice
- **Chain**: Person Register → Prior Request → Claim Submission → Remittance Advice (takeback) → Claim Resubmission
  (correction) → Second Remittance Advice (request under test).
- Only implements full-scenario logic unconditionally (no `if self.xxx_template is None` guard around the whole
  chain) — every call rebuilds the full chain. `_do_single_request` is not really usable standalone; the class
  effectively requires full-scenario execution.

### ThirdRemittanceAdvice
- **Chain**: Person Register → Prior Request → Claim Submission → Remittance Advice (takeback) → Claim Resubmission
  (correction) → Remittance Advice (2nd takeback) → Claim Resubmission (correction, 2nd) → Third/Second Remittance
  Advice (request under test).
- Same as `SecondRemittanceAdvice`: always rebuilds the full chain, not meant for single-request mode.

### SecondRemittanceAdviceAfterTKBK
- **Chain**: Person Register → Prior Request → Claim Submission → Remittance Advice (takeback) → Second Remittance
  Advice (request under test).
- `_do_single_request` explicitly raises `Exception("Please use full scenario for this transaction type")` — this
  transaction cannot run in isolated/single-request mode at all.

### RemittanceAdviceHAADClaim
- **Chain**: Person Register → Prior Request → Claim Submission (HAAD) → Remittance Advice (request under test).

---

## Non-chained / API-style transactions

These don't follow the "person register → ... → request under test" pattern. Instead, they optionally run a single
arbitrary prerequisite transaction (recursively resolved via `do_requests()` from a `Precondition` string) and use its
response/template data to populate fields on the request under test — used for the search/download/reconciliation
family of API calls, where the object of interest is "whatever transaction was produced right before this one."

### SearchTransactions
- If `self.prerequisites` is set, treats it as a newline-delimited precondition list. The **last** line names the
  prerequisite transaction; the rest (`[:-1]`) are that prerequisite's own preconditions. Recursively resolves it via
  `do_requests(...).do_request(system)`, asserts it had no errors, then maps fields from its response/template
  (fileName, SenderID → callerLicense, ReceiverID → ePartner, login, pwd, transaction ID) into the Search Transactions
  request. If no prerequisites, sends Search Transactions with just the caller's `live_data`.

### GetNewPriorAuthorizationTransactions
- Same recursive-prerequisite pattern as `SearchTransactions`, mapping fileName, SenderID, and
  login/pwd (derived from ReceiverID via `get_login_from_id`/`get_password_from_id`) into the Get New Prior
  Authorization Transactions request.

### GetNewTransactions
- Same pattern, mapping SenderID and login/pwd (derived from ReceiverID) into the Get New Transactions request.

### DownloadTransaction
- Same pattern, mapping the prerequisite's transaction ID (from its response `content`) plus login/pwd (derived from
  ReceiverID) into the Download Transaction request.

### SetTransactionDownloaded
- Same pattern as `DownloadTransaction`, targeting the Set Transaction Downloaded request.

### Reconciliation
- Same pattern, mapping login/pwd (from the prerequisite's request XML) and the prerequisite transaction's tag name
  (as `transactionName`) into the Claim Count Reconciliation request.

### GetPersonInsuranceHistory
- Same pattern, mapping login/pwd plus `EmiratesIDNumber` → `EmiratesID` and `UnifiedNumber` → `UnifiedID` from the
  prerequisite template into the Get Person Insurance History request.

### PayForQuality
- No prerequisites, no chain, no `_should_use_single_request()` check — always sends `pay_for_quality` directly
  with the caller's `live_data`.

### DefaultAbstractRequest
- Fallback used by `do_requests()` when the requested transaction name doesn't match any known request. Always
  raises `Exception(f"Unexpected type of request {self.request_name}")`.

---

## Summary table

| Class | Prerequisite chain (in order) | Request under test | Per-step live data? |
|---|---|---|---|
| PersonRegister | — | Person Register | No |
| PersonRegisterResubmission | Person Register | Person Register Resubmission | No |
| PersonRegisterTPA | — | Person Register TPA | No |
| PriorRequest | Person Register | Prior Request | No |
| PriorRequestToTPA | Person Register (TPA) | Prior Request to TPA | No |
| PriorRequestMultipleXmls | Person Register, Prior Request | Prior Request (multi XML send) | No |
| PriorRequestGreaterThan6MB | Person Register, Prior Request, Prior Authorization | Prior Request Resubmission (>6MB) | No |
| PriorRequestResubmission | Person Register, Prior Request, Prior Authorization | Prior Request Resubmission | No |
| PriorRequestZipped | Person Register, Prior Request | Prior Request (zipped send) | No |
| PriorAuthorizationPrescription | Person Register, Prior Request (prescription) | Prior Authorization (prescription) | No |
| PriorAuthorizationCancellation | Person Register, Prior Request (cancellation) | Prior Authorization (cancellation) | No |
| PriorAuthorizationExtension | Person Register, Prior Request (extension) | Prior Authorization (extension) | No |
| PriorAuthorizationEligibility | Person Register, Prior Request (eligibility) | Prior Authorization (eligibility) | No |
| PriorAuthorizationLarge | Person Register, Prior Request | Prior Authorization (large) | No |
| PriorAuthorization | Person Register, Prior Request | Prior Authorization | No |
| PriorAuthorizationTPA | Person Register TPA, Prior Request to TPA | Prior Authorization TPA | No |
| ClaimSubmission | Person Register, Prior Request | Claim Submission | No |
| **ClaimChecker** | Person Register, Prior Request, Prior Authorization | Claim Checker | **Yes** |
| **PersonCorrectedClaimChecker** | Person Register, Person Register Resubmission (2nd/correction), Prior Request, Prior Authorization | Claim Checker | **Yes** (full-scenario only; single-request raises) |
| **ClaimCheckerNoPriorAuthorization** | Person Register, Prior Request | Claim Checker (no prior auth) | **Yes** |
| **ClaimCheckerResubmission** | Person Register, Prior Request, Claim Submission, Remittance Advice | Claim Checker Resubmission | **Yes** |
| **ClaimCheckerNoRemittance** | Person Register, Prior Request, Claim Submission | Claim Checker (no remittance) | **Yes** |
| **ClaimCheckerConsultationNoRemittance** | Person Register, Prior Request Consultation, Claim Submission | Claim Checker (no remittance) | **Yes** |
| **ClaimCheckerSelfPay** | Person Register (self pay) | Claim Checker (self pay) | **Yes** |
| **ClaimCheckerMultipleClaimsZipped** | Person Register, Prior Request, Prior Authorization | Claim Checker (multi claims, zipped send) | **Yes** |
| ClaimSubmissionMultipleActivities | Person Register, Prior Request (multi activity) | Claim Submission (multi activity) | No |
| ClaimSubmissionSelfPay | Person Register (self pay) | Claim Submission (self pay) | No |
| PreconditionClaimSubmission | Person Register, Prior Request | Claim Submission (live_data = precondition text) | No |
| SecondClaimNoRemittance | Person Register, Prior Request, Claim Submission | Claim Resubmission (no remittance) | No |
| ClaimSubmissionToTPA | Person Register (TPA), Prior Request to TPA | Claim Submission to TPA | No |
| ClaimSubmissionMultipleClaims | Person Register, Prior Request, Prior Authorization | Claim Submission (multi claims) | No |
| ClaimSubmissionMultipleClaimsZipped | Person Register, Prior Request, Prior Authorization | Claim Submission (multi claims, zipped send) | No |
| ClaimResubmissionToTakeBack | Person Register, Prior Request, Claim Submission, Remittance Advice (takeback) | Claim Resubmission (correction) | No |
| ClaimResubmission | Person Register, Prior Request, Claim Submission, Remittance Advice | Claim Resubmission | No |
| ClaimResubmissionConsultation | Person Register, Prior Request (consultation), Claim Submission, Remittance Advice | Claim Resubmission | No |
| ClaimResubmissionConsultationNoRemittance | Person Register, Prior Request (consultation), Claim Submission | Claim Resubmission (no remittance) | No |
| ClaimSecondResubmission | Person Register, Prior Request, Claim Submission, Claim Resubmission (1st) | Claim Submission (2nd resubmission) | No |
| RemittanceAdvice | Person Register, Prior Request, Claim Submission | Remittance Advice | No |
| RemittanceAdviceMultipleActivities | Person Register, Prior Request (multi activity), Claim Submission (multi activity) | Remittance Advice (multi activity) | No |
| RemittanceAdviceTPA | Person Register (TPA), Prior Request to TPA, Claim Submission to TPA | Remittance Advice TPA | No |
| CostSubmission | Person Register, Prior Request, Claim Submission | Cost Submission | No |
| CostSubmissionMultipleClaims | Person Register, Prior Request, Claim Submission (multi claims) | Cost Submission (multi claims) | No |
| CostSubmissionZipped | Person Register, Prior Request, Claim Submission | Cost Submission (zipped send) | No |
| CostResubmission | Person Register, Prior Request, Claim Submission, Cost Submission | Cost Resubmission | No |
| RemittanceAdviceMultipleClaims | Person Register, Prior Request, Claim Submission (multi claims) | Remittance Advice (multi claims) | No |
| SecondRemittanceAdvice | Person Register, Prior Request, Claim Submission, Remittance Advice (tkbk), Claim Resubmission (correction) | Second Remittance Advice | No (full-scenario only) |
| ThirdRemittanceAdvice | ...as above, plus 2nd tkbk + 2nd correction | Third/Second Remittance Advice | No (full-scenario only) |
| SecondRemittanceAdviceAfterTKBK | Person Register, Prior Request, Claim Submission, Remittance Advice (tkbk) | Second Remittance Advice | No (full-scenario only; single-request raises) |
| RemittanceAdviceHAADClaim | Person Register, Prior Request, Claim Submission (HAAD) | Remittance Advice | No |
| SearchTransactions | (dynamic: recursively resolved prerequisite transaction) | Search Transactions | N/A (field-mapping, not live_data prefix) |
| GetNewPriorAuthorizationTransactions | (dynamic) | Get New Prior Authorization Transactions | N/A |
| GetNewTransactions | (dynamic) | Get New Transactions | N/A |
| DownloadTransaction | (dynamic) | Download Transaction | N/A |
| SetTransactionDownloaded | (dynamic) | Set Transaction Downloaded | N/A |
| Reconciliation | (dynamic) | Claim Count Reconciliation | N/A |
| GetPersonInsuranceHistory | (dynamic) | Get Person Insurance History | N/A |
| PayForQuality | — | Pay For Quality | No |
| DefaultAbstractRequest | — | raises exception (unknown request name) | N/A |

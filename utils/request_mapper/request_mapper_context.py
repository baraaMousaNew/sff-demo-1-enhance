import re

from utils.request_mapper.request_mapper import SecondRemittanceAdviceAfterTKBK, PersonRegisterTPA, PriorRequestToTPA, \
    PriorAuthorizationTPA, ClaimSubmissionToTPA, RemittanceAdviceTPA, SecondClaimNoRemittance, Reconciliation, \
    GetPersonInsuranceHistory, PreconditionClaimSubmission, ClaimResubmissionToTakeBack, \
    ClaimResubmissionConsultation, ClaimSubmissionSelfPay, PersonRegisterResubmission, \
    ClaimSubmissionMultipleActivities, RemittanceAdviceMultipleActivities, ThirdRemittanceAdvice, \
    ClaimResubmissionConsultationNoRemittance, PayForQuality
from utils.request_mapper.request_mapper import PriorRequestMultipleXmls
from utils.request_mapper.request_mapper import PriorRequest, PersonRegister, PriorAuthorization, \
    ClaimSubmission, RemittanceAdvice, DefaultAbstractRequest, SearchTransactions, GetNewTransactions, \
    DownloadTransaction, SetTransactionDownloaded, PriorRequestResubmission, PriorRequestZipped, \
    PriorAuthorizationPrescription, \
    PriorAuthorizationCancellation, PriorAuthorizationExtension, PriorAuthorizationEligibility, PriorAuthorizationLarge, \
    ClaimResubmission, RemittanceAdviceHAADClaim, ClaimSecondResubmission, ClaimCheckerSecondResubmission, SecondRemittanceAdvice, \
    RemittanceAdviceMultipleClaims, PriorRequestGreaterThan6MB, GetNewPriorAuthorizationTransactions, \
    ClaimSubmissionMultipleClaims, ClaimSubmissionMultipleClaimsZipped, CostSubmission, CostSubmissionMultipleClaims, CostSubmissionZipped, CostResubmission, \
    ClaimChecker, ClaimCheckerNoPriorAuthorization, ClaimCheckerResubmission, PersonCorrectedClaimChecker, \
    ClaimCheckerNoRemittance, ClaimCheckerConsultationNoRemittance, ClaimCheckerSelfPay, ClaimCheckerMultipleClaimsZipped
from utils.template_generator.requests_name_enums import RequestsName


def do_requests(under_test_request, prerequisites):
    if under_test_request.lower() == RequestsName.person_register.value:
        return PersonRegister(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.person_register_tpa.value:
        return PersonRegisterTPA(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.person_register_resubmission.value:
        return PersonRegisterResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_request.value:
        return PriorRequest(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_request_to_tpa.value:
        return PriorRequestToTPA(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization.value:
        return PriorAuthorization(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_tpa.value:
        return PriorAuthorizationTPA(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission.value:
        return ClaimSubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission_multiple_activities.value:
        return ClaimSubmissionMultipleActivities(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.remittance_advice_multiple_activities.value:
        return RemittanceAdviceMultipleActivities(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission_self_pay.value:
        return ClaimSubmissionSelfPay(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_resubmission_consultation.value:
        return ClaimResubmissionConsultation(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_resubmission_consultation_no_remittance.value:
        return ClaimResubmissionConsultationNoRemittance(prerequisites=prerequisites)
    elif match := re.match(rf'{RequestsName.claim_submission.value} \((.+)\)', under_test_request, re.IGNORECASE):
        return PreconditionClaimSubmission(prerequisites=match.group(1))
    elif under_test_request.lower() == RequestsName.claim_submission_to_tpa.value:
        return ClaimSubmissionToTPA(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_checker.value:
        return ClaimChecker(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_checker_no_prior_authorization.value:
        return ClaimCheckerNoPriorAuthorization(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_checker_resubmission.value:
        return ClaimCheckerResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_checker_no_remittance.value:
        return ClaimCheckerNoRemittance(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_checker_consultation_no_remittance.value:
        return ClaimCheckerConsultationNoRemittance(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_checker_self_pay.value:
        return ClaimCheckerSelfPay(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_checker_multiple_claims_zipped.value:
        return ClaimCheckerMultipleClaimsZipped(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.remittance_advice.value:
        return RemittanceAdvice(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.remittance_advice_tpa.value:
        return RemittanceAdviceTPA(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_request_resubmission.value:
        return PriorRequestResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_request_zipped.value:
        return PriorRequestZipped(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_prescription.value:
        return PriorAuthorizationPrescription(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_cancellation.value:
        return PriorAuthorizationCancellation(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_extension.value:
        return PriorAuthorizationExtension(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_eligibility.value:
        return PriorAuthorizationEligibility(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_large.value:
        return PriorAuthorizationLarge(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission_resubmission.value:
        return ClaimResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.remittance_advice_haad_claim.value:
        return RemittanceAdviceHAADClaim(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_resubmission_to_takeback.value:
        return ClaimResubmissionToTakeBack(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission_multiple_claims.value:
        return ClaimSubmissionMultipleClaims(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission_multiple_claims_zipped.value:
        return ClaimSubmissionMultipleClaimsZipped(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission_second_resubmission.value:
        return ClaimSecondResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_checker_second_resubmission.value:
        return ClaimCheckerSecondResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.person_corrected_claim_checker.value:
        return PersonCorrectedClaimChecker(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.second_remittance_advice.value:
        return SecondRemittanceAdvice(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.third_remittance_advice.value:
        return ThirdRemittanceAdvice(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.second_remittance_after_tkbk.value:
        return SecondRemittanceAdviceAfterTKBK(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.remittance_advice_multiple_claims.value:
        return RemittanceAdviceMultipleClaims(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_request_greater_than_6MB.value:
        return PriorRequestGreaterThan6MB(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.cost_submission.value:
        return CostSubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.cost_submission_multiple_claims.value:
        return CostSubmissionMultipleClaims(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.cost_submission_zipped.value:
        return CostSubmissionZipped(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.cost_resubmission.value:
        return CostResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_request_multiple_xmls.value:
        return PriorRequestMultipleXmls(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_resubmission_no_remittance.value:
        return SecondClaimNoRemittance(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.pay_for_quality.value:
        return PayForQuality(prerequisites=prerequisites)
    else:
        return DefaultAbstractRequest(prerequisites=prerequisites, request_name=under_test_request)


# Only ever run from the Assertion tab — the only place these 7 mappers are constructed.
def do_assertion_requests(under_test_request, prerequisites):
    if under_test_request.lower() == RequestsName.search_transactions.value:
        return SearchTransactions(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.get_new_transactions.value:
        return GetNewTransactions(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.download_transaction.value:
        return DownloadTransaction(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.set_transaction_downloaded.value:
        return SetTransactionDownloaded(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.get_new_prior_authorization.value:
        return GetNewPriorAuthorizationTransactions(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.reconciliation_transaction.value:
        return Reconciliation(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.get_person_insurance_history.value:
        return GetPersonInsuranceHistory(prerequisites=prerequisites)
    else:
        return DefaultAbstractRequest(prerequisites=prerequisites, request_name=under_test_request)



from utils.request_mapper.request_mapper import PriorRequest, PersonRegister, PriorAuthorization, \
    ClaimSubmission, RemittanceAdvice, DefaultAbstractRequest, SearchTransactions, GetNewTransactions, \
    DownloadTransaction, SetTransactionDownloaded, PriorRequestResubmission, PriorRequestZipped, \
    PersonRegisterResubmission, PriorAuthorizationResubmission, PriorAuthorizationPrescription, \
    PriorAuthorizationCancellation, PriorAuthorizationExtension, PriorAuthorizationEligibility, PriorAuthorizationLarge, \
    ClaimResubmission, RemittanceAdviceHAADClaim, ClaimSecondResubmission, SecondRemittanceAdvice, \
    RemittanceAdviceMultipleClaims, PriorRequestGreaterThan6MB, GetNewPriorAuthorizationTransactions, \
    ClaimSubmissionMultipleClaims, CostSubmission, CostResubmission
from utils.template_generator.requests_name_enums import RequestsName


def do_requests(under_test_request, prerequisites):
    if under_test_request.lower() == RequestsName.person_register.value:
        return PersonRegister(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_request.value:
        return PriorRequest(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization.value:
        return PriorAuthorization(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission.value:
        return ClaimSubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.remittance_advice.value:
        return RemittanceAdvice(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.search_transactions.value:
        return SearchTransactions(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.get_new_transactions.value:
        return GetNewTransactions(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.download_transaction.value:
        return DownloadTransaction(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.set_transaction_downloaded.value:
        return SetTransactionDownloaded(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_request_resubmission.value:
        return PriorRequestResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_request_zipped.value:
        return PriorRequestZipped(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.person_register_resubmission.value:
        return PersonRegisterResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_resubmission.value:
        return PriorAuthorizationResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_prescription.value:
        return PriorAuthorizationPrescription(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_cancellation.value:
        return PriorAuthorizationCancellation(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_extension.value:
        return PriorAuthorizationExtension(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_eligibility.value:
        return PriorAuthorizationEligibility(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_extension.value:
        return PriorAuthorizationLarge(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_authorization_large.value:
        return PriorAuthorizationLarge(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission_resubmission.value:
        return ClaimResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.remittance_advice_haad_claim.value:
        return RemittanceAdviceHAADClaim(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission_multiple_claims.value:
        return ClaimSubmissionMultipleClaims(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.claim_submission_second_resubmission.value:
        return ClaimSecondResubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.second_remittance_advice.value:
        return SecondRemittanceAdvice(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.remittance_advice_multiple_claims.value:
        return RemittanceAdviceMultipleClaims(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.prior_request_greater_than_6MB.value:
        return PriorRequestGreaterThan6MB(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.get_new_prior_authorization.value:
        return GetNewPriorAuthorizationTransactions(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.cost_submission.value:
        return CostSubmission(prerequisites=prerequisites)
    elif under_test_request.lower() == RequestsName.cost_resubmission.value:
        return CostResubmission(prerequisites=prerequisites)
    else:
        return DefaultAbstractRequest(prerequisites=prerequisites, request_name=under_test_request)



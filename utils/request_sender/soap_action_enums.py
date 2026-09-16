import re
from enum import Enum

from utils.template_generator.requests_name_enums import RequestsName


class SoapAction(Enum):
    UPLOAD_TRANSACTION = "UploadTransaction"
    SEARCH_TRANSACTIONS = "SearchTransactions"
    GET_CLAIM_COUNT_RECONCILIATION = "GetClaimCountReconciliation"
    GET_PERSON_INSURANCE_HISTORY = "GetPersonInsuranceHistory"
    GET_NEW_PRIOR_AUTHORIZATION_TRANSACTIONS = "GetNewPriorAuthorizationTransactions"
    GET_NEW_TRANSACTIONS = "GetNewTransactions"
    DOWNLOAD_TRANSACTION_FILE = "DownloadTransactionFile"
    SET_TRANSACTION_DOWNLOADED = "SetTransactionDownloaded"


# Maps RequestsName values to their SoapAction.
# Transactions not listed here default to UPLOAD_TRANSACTION.
_TRANSACTION_TO_SOAP_ACTION: dict[str, SoapAction] = {
    RequestsName.search_transactions.value:      SoapAction.SEARCH_TRANSACTIONS,
    RequestsName.get_new_transactions.value:     SoapAction.GET_NEW_TRANSACTIONS,
    RequestsName.download_transaction.value:     SoapAction.DOWNLOAD_TRANSACTION_FILE,
    RequestsName.set_transaction_downloaded.value: SoapAction.SET_TRANSACTION_DOWNLOADED,
    RequestsName.get_new_prior_authorization.value: SoapAction.GET_NEW_PRIOR_AUTHORIZATION_TRANSACTIONS,
    RequestsName.reconciliation_transaction.value: SoapAction.GET_CLAIM_COUNT_RECONCILIATION,
    RequestsName.get_person_insurance_history.value: SoapAction.GET_PERSON_INSURANCE_HISTORY,
    RequestsName.upload_transaction.value: SoapAction.UPLOAD_TRANSACTION,
}


def get_soap_action(transaction_name: str) -> SoapAction | None:
    """Return the SoapAction for the given transaction name (case-insensitive).
    Returns None if the transaction name is not recognised."""
    return _TRANSACTION_TO_SOAP_ACTION.get(transaction_name.strip().lower())


def extract_namespace(xml_string: str) -> str:
    """Extract the namespace URI of the operation element (first child of soap:Body).
    Falls back to the xmlns:ns1 attribute if the body cannot be parsed.
    Returns an empty string if nothing is found."""
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_string)
        body = root.find("{http://schemas.xmlsoap.org/soap/envelope/}Body")
        if body is not None:
            children = list(body)
            if children:
                tag = children[0].tag          # e.g. "{https://www.shafafiya.org/v2/}GetPersonInsuranceHistory"
                if tag.startswith("{"):
                    return tag[1:].split("}")[0]  # extract the URI between { and }
    except Exception:
        pass
    # Fallback: scan for xmlns:* declarations and return the first non-soap namespace
    match = re.search(r'xmlns:\w+="([^"]+)"', xml_string)
    return match.group(1) if match else ""


def build_soap_action(transaction_name: str, xml_string: str) -> str | None:
    """Derive the full SOAPAction header value from the transaction name and payload XML.
    Returns None if the transaction name is not recognised."""
    action = get_soap_action(transaction_name)
    if action is None:
        return None
    namespace = extract_namespace(xml_string)
    return f"{namespace}{action.value}"

from abc import ABC

import allure
import pytest
import re
import xml.etree.ElementTree as ET

from functions.custom_functions import get_current_date_iso, format_date_to_iso
from utils.request_mapper.request_mapper import SearchTransactions
from utils.template_generator.extract_data_strategy.extract_data_context import ExtractDataContext
from utils.template_generator.requests_name_enums import RequestsName
from utils.xml_utils import decode_base64_to_xml
from utils.asserter.error_text_processor import ErrorTextProcessor

def _local_tag(elem):
    tag = elem.tag
    return tag.split('}')[-1] if '}' in tag else tag


def _extract_from_matching_parent(xml_root, parent_tag, filters, extract_tag):
    for elem in xml_root.iter():
        if _local_tag(elem) != parent_tag:
            continue
        all_match = all(
            any(_local_tag(child) == fk and child.text == fv for child in elem.iter())
            for fk, fv in filters.items()
        )
        if not all_match:
            continue
        for child in elem.iter():
            if _local_tag(child) == extract_tag:
                return child.text
    return None


requests_qualified_for_custom_asserter = [RequestsName.search_transactions.value, RequestsName.get_new_prior_authorization.value,
                                          RequestsName.get_new_transactions.value, RequestsName.download_transaction.value,
                                          RequestsName.set_transaction_downloaded.value, RequestsName.reconciliation_transaction.value,
                                          RequestsName.get_person_insurance_history.value]

class CustomAsserterContext:

    def __init__(self, request:str):
        self.request = request

    def get_request_strategy(self):
        if self.request.lower().strip() in requests_qualified_for_custom_asserter:
            return XMLSearchTransactionsStrategy(self.request)
        else:
            return DefaultTransactionsStrategy(self.request)



class CustomAsserter(ABC):

    def __init__(self, request):
        self.request = request

    def found(self, response, prerequisite, template):
        pass

    def found_downloaded(self, response, prerequisite, template):
        pass

    def not_found(self, response, prerequisite):
        pass

    def error(self, response, error_message):
        pass

    def downloaded(self, template, response):
        pass

    def determine(self, template, response, prerequisite, expected):
        pass

    def set_downloaded(self, template, response):
        pass

    def report_generated(self, template, response):
        pass

    def element(self, element, response, expected):
        pass

    def file_found(self, response, expected, template):
        pass

    def file_not_found(self, response, expected, template):
        pass



class XMLSearchTransactionsStrategy(CustomAsserter):

    def __init__(self, request:str):
        super().__init__(request)

    def determine(self, template, response, prerequisite, expected):
        lines = [line.strip() for line in expected.split('\n') if line.strip()]
        for line in lines:
            line_lower = line.lower()
            if line_lower in ['new transaction retrieved', 'new transaction found', 'new transaction request found', 'new transaction request is found', 'new transaction request retrieved', 'new transaction request is retrieved', 'new transaction transaction found', 'new transaction transaction is found', 'new transaction transaction retrieved', 'new transaction transaction is retrieved']:
                self.new_transaction_found(response, prerequisite, template)
            elif line_lower in ['new prior auth retrieved', 'new prior auth found', 'new prior auth request found', 'new prior auth request is found', 'new prior auth request retrieved', 'new prior auth request is retrieved', 'new prior auth transaction found', 'new prior auth transaction is found', 'new prior auth transaction retrieved', 'new prior auth transaction is retrieved']:
                self.prior_auth_found(response, prerequisite, template)
            elif line_lower in ['retrieved', 'found', 'request found', 'request is found', 'request retrieved', 'request is retrieved', 'transaction found', 'transaction is found', 'transaction retrieved', 'transaction is retrieved']:
                self.found(response, prerequisite, template)
            elif line_lower in ['retrieved downloaded', 'found downloaded', 'request found downloaded', 'request is found downloaded', 'request retrieved downloaded', 'request is retrieved downloaded', 'transaction found downloaded', 'transaction is found downloaded', 'transaction retrieved downloaded', 'transaction is retrieved downloaded']:
                self.found_downloaded(response, prerequisite, template)
            elif line_lower in ['not retrieved', 'not found', 'request not found', 'request is not found', 'request not retrieved', 'request is not retrieved', 'transaction  not found', 'transaction is  not found', 'transaction  not retrieved', 'transaction is  not retrieved']:
                self.not_found(response, prerequisite)
            elif line_lower in ['report generated', 'report is generated']:
                self.report_generated(template, response)
            elif line_lower.startswith('errorcode'):
                try:
                    error_code = line.split('-', 1)[1].strip()
                    self._custom_error_code(response, error_code)
                except IndexError:
                    pytest.fail("Issue with error code. Make sure to use the format ErrorCode - {error_code}")
            elif line_lower.startswith('error'):
                try:
                    error_message = line.split('-', 1)[1].strip()
                    self.error(response, error_message, template)
                except IndexError:
                    pytest.fail("Issue with error message. Make sure to use the format Error - {error_message}")
            elif line_lower in ['downloaded', 'request is downloaded', 'request downloaded']:
                self.downloaded(template, response)
            elif line_lower in ['set downloaded', 'request is set downloaded', 'request set downloaded']:
                self.set_downloaded(template, response)
            elif line_lower.startswith('element'):
                try:
                    element = line.split('-', 1)[1].strip()
                    self.element(element, response, expected)
                except IndexError:
                    pytest.fail("Issue with element assertion. Make sure to use the format Element - elementTag = expected_value")
            elif line_lower.startswith('file not found') or line_lower.startswith('file is not found'):
                try:
                    pairs_str = line.split('-', 1)[1].strip()
                    self.file_not_found(response, pairs_str, template)
                except IndexError:
                    pytest.fail("Issue with file not found assertion. Make sure to use the format File Not Found - key1 = value1; key2 = value2")
            elif line_lower.startswith('file found') or line_lower.startswith('file is found'):
                try:
                    pairs_str = line.split('-', 1)[1].strip()
                    self.file_found(response, pairs_str, template)
                except IndexError:
                    pytest.fail("Issue with file found assertion. Make sure to use the format File Found - key1 = value1; key2 = value2")
            else:
                pytest.fail(f"Unexpected: {line}.")

    def element(self, element, response, expected):
        # Split on the first '=' that is NOT inside brackets [...], to correctly handle
        # filtered tag syntax like: ParentTag[key=val].childTag = expected_value
        split_match = re.match(r'^(\w+(?:\[[^\]]+\]\.\w+)?)\s*=\s*(.+)$', element, re.DOTALL)
        if not split_match:
            pytest.fail(f"Invalid element format '{element}'. Use: Element - elementTag = expected_value")
        element_tag = split_match.group(1).strip()
        expected_value = split_match.group(2).strip()

        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)

        # Filtered search: ParentElement[filterChild=filterValue,...].extractChild
        filtered_match = re.match(r'^(\w+)\[([^\]]+)\]\.(\w+)$', element_tag)
        if filtered_match:
            parent_tag  = filtered_match.group(1)
            filters_str = filtered_match.group(2)
            extract_tag = filtered_match.group(3)
            filters = {}
            for f in filters_str.split(','):
                if '=' in f:
                    fk, fv = [p.strip() for p in f.split('=', 1)]
                    filters[fk] = fv
            actual_value = _extract_from_matching_parent(xml_response_body, parent_tag, filters, extract_tag)
        else:
            actual_element = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, element_tag)
            actual_value = actual_element.text if actual_element is not None else None

        with allure.step(f"Assert element '{element_tag}' equals '{expected_value}'"):
            if actual_value is None:
                allure.dynamic.tag("System 1 Failure")
                allure.dynamic.label("failure_reason", "system_1_issue")
                allure.dynamic.tag("System 1 Failure")
                allure.dynamic.label("failure_reason", "system_1_issue")
                pytest.fail(f"Element '{element_tag}' not found in response")

            allure.attach(
                f"Element: {element_tag}\nExpected: {expected_value}\nActual: {actual_value}",
                name='e4c52a - Element value verification',
                attachment_type=allure.attachment_type.TEXT
            )

            if actual_value != expected_value:
                allure.dynamic.tag("System 1 Failure")
                allure.dynamic.label("failure_reason", "system_1_issue")
                pytest.fail(f"Element '{element_tag}': expected '{expected_value}' but got '{actual_value}'")

    def not_found(self, response, prerequisite):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        try:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'foundTransactions')
            xml_files = ET.fromstring(files.text)
        except AttributeError:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'xmlTransactions')
            if files is None:
                allure.dynamic.tag("System 1 Failure")
                allure.dynamic.label("failure_reason", "system_1_issue")
                pytest.fail("Neither 'foundTransactions' nor 'xmlTransactions' element was found in the response")
            xml_files = ET.fromstring(files.text)
        expected_transaction_id = ExtractDataContext(
            ET.fromstring(prerequisite['content'])).decide_template_type().extract_from_template(
            ET.fromstring(prerequisite['content']), 'TransactionID')
        found = False
        with allure.step(f"Assert transaction {expected_transaction_id} is not found"):
            for file in xml_files.findall('File'):
                file_dictionary = file.attrib
                allure.attach(
                    f"Actual transaction {file_dictionary['FileID']}",
                    name='2ffe8e - Check against transaction',
                    attachment_type=allure.attachment_type.TEXT
                )
                if file_dictionary['FileID'] == expected_transaction_id:
                    found = True
                    break

            if found:
                allure.attach(
                    f"Expected transaction ID: {expected_transaction_id}\nWas unexpectedly found in the returned transactions.",
                    name='2ffvce - Unexpected transaction found',
                    attachment_type=allure.attachment_type.TEXT
                )
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Transaction {expected_transaction_id} was found")

    def found(self, response, prerequisite, template):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        try:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'foundTransactions')
            xml_files = ET.fromstring(files.text)
        except AttributeError:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'xmlTransactions')
            if files is None:
                allure.dynamic.tag("System 1 Failure")
                allure.dynamic.label("failure_reason", "system_1_issue")
                pytest.fail("Neither 'foundTransactions' nor 'xmlTransactions' element was found in the response")
            xml_files = ET.fromstring(files.text)
        expected_transaction_id = ExtractDataContext(ET.fromstring(prerequisite['content'])).decide_template_type().extract_from_template(
            ET.fromstring(prerequisite['content']), 'TransactionID')
        found = False
        with allure.step(f"Assert transaction {expected_transaction_id} is found"):
            for file in xml_files.findall('File'):
                file_dictionary = file.attrib
                allure.attach(
                    f"Actual transaction {file_dictionary['FileID']}",
                    name='8b450b - Check against transaction',
                    attachment_type=allure.attachment_type.TEXT
                )
                if file_dictionary['FileID'] == expected_transaction_id:
                    found = True
                    allure.attach(
                        f"Actual transaction {file_dictionary['FileID']}",
                        name='d43b5a - Transaction FileID was found',
                        attachment_type=allure.attachment_type.TEXT
                    )
                    expected_file_name = ExtractDataContext(
                        ET.fromstring(prerequisite['request_xml'])).decide_template_type().extract_from_template(
                        ET.fromstring(prerequisite['request_xml']), 'fileName')
                    if file_dictionary['FileName'] == expected_file_name:
                        allure.attach(
                            f"Expected file name: {expected_file_name}\nActual file name: {file_dictionary['FileName']}",
                            name='d43b5a - File name match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected file name: {expected_file_name}\nActual file name: {file_dictionary['FileName']}",
                            name='d56775a - File name mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"File name in transaction {expected_transaction_id} is not correct")
                    expected_sender_id = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'SenderID')
                    if file_dictionary['SenderID'] == expected_sender_id:
                        allure.attach(
                            f"Expected sender id: {expected_sender_id}\nActual sender id: {file_dictionary['SenderID']}",
                            name='d4t6577 - Sender ID match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected sender id: {expected_sender_id}\nActual sender id: {file_dictionary['SenderID']}",
                            name='d4ty5a - Sender ID mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Sender ID in transaction {expected_transaction_id} is not correct")
                    expected_receiver_id = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'ReceiverID')
                    if file_dictionary['ReceiverID'] == expected_receiver_id:
                        allure.attach(
                            f"Expected receiver id: {expected_receiver_id}\nActual receiver id: {file_dictionary['ReceiverID']}",
                            name='d4m7ua - Sender ID match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected receiver id: {expected_receiver_id}\nActual receiver id: {file_dictionary['ReceiverID']}",
                            name='d4ml5a - Sender ID mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Receiver ID in transaction {expected_transaction_id} is not correct")
                    expected_record_count = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'RecordCount')
                    if file_dictionary['RecordCount'] == expected_record_count:
                        allure.attach(
                            f"Expected record count: {expected_record_count}\nActual record count: {file_dictionary['RecordCount']}",
                            name='d0popa - record count match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected record count: {expected_record_count}\nActual record count: {file_dictionary['RecordCount']}",
                            name='d4005a - record count mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Record count in transaction {expected_transaction_id} is not correct")
                    expected_transaction_date = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'TransactionDate')
                    if file_dictionary['TransactionDate'] == expected_transaction_date:
                        allure.attach(
                            f"Expected transaction date: {expected_transaction_date}\nActual transaction date: {file_dictionary['TransactionDate']}",
                            name='d4w4nb5a - transaction date match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected transaction date: {expected_transaction_date}\nActual transaction date: {file_dictionary['TransactionDate']}",
                            name='d4ioo5a - transaction date mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Transaction date in transaction {expected_transaction_id} is not correct")
                    iso_transaction_timestamp = format_date_to_iso(file_dictionary['TransactionTimestamp'])
                    iso_current_date = get_current_date_iso()
                    if iso_transaction_timestamp == iso_current_date:
                        allure.attach(
                            f"Expected transaction timestamp: {iso_current_date}\nActual transaction timestamp: {iso_transaction_timestamp}",
                            name='d4ezz5a - transaction timestamp match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected transaction timestamp: {iso_current_date}\nActual transaction timestamp: {iso_transaction_timestamp}",
                            name='d4er05a - transaction timestamp mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"transaction timestamp in transaction {expected_transaction_id} is not correct")
                    expected_downloaded = 'False'
                    if file_dictionary['IsDownloaded'] == expected_downloaded:
                        allure.attach(
                            f"Expected is downloaded: {expected_downloaded}\nActual is downloaded: {file_dictionary['IsDownloaded']}",
                            name='d4jjj5a - is downloaded flag match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected is downloaded: {expected_downloaded}\nActual is downloaded: {file_dictionary['IsDownloaded']}",
                            name='d4tto5a - is downloaded flag mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"is downloaded flag in transaction {expected_transaction_id} is not correct")
                    break
            if not found:
                allure.attach(
                    f"Expected transaction ID: {expected_transaction_id}\nNot found among the returned transactions.",
                    name='8b450b - Transaction not found',
                    attachment_type=allure.attachment_type.TEXT
                )
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Transaction {expected_transaction_id} was not found")

    def prior_auth_found(self, response, prerequisite, template):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        try:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'foundTransactions')
            xml_files = ET.fromstring(files.text)
        except AttributeError:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'xmlTransactions')
            if files is None:
                allure.dynamic.tag("System 1 Failure")
                allure.dynamic.label("failure_reason", "system_1_issue")
                pytest.fail("Neither 'foundTransactions' nor 'xmlTransactions' element was found in the response")
            xml_files = ET.fromstring(files.text)
        expected_transaction_id = ExtractDataContext(ET.fromstring(prerequisite['content'])).decide_template_type().extract_from_template(
            ET.fromstring(prerequisite['content']), 'TransactionID')
        found = False
        with allure.step(f"Assert transaction {expected_transaction_id} is found"):
            for file in xml_files.findall('File'):
                file_dictionary = file.attrib
                allure.attach(
                    f"Actual transaction {file_dictionary['FileID']}",
                    name='8b450b - Check against transaction',
                    attachment_type=allure.attachment_type.TEXT
                )
                if file_dictionary['FileID'] == expected_transaction_id:
                    found = True
                    allure.attach(
                        f"Actual transaction {file_dictionary['FileID']}",
                        name='d43b5a - Transaction FileID was found',
                        attachment_type=allure.attachment_type.TEXT
                    )
                    expected_file_name = ExtractDataContext(
                        ET.fromstring(prerequisite['request_xml'])).decide_template_type().extract_from_template(
                        ET.fromstring(prerequisite['request_xml']), 'fileName')
                    if file_dictionary['FileName'] == expected_file_name:
                        allure.attach(
                            f"Expected file name: {expected_file_name}\nActual file name: {file_dictionary['FileName']}",
                            name='d43b5a - File name match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected file name: {expected_file_name}\nActual file name: {file_dictionary['FileName']}",
                            name='d56775a - File name mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"File name in transaction {expected_transaction_id} is not correct")
                    expected_sender_id = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'SenderID')
                    if file_dictionary['SenderID'] == expected_sender_id:
                        allure.attach(
                            f"Expected sender id: {expected_sender_id}\nActual sender id: {file_dictionary['SenderID']}",
                            name='d4t6577 - Sender ID match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected sender id: {expected_sender_id}\nActual sender id: {file_dictionary['SenderID']}",
                            name='d4ty5a - Sender ID mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Sender ID in transaction {expected_transaction_id} is not correct")
                    expected_receiver_id = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'ReceiverID')
                    if file_dictionary['ReceiverID'] == expected_receiver_id:
                        allure.attach(
                            f"Expected receiver id: {expected_receiver_id}\nActual receiver id: {file_dictionary['ReceiverID']}",
                            name='d4m7ua - Sender ID match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected receiver id: {expected_receiver_id}\nActual receiver id: {file_dictionary['ReceiverID']}",
                            name='d4ml5a - Sender ID mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Receiver ID in transaction {expected_transaction_id} is not correct")
                    expected_record_count = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'RecordCount')
                    if file_dictionary['RecordCount'] == expected_record_count:
                        allure.attach(
                            f"Expected record count: {expected_record_count}\nActual record count: {file_dictionary['RecordCount']}",
                            name='d0popa - record count match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected record count: {expected_record_count}\nActual record count: {file_dictionary['RecordCount']}",
                            name='d4005a - record count mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Record count in transaction {expected_transaction_id} is not correct")
                    expected_transaction_date = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'TransactionDate')
                    if file_dictionary['TransactionDate'] == expected_transaction_date:
                        allure.attach(
                            f"Expected transaction date: {expected_transaction_date}\nActual transaction date: {file_dictionary['TransactionDate']}",
                            name='d4w4nb5a - transaction date match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected transaction date: {expected_transaction_date}\nActual transaction date: {file_dictionary['TransactionDate']}",
                            name='d4ioo5a - transaction date mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Transaction date in transaction {expected_transaction_id} is not correct")
                    expected_downloaded = 'FALSE'
                    if file_dictionary['IsDownloaded'] == expected_downloaded:
                        allure.attach(
                            f"Expected is downloaded: {expected_downloaded}\nActual is downloaded: {file_dictionary['IsDownloaded']}",
                            name='d4jjj5a - is downloaded flag match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected is downloaded: {expected_downloaded}\nActual is downloaded: {file_dictionary['IsDownloaded']}",
                            name='d4tto5a - is downloaded flag mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"is downloaded flag in transaction {expected_transaction_id} is not correct")
                    break
            if not found:
                allure.attach(
                    f"Expected transaction ID: {expected_transaction_id}\nNot found among the returned transactions.",
                    name='8b450b - Transaction not found',
                    attachment_type=allure.attachment_type.TEXT
                )
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Transaction {expected_transaction_id} was not found")

    def new_transaction_found(self, response, prerequisite, template):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        try:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'foundTransactions')
            xml_files = ET.fromstring(files.text)
        except AttributeError:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'xmlTransactions')
            if files is None:
                allure.dynamic.tag("System 1 Failure")
                allure.dynamic.label("failure_reason", "system_1_issue")
                pytest.fail("Neither 'foundTransactions' nor 'xmlTransactions' element was found in the response")
            xml_files = ET.fromstring(files.text)
        expected_transaction_id = ExtractDataContext(ET.fromstring(prerequisite['content'])).decide_template_type().extract_from_template(
            ET.fromstring(prerequisite['content']), 'TransactionID')
        found = False
        with allure.step(f"Assert transaction {expected_transaction_id} is found"):
            for file in xml_files.findall('File'):
                file_dictionary = file.attrib
                allure.attach(
                    f"Actual transaction {file_dictionary['FileID']}",
                    name='8b450b - Check against transaction',
                    attachment_type=allure.attachment_type.TEXT
                )
                if file_dictionary['FileID'] == expected_transaction_id:
                    found = True
                    allure.attach(
                        f"Actual transaction {file_dictionary['FileID']}",
                        name='d43b5a - Transaction FileID was found',
                        attachment_type=allure.attachment_type.TEXT
                    )
                    expected_file_name = ExtractDataContext(
                        ET.fromstring(prerequisite['request_xml'])).decide_template_type().extract_from_template(
                        ET.fromstring(prerequisite['request_xml']), 'fileName')
                    if file_dictionary['FileName'] == expected_file_name:
                        allure.attach(
                            f"Expected file name: {expected_file_name}\nActual file name: {file_dictionary['FileName']}",
                            name='d43b5a - File name match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected file name: {expected_file_name}\nActual file name: {file_dictionary['FileName']}",
                            name='d56775a - File name mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"File name in transaction {expected_transaction_id} is not correct")
                    expected_sender_id = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'SenderID')
                    if file_dictionary['SenderID'] == expected_sender_id:
                        allure.attach(
                            f"Expected sender id: {expected_sender_id}\nActual sender id: {file_dictionary['SenderID']}",
                            name='d4t6577 - Sender ID match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected sender id: {expected_sender_id}\nActual sender id: {file_dictionary['SenderID']}",
                            name='d4ty5a - Sender ID mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Sender ID in transaction {expected_transaction_id} is not correct")
                    expected_receiver_id = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'ReceiverID')
                    if file_dictionary['ReceiverID'] == expected_receiver_id:
                        allure.attach(
                            f"Expected receiver id: {expected_receiver_id}\nActual receiver id: {file_dictionary['ReceiverID']}",
                            name='d4m7ua - Sender ID match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected receiver id: {expected_receiver_id}\nActual receiver id: {file_dictionary['ReceiverID']}",
                            name='d4ml5a - Sender ID mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Receiver ID in transaction {expected_transaction_id} is not correct")
                    expected_record_count = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'RecordCount')
                    if file_dictionary['RecordCount'] == expected_record_count:
                        allure.attach(
                            f"Expected record count: {expected_record_count}\nActual record count: {file_dictionary['RecordCount']}",
                            name='d0popa - record count match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected record count: {expected_record_count}\nActual record count: {file_dictionary['RecordCount']}",
                            name='d4005a - record count mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Record count in transaction {expected_transaction_id} is not correct")
                    expected_transaction_date = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'TransactionDate')
                    if file_dictionary['TransactionDate'] == expected_transaction_date:
                        allure.attach(
                            f"Expected transaction date: {expected_transaction_date}\nActual transaction date: {file_dictionary['TransactionDate']}",
                            name='d4w4nb5a - transaction date match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected transaction date: {expected_transaction_date}\nActual transaction date: {file_dictionary['TransactionDate']}",
                            name='d4ioo5a - transaction date mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Transaction date in transaction {expected_transaction_id} is not correct")
                    expected_downloaded = 'FALSE'
                    if file_dictionary['IsDownloaded'] == expected_downloaded:
                        allure.attach(
                            f"Expected is downloaded: {expected_downloaded}\nActual is downloaded: {file_dictionary['IsDownloaded']}",
                            name='d4jjj5a - is downloaded flag match',
                            attachment_type=allure.attachment_type.TEXT
                        )
                    else:
                        allure.attach(
                            f"Expected is downloaded: {expected_downloaded}\nActual is downloaded: {file_dictionary['IsDownloaded']}",
                            name='d4tto5a - is downloaded flag mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"is downloaded flag in transaction {expected_transaction_id} is not correct")
                    break
            if not found:
                allure.attach(
                    f"Expected transaction ID: {expected_transaction_id}\nNot found among the returned transactions.",
                    name='8b450b - Transaction not found',
                    attachment_type=allure.attachment_type.TEXT
                )
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Transaction {expected_transaction_id} was not found")

    def found_downloaded(self, response, prerequisite, template):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        try:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'foundTransactions')
            xml_files = ET.fromstring(files.text)
        except AttributeError:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'xmlTransactions')
            if files is None:
                allure.dynamic.tag("System 1 Failure")
                allure.dynamic.label("failure_reason", "system_1_issue")
                pytest.fail("Neither 'foundTransactions' nor 'xmlTransactions' element was found in the response")
            xml_files = ET.fromstring(files.text)
        expected_transaction_id = ExtractDataContext(ET.fromstring(prerequisite['content'])).decide_template_type().extract_from_template(
            ET.fromstring(prerequisite['content']), 'TransactionID')
        found = False
        with allure.step(f"Assert transaction {expected_transaction_id} is found"):
            for file in xml_files.findall('File'):
                file_dictionary = file.attrib
                allure.attach(
                    f"Actual transaction {file_dictionary['FileID']}",
                    name='8b450b - Check against transaction',
                    attachment_type=allure.attachment_type.TEXT
                )
                if file_dictionary['FileID'] == expected_transaction_id:
                    found = True
                    allure.attach(
                        f"Actual transaction {file_dictionary['FileID']}",
                        name='d43b5a - Transaction FileID was found',
                        attachment_type=allure.attachment_type.TEXT
                    )
                    expected_file_name = ExtractDataContext(
                        ET.fromstring(prerequisite['request_xml'])).decide_template_type().extract_from_template(
                        ET.fromstring(prerequisite['request_xml']), 'fileName')
                    if file_dictionary['FileName'] != expected_file_name:
                        allure.attach(
                            f"Expected file name: {expected_file_name}\nActual file name: {file_dictionary['FileName']}",
                            name='d43we5a - File name mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"File name in transaction {expected_transaction_id} is not correct")
                    expected_sender_id = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'SenderID')
                    if file_dictionary['SenderID'] != expected_sender_id:
                        allure.attach(
                            f"Expected sender id: {expected_sender_id}\nActual sender id: {file_dictionary['SenderID']}",
                            name='d4ty5a - Sender ID mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Sender ID in transaction {expected_transaction_id} is not correct")
                    expected_receiver_id = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'ReceiverID')
                    if file_dictionary['ReceiverID'] != expected_receiver_id:
                        allure.attach(
                            f"Expected receiver id: {expected_receiver_id}\nActual receiver id: {file_dictionary['ReceiverID']}",
                            name='d4ml5a - Sender ID mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Receiver ID in transaction {expected_transaction_id} is not correct")
                    expected_record_count = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'RecordCount')
                    if file_dictionary['RecordCount'] != expected_record_count:
                        allure.attach(
                            f"Expected record count: {expected_record_count}\nActual record count: {file_dictionary['RecordCount']}",
                            name='d4005a - record count mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Record count in transaction {expected_transaction_id} is not correct")
                    expected_transaction_date = ExtractDataContext(
                        template).decide_template_type().extract_from_template(
                        template, 'TransactionDate')
                    if file_dictionary['TransactionDate'] != expected_transaction_date:
                        allure.attach(
                            f"Expected transaction date: {expected_transaction_date}\nActual transaction date: {file_dictionary['TransactionDate']}",
                            name='d4ioo5a - transaction date mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"Transaction date in transaction {expected_transaction_id} is not correct")
                    iso_transaction_timestamp = format_date_to_iso(file_dictionary['TransactionTimestamp'])
                    iso_current_date = get_current_date_iso()
                    if iso_transaction_timestamp != iso_current_date:
                        allure.attach(
                            f"Expected transaction timestamp: {iso_current_date}\nActual transaction timestamp: {iso_transaction_timestamp}",
                            name='d4er05a - transaction timestamp mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"transaction timestamp in transaction {expected_transaction_id} is not correct")
                    expected_downloaded = 'True'
                    if file_dictionary['IsDownloaded'] != expected_downloaded:
                        allure.attach(
                            f"Expected is downloaded: {expected_downloaded}\nActual is downloaded: {file_dictionary['IsDownloaded']}",
                            name='d4tto5a - is downloaded flag mismatch',
                            attachment_type=allure.attachment_type.TEXT
                        )
                        allure.dynamic.tag(f"System 1 Failure")
                        allure.dynamic.label("failure_reason", f"system_1_issue")
                        pytest.fail(f"is downloaded flag in transaction {expected_transaction_id} is not correct")
                    break
            if not found:
                allure.attach(
                    f"Expected transaction ID: {expected_transaction_id}\nNot found among the returned transactions.",
                    name='8b450b - Transaction not found',
                    attachment_type=allure.attachment_type.TEXT
                )
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Transaction {expected_transaction_id} was not found")

    def error(self, response, error_message, template=None):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        error = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'errorMessage')
        if error is None:
            allure.dynamic.tag("System 1 Failure")
            allure.dynamic.label("failure_reason", "system_1_issue")
            pytest.fail("'errorMessage' element was not found in the response")
        if error_message.lower() != '<none>':
            if template is not None:
                error_message = ErrorTextProcessor(error_message, template).process_error_text()
        else:
            error_message = None
        with allure.step(f"Assert error is found"):
            allure.attach(
                f"Expected error message: {error_message}\nActual error message: {error.text}",
                name='568d49 - Check error message',
                attachment_type=allure.attachment_type.TEXT
            )

            if error.text != error_message:
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Expected error message doesn't match actual error message\nExpected: {error_message}\nActual: {error.text}")

    def downloaded(self, template, response):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        file = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'file')
        if file is None:
            allure.dynamic.tag("System 1 Failure")
            allure.dynamic.label("failure_reason", "system_1_issue")
            pytest.fail("'file' element was not found in the response")
        with allure.step(f"Assert downloaded file matches template"):
            xml_file_string=decode_base64_to_xml(file.text)
            template_string = ET.tostring(template, encoding='unicode')
            allure.attach(
                f"Downloaded: {xml_file_string}\nTemplate: {template_string}",
                name='c67011 - Compare template and downloaded file',
                attachment_type=allure.attachment_type.TEXT
            )

            if xml_file_string != template_string:
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Downloaded Transaction doesn't match the template")

    def set_downloaded(self, template, response):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        set_downloaded_result = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'SetTransactionDownloadedResult')
        if set_downloaded_result is None:
            allure.dynamic.tag("System 1 Failure")
            allure.dynamic.label("failure_reason", "system_1_issue")
            pytest.fail("'SetTransactionDownloadedResult' element was not found in the response")
        error_message = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(xml_response_body, 'errorMessage')
        if error_message is None:
            allure.dynamic.tag("System 1 Failure")
            allure.dynamic.label("failure_reason", "system_1_issue")
            pytest.fail("'errorMessage' element was not found in the response")
        with allure.step(f"Assert set downloaded response matches expected"):
            xml_result_string = set_downloaded_result.text
            error_message_text = error_message.text
            allure.attach(
                f"Expected code = 0 & Actual code: {xml_result_string}\n\nExpected error message is empty & actual error message is: {error_message_text}",
                name='c67045 - Check set downloaded code and error message',
                attachment_type=allure.attachment_type.TEXT
            )

            if xml_result_string != '0':
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Set Transaction Downloaded doesn't match the expected code")

            if error_message_text is not None:
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Set Transaction Downloaded error message is not empty")

    def report_generated(self, template, response):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        reconciliation_result = ExtractDataContext(
            xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'GetClaimCountReconciliationResult')
        if reconciliation_result is None:
            allure.dynamic.tag("System 1 Failure")
            allure.dynamic.label("failure_reason", "system_1_issue")
            pytest.fail("'GetClaimCountReconciliationResult' element was not found in the response")
        error_message = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'errorMessage')
        if error_message is None:
            allure.dynamic.tag("System 1 Failure")
            allure.dynamic.label("failure_reason", "system_1_issue")
            pytest.fail("'errorMessage' element was not found in the response")
        upload_count = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'uploadCount')
        download_count = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'downloadCount')
        with allure.step(f"Assert reconciliation response matches expected"):
            xml_result_string = reconciliation_result.text
            error_message_text = error_message.text
            allure.attach(
                f"Expected code = 0 & Actual code: {xml_result_string}\n\nExpected error message is 'Operation is successful' & actual error message is: {error_message_text}",
                name='crrre96 - Check reconciliation code and error message',
                attachment_type=allure.attachment_type.TEXT
            )

            if xml_result_string != '0':
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Reconciliation doesn't match the expected code")

            if error_message_text != 'Operation is successful':
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Reconciliation error message doesn't match the expected: Operation is successful")

            if upload_count is None:
                allure.dynamic.tag("System 1 Failure")
                allure.dynamic.label("failure_reason", "system_1_issue")
                pytest.fail("'uploadCount' element was not found in the response")

            if download_count is None:
                allure.dynamic.tag("System 1 Failure")
                allure.dynamic.label("failure_reason", "system_1_issue")
                pytest.fail("'downloadCount' element was not found in the response")

            if not upload_count.text.isnumeric():
                allure.attach(
                    f"upload_count value: '{upload_count.text}'\nExpected: a numeric value",
                    name='c63496 - upload_count not numeric',
                    attachment_type=allure.attachment_type.TEXT
                )
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"upload_count value '{upload_count.text}' is not numeric")

            if not download_count.text.isnumeric():
                allure.attach(
                    f"download_count value: '{download_count.text}'\nExpected: a numeric value",
                    name='c6ggfr6 - download_count not numeric',
                    attachment_type=allure.attachment_type.TEXT
                )
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"download_count value '{download_count.text}' is not numeric")

    def _parse_file_filters(self, expected):
        filters = {}
        for pair in expected.split(';'):
            pair = pair.strip()
            if not pair or '=' not in pair:
                continue
            key, value = pair.split('=', 1)
            key, value = key.strip(), value.strip()
            if key and value:
                filters[key] = value
        return filters

    def file_found(self, response, expected, template):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        person_insurance_details = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'PersonInsuranceDetails')
        if person_insurance_details is None:
            allure.dynamic.tag("System 1 Failure")
            allure.dynamic.label("failure_reason", "system_1_issue")
            pytest.fail("'PersonInsuranceDetails' element was not found in the response")
        xml_files = ET.fromstring(person_insurance_details.text)
        if template is not None:
            expected = ErrorTextProcessor(expected, template).process_error_text()
        filters = self._parse_file_filters(expected)
        with allure.step(f"Assert file is found with attributes: {filters}"):
            allure.attach(
                f"Expected attributes: {filters}",
                name='f41a3b - Check file found',
                attachment_type=allure.attachment_type.TEXT
            )
            for file in xml_files.findall('File'):
                file_attrs = file.attrib
                if all(file_attrs.get(k) == v for k, v in filters.items()):
                    allure.attach(
                        f"Matching file attributes: {file_attrs}",
                        name='f41a3b - Matching file found',
                        attachment_type=allure.attachment_type.TEXT
                    )
                    return
            allure.dynamic.tag("System 1 Failure")
            allure.dynamic.label("failure_reason", "system_1_issue")
            pytest.fail(f"No file matching {filters} was found in PersonInsuranceDetails")

    def file_not_found(self, response, expected, template):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        person_insurance_details = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'PersonInsuranceDetails')
        if person_insurance_details is None:
            allure.dynamic.tag("System 1 Failure")
            allure.dynamic.label("failure_reason", "system_1_issue")
            pytest.fail("'PersonInsuranceDetails' element was not found in the response")
        xml_files = ET.fromstring(person_insurance_details.text)
        if template is not None:
            expected = ErrorTextProcessor(expected, template).process_error_text()
        filters = self._parse_file_filters(expected)
        with allure.step(f"Assert no file is found with attributes: {filters}"):
            allure.attach(
                f"Expected absent attributes: {filters}",
                name='f17d8e - Check file not found',
                attachment_type=allure.attachment_type.TEXT
            )
            for file in xml_files.findall('File'):
                file_attrs = file.attrib
                if all(file_attrs.get(k) == v for k, v in filters.items()):
                    allure.attach(
                        f"Unexpected matching file attributes: {file_attrs}",
                        name='f17d8e - Unexpected file found',
                        attachment_type=allure.attachment_type.TEXT
                    )
                    allure.dynamic.tag("System 1 Failure")
                    allure.dynamic.label("failure_reason", "system_1_issue")
                    pytest.fail(f"File matching {filters} was found in PersonInsuranceDetails but was not expected")

    def _custom_error_code(self, response, error_code):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        error_code_element = ExtractDataContext(
            xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, self.request.title().replace(' ','') + 'Result')
        if error_code_element is None:
            allure.dynamic.tag("System 1 Failure")
            allure.dynamic.label("failure_reason", "system_1_issue")
            pytest.fail(f"'{self.request.title().replace(' ', '')}Result' element was not found in the response")
        with allure.step(f"Assert Code is correct"):
            actual_error_code = error_code_element.text
            allure.attach(
                f"Actual code: {actual_error_code}\n\nExpected error code: {error_code}",
                name='c67048 - Check error code',
                attachment_type=allure.attachment_type.TEXT
            )

            if actual_error_code != error_code :
                allure.dynamic.tag(f"System 1 Failure")
                allure.dynamic.label("failure_reason", f"system_1_issue")
                pytest.fail(f"Error code is incorrect")



class DefaultTransactionsStrategy(CustomAsserter):

    def __init__(self, request:str):
        super().__init__(request)

    def found(self, response, prerequisite):
        raise Exception("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")

    def not_found(self, response, prerequisite):
        raise Exception("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")

    def determine(self, template, response, prerequisite, expected):
        raise Exception("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")

    def error(self, response, error_message):
        raise Exception("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")

    def downloaded(self, template, response):
        raise Exception("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")

    def set_downloaded(self, template, response):
        raise Exception("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")

    def report_generated(self, template, response):
        raise Exception("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")

    def file_found(self, response, expected, template):
        raise Exception("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")

    def file_not_found(self, response, expected, template):
        raise Exception("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")


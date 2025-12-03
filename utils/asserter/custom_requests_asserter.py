from abc import ABC

import allure
import pytest
import xml.etree.ElementTree as ET
from utils.request_mapper.request_mapper import SearchTransactions
from utils.template_generator.extract_data_strategy.extract_data_context import ExtractDataContext


class CustomAsserterContext:

    def __init__(self, request:str):
        self.request = request

    def get_request_strategy(self):
        if self.request.lower().strip() == 'search transactions':
            return XMLSearchTransactionsStrategy()
        else:
            return DefaultTransactionsStrategy()



class CustomAsserter(ABC):

    def found(self, response, prerequisite):
        pass

    def not_found(self, response, prerequisite):
        pass

    def determine(self, response, prerequisite, expected):
        pass

class XMLSearchTransactionsStrategy(CustomAsserter):

    def determine(self, response, prerequisite, expected):
        if expected.lower().strip() in ['retrieved', 'found', 'request found', 'request is found', 'request retrieved', 'request is retrieved', 'transaction found', 'transaction is found', 'transaction retrieved', 'transaction is retrieved']:
            self.found(response, prerequisite)
        elif expected.lower().strip() in ['not retrieved', 'not found', 'request not found', 'request is not found', 'request not retrieved', 'request is not retrieved', 'transaction  not found', 'transaction is  not found', 'transaction  not retrieved', 'transaction is  not retrieved']:
            self.not_found(response, prerequisite)
        else:
            pytest.fail(f"Unexpected: {expected}.")

    def not_found(self, response, prerequisite):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'foundTransactions')
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
                    name='Check against transaction',
                    attachment_type=allure.attachment_type.TEXT
                )
                if file_dictionary['FileID'] == expected_transaction_id:
                    found = True
                    break
            assert not found, f"Transaction {expected_transaction_id} was found"

    def found(self, response, prerequisite):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(xml_response_body, 'foundTransactions')
        xml_files = ET.fromstring(files.text)
        expected_transaction_id = ExtractDataContext(ET.fromstring(prerequisite['content'])).decide_template_type().extract_from_template(
            ET.fromstring(prerequisite['content']), 'TransactionID')
        found = False
        with allure.step(f"Assert transaction {expected_transaction_id} is found"):
            for file in xml_files.findall('File'):
                file_dictionary = file.attrib
                allure.attach(
                    f"Actual transaction {file_dictionary['FileID']}",
                    name='Check against transaction',
                    attachment_type=allure.attachment_type.TEXT
                )
                if file_dictionary['FileID'] == expected_transaction_id:
                    found = True
                    allure.attach(
                        f"Actual transaction {file_dictionary['FileID']}",
                        name='Transaction FileID was found',
                        attachment_type=allure.attachment_type.TEXT
                    )
                    expected_file_name = ExtractDataContext(
                        ET.fromstring(prerequisite['request_xml'])).decide_template_type().extract_from_template(
                        ET.fromstring(prerequisite['request_xml']), 'fileName')
                    assert file_dictionary['FileName'] == expected_file_name
                    break
            assert found, f"Transaction {expected_transaction_id} was not found"



class DefaultTransactionsStrategy(CustomAsserter):

    def found(self, response, prerequisite):
        pytest.fail("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")

    def not_found(self, response, prerequisite):
        pytest.fail("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")

    def determine(self, response, prerequisite, expected):
        pytest.fail("Invalid Transaction Strategy; This transaction doesn't qualify for assertion run")
from abc import ABC

import allure
import pytest
import xml.etree.ElementTree as ET
from utils.request_mapper.request_mapper import SearchTransactions
from utils.template_generator.extract_data_strategy.extract_data_context import ExtractDataContext
from utils.template_generator.requests_name_enums import RequestsName
from utils.xml_utils import decode_base64_to_xml

requests_qualified_for_custom_asserter = [RequestsName.search_transactions.value, RequestsName.get_new_prior_authorization.value,
                                          RequestsName.get_new_transactions.value, RequestsName.download_transaction.value]

class CustomAsserterContext:

    def __init__(self, request:str):
        self.request = request

    def get_request_strategy(self):
        if self.request.lower().strip() in requests_qualified_for_custom_asserter:
            return XMLSearchTransactionsStrategy()
        else:
            return DefaultTransactionsStrategy()



class CustomAsserter(ABC):

    def found(self, response, prerequisite):
        pass

    def not_found(self, response, prerequisite):
        pass

    def error(self, response, error_message):
        pass

    def downloaded(self, template, response):
        pass

    def determine(self, template, response, prerequisite, expected):
        pass

class XMLSearchTransactionsStrategy(CustomAsserter):

    def determine(self, template, response, prerequisite, expected):
        if expected.lower().strip() in ['retrieved', 'found', 'request found', 'request is found', 'request retrieved', 'request is retrieved', 'transaction found', 'transaction is found', 'transaction retrieved', 'transaction is retrieved']:
            self.found(response, prerequisite)
        elif expected.lower().strip() in ['not retrieved', 'not found', 'request not found', 'request is not found', 'request not retrieved', 'request is not retrieved', 'transaction  not found', 'transaction is  not found', 'transaction  not retrieved', 'transaction is  not retrieved']:
            self.not_found(response, prerequisite)
        elif expected.lower().strip().startswith('error'):
            try:
                error_message = expected.split('-',1)[1].strip()
                self.error(response, error_message)
            except IndexError:
                raise Exception("Issue with error message. Make sure to add expected error message in the format Error - {error_message}")
        elif expected.lower().strip() in ['downloaded', 'request is downloaded', 'request downloaded']:
            self.downloaded(template, response)
        else:
            raise Exception(f"Unexpected: {expected}.")

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
        try:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'foundTransactions')
            xml_files = ET.fromstring(files.text)
        except AttributeError:
            files = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
                xml_response_body, 'xmlTransactions')
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

    def error(self, response, error_message):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        error = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'errorMessage')
        with allure.step(f"Assert error is found"):
            allure.attach(
                f"Expected error message: {error_message}\nActual error message: {error.text}",
                name='Check error message',
                attachment_type=allure.attachment_type.TEXT
            )
            assert error.text == error_message, f"Expected error message doesn't match actual error message\nExpected: {error_message}\nActual: {error.text}"

    def downloaded(self, template, response):
        response_body = response['content']
        xml_response_body = ET.fromstring(response_body)
        file = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'file')
        with allure.step(f"Assert downloaded file matches template"):
            xml_file_string=decode_base64_to_xml(file.text)
            template_string= ET.tostring(template).decode('utf-8')
            allure.attach(
                f"Downloaded: {xml_file_string}\nTemplate: {template_string}",
                name='Compare template and downloaded file',
                attachment_type=allure.attachment_type.TEXT
            )
            assert xml_file_string == template_string, f"Downloaded Transaction doesn't match the template"



class DefaultTransactionsStrategy(CustomAsserter):

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
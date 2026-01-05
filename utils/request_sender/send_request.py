import base64
import json
import re
from abc import ABC
import xml.etree.ElementTree as ET

import allure
import pytest

from functions.custom_functions import generate_filename, get_random_payer_login, zip_file
from utils.api_client import APIClient
from utils.template_generator.requests_name_enums import RequestsName
from utils.template_generator.template_generator import GetRequestTemplate


def encode_xml(template):
    string_xml = ET.tostring(template).decode("utf-8")
    bytes_xml = string_xml.encode("utf-8")
    base64_xml = base64.b64encode(bytes_xml)
    base64_string_xml = base64_xml.decode("utf-8")
    return base64_string_xml

def encode_zipped(zip_file):
    encoded_data = base64.b64encode(zip_file)
    return encoded_data.decode("utf-8")

class SendRequest(ABC):

    def __init__(self, template, variables):
        self.template = template
        if variables is None:
            self.variables = ""
        else:
            self.variables = variables

    with open("resources/system_defaults.json", "r") as defaults_file:
        defaults = json.load(defaults_file)

    def send_request_old_system(self):
        pass

    def send_request_new_system(self):
        pass

class SendPersonRegister(SendRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_upload_transaction.value,live_data=self.variables)
            if live_data is not None and live_data != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {live_data}")
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template).decode("utf-8")).group(1)
        with allure.step(f"Send Person Register Request - Old System"):
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(template).decode("utf-8"),
                soap_action=f'{namespace_value}UploadTransaction'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}UploadTransaction",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()


class SendPriorRequest(SendRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            if live_data is not None and live_data != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {live_data}")
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template).decode("utf-8")).group(1)
        with allure.step(f"Send Prior Request - Old System"):
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(template).decode("utf-8"),
                soap_action=f'{namespace_value}UploadTransaction'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}UploadTransaction",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()

class SendPriorRequestZipped(SendRequest):

    def send_request_old_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            if live_data is not None and live_data != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {live_data}")
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template).decode("utf-8")).group(1)
        with allure.step(f"Send Prior Request - Old System"):
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(template).decode("utf-8"),
                soap_action=f'{namespace_value}UploadTransaction'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}UploadTransaction",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()


class SendPriorAuthorization(SendRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior authorization"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.prior_authorization_upload_transaction.value, live_data=self.variables)
            if live_data is not None and live_data != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {live_data}")
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template).decode("utf-8")).group(1)
        with allure.step(f"Send Prior Authorization - Old System"):
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(template).decode("utf-8"),
                soap_action=f'{namespace_value}UploadTransaction'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}UploadTransaction",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()


class SendClaimSubmission(SendRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            if live_data is not None and live_data != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {live_data}")
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template).decode("utf-8")).group(1)
        with allure.step(f"Send Claim Submission - Old System"):
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(template).decode("utf-8"),
                soap_action=f'{namespace_value}UploadTransaction'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}UploadTransaction",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()

class SendClaimReSubmission(SendRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim resubmission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            if live_data is not None and live_data != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {live_data}")
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template).decode("utf-8")).group(1)
        with allure.step(f"Send Claim Resubmission - Old System"):
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(template).decode("utf-8"),
                soap_action=f'{namespace_value}UploadTransaction'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}UploadTransaction",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()

class SendRemittanceAdvice(SendRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for remittance advice"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.remittance_advice_upload_transaction.value, live_data=self.variables)
            if live_data is not None and live_data != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {live_data}")
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template).decode("utf-8")).group(1)
        with allure.step(f"Send Remittance Advice - Old System"):
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(template).decode("utf-8"),
                soap_action=f'{namespace_value}UploadTransaction'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}UploadTransaction",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()


class SendCostSubmission(SendRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for cost submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.cost_submission_upload_transaction.value, live_data=self.variables)
            if live_data is not None and live_data != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {live_data}")
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template).decode("utf-8")).group(1)
        with allure.step(f"Send Cost Submission - Old System"):
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(template).decode("utf-8"),
                soap_action=f'{namespace_value}UploadTransaction'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}UploadTransaction",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()


class SendSearchTransactions(SendRequest):

    def send_request_new_system(self):
        return self.send_request_old_system()

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template).decode("utf-8")).group(1)
        with allure.step(f"Send Search Transactions - Old System"):
            if self.variables is not None and self.variables != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {self.variables}")
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(self.template).decode("utf-8"),
                soap_action=f'{namespace_value}SearchTransactions'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}SearchTransactions",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

class SendGetNewPriorAuthorizationTransactions(SendRequest):

    def send_request_new_system(self):
        return self.send_request_old_system()

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template).decode("utf-8")).group(1)
        with allure.step(f"Send Get New Prior Authorization Transactions - Old System"):
            if self.variables is not None and self.variables != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {self.variables}")
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(self.template).decode("utf-8"),
                soap_action=f'{namespace_value}GetNewPriorAuthorizationTransactions'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}GetNewPriorAuthorizationTransactions",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

class SendGetNewTransaction(SendRequest):

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template).decode("utf-8")).group(1)
        with allure.step(f"Send Get Transaction - Old System"):
            if self.variables is not None and self.variables != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {self.variables}")
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(self.template).decode("utf-8"),
                soap_action=f'{namespace_value}GetNewTransactions'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}GetNewTransactions",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()

class SendDownloadTransaction(SendRequest):

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template).decode("utf-8")).group(1)
        with allure.step(f"Send Download Transaction - Old System"):
            if self.variables is not None and self.variables != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {self.variables}")
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(self.template).decode("utf-8"),
                soap_action=f'{namespace_value}DownloadTransactionFile'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}DownloadTransactionFile",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()

class SendSetTransactionDownloaded(SendRequest):

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template).decode("utf-8")).group(1)
        with allure.step(f"Send Set Transaction Downloaded - Old System"):
            if self.variables is not None and self.variables != '':
                pytest.fail(f"live data is not all consumed; the following are still unused: {self.variables}")
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('url'),
                xml_body=ET.tostring(self.template).decode("utf-8"),
                soap_action=f'{namespace_value}SetTransactionDownloaded'
            )
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('url')}\nAction: {namespace_value}SetTransactionDownloaded",
                name="Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template).decode("utf-8"),
                name="Request",
                attachment_type=allure.attachment_type.XML,
            )
            allure.attach(
                response['content'],
                name="Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        return self.send_request_old_system()
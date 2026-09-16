import base64
import json
import re
from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET
import os

import allure
import pytest

from functions.custom_functions import generate_filename, get_random_payer_login, zip_file,zip_files
from utils.api_client import APIClient
from utils.request_sender.soap_action_enums import SoapAction
from utils.template_generator.requests_name_enums import RequestsName
from utils.template_generator.template_generator import GetRequestTemplate
from utils.env_vars import EnvVar


def _format_unused_live_data(live_data_str):
    if not live_data_str:
        return ""
    lines = []
    for entry in live_data_str.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if "=" in entry:
            key, value = entry.split("=", 1)
            key, value = key.strip(), value.strip()
            key = key.replace("<", "&lt;").replace(">", "&gt;")
            if not key:
                lines.append(f"  - (empty tag name) = '{value}'  ← stray '={value}' in test data")
            else:
                lines.append(f"  - '{key}' = '{value}'")
        else:
            lines.append(f"  - (no '=' found): '{entry}'")
    return "\n".join(lines)


def encode_xml(template):
    string_xml = ET.tostring(template, encoding="unicode")
    bytes_xml = string_xml.encode("utf-8")
    base64_xml = base64.b64encode(bytes_xml)
    base64_string_xml = base64_xml.decode("utf-8")
    return base64_string_xml

def encode_zipped(zip_file):
    encoded_data = base64.b64encode(zip_file)
    return encoded_data.decode("utf-8")

def change_login(template, namespace_value, payer_or_provider:str):
    """
    Change the login of the template to a specific login if the USE_SPECIFIC_LOGIN environment variable is set to true.
    :param template: The template to change the login of.
    :param namespace_value: The namespace value of the template.
    :param payer_or_provider: The payer or provider to change the login of.
    :return: The template with the changed login.
    """
    if os.environ.get(EnvVar.USE_SPECIFIC_LOGIN) == "true":
        if payer_or_provider == "payer":
            template.find(f".//{{{namespace_value}}}login").text = os.environ.get(EnvVar.PAYER_VALUE)
        elif payer_or_provider == "provider":
            template.find(f".//{{{namespace_value}}}login").text = os.environ.get(EnvVar.PROVIDER_VALUE)
        elif payer_or_provider == "tpa":
            template.find(f".//{{{namespace_value}}}login").text = os.environ.get(EnvVar.TPA_VALUE)
        elif payer_or_provider == "pharmacy":
            template.find(f".//{{{namespace_value}}}login").text = os.environ.get(EnvVar.PHARMACY_VALUE)
    return template

class SendRequest(ABC):

    def __init__(self, template, variables):
        self.template = template
        if variables is None:
            self.variables = ""
        else:
            self.variables = variables

    with open("resources/system_defaults.json", "r") as defaults_file:
        defaults = json.load(defaults_file)

    def get_new_system_url(self):
        env = os.environ.get(EnvVar.NEW_TARGET_ENVIRONMENT)
        if env and env.lower() == "dev":
            return self.defaults.get('new_system').get('dev_url')
        if env and env.lower() == "uat":
            return self.defaults.get('new_system').get('uat_url')
        if env and env.lower() == "stage":
            return self.defaults.get('new_system').get('stage_url')
        return self.defaults.get('new_system').get('url')

    def get_new_system_claim_checker_url(self):
        env = os.environ.get(EnvVar.NEW_TARGET_ENVIRONMENT)
        if env and env.lower() == "dev":
            return self.defaults.get('claim_checker').get('new_system').get('dev_url')
        if env and env.lower() == "uat":
            return self.defaults.get('claim_checker').get('new_system').get('uat_url')
        if env and env.lower() == "stage":
            return self.defaults.get('claim_checker').get('new_system').get('stage_url')
        return self.defaults.get('claim_checker').get('new_system').get('url')

    @abstractmethod
    def send_request_old_system(self):
        pass

    @abstractmethod
    def send_request_new_system(self):
        pass
    

class SendDualSystemRequest(SendRequest):
    
    @abstractmethod
    def send_request_dual_systems(self):
        pass

    @abstractmethod
    def send_request_dual_old_system(self):
        pass
    


class SendPersonRegister(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="1dac54 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Person Register Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="084971 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="3c4909 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Person Register Request - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="8d6142 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]


class SendPersonRegisterProvider(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_provider_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_provider_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="1dac54 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_provider_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Person Register Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="084971 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_provider_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="3c4909 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Person Register Request - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="8d6142 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]


class SendPersonRegisterTPA(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_tpa_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_tpa_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="1dac54 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_tpa_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Person Register Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="084971 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for person register"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_tpa_upload_transaction.value,live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Person Register Request - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="3c4909 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Person Register Request - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="8d6142 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]


class SendPriorRequest(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="9b81e2 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Prior Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="fecb4c - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="41d6bc - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Prior Request - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="6c10ef - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]

class SendPriorRequestZipped(SendDualSystemRequest):

    def send_request_old_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="a47436 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Prior Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="371d31 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="1d2da7 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Prior Request - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="f27bc8 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]

class SendPriorRequestMultipleXmls(SendDualSystemRequest):
    
    def send_request_old_system(self):
        zipped_template = zip_files(self.template, self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        zipped_template = zip_files(self.template, self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="abd4b6 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        zipped_template = zip_files(self.template, self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Prior Request - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="4a4457 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        zipped_template = zip_files(self.template, self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for prior request"):
            template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Request - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="f7e50d - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Prior Request - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="321876 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]

class SendPriorAuthorization(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior authorization"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.prior_authorization_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Authorization - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior authorization"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.prior_authorization_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Authorization - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="601f72 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior authorization"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.prior_authorization_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Authorization - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Prior Authorization - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="825327 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior authorization"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.prior_authorization_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Authorization - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="c0eb78 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Prior Authorization - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="b5b47f - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]

class SendPriorAuthorizationTPA(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior authorization"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.prior_authorization_tpa_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Authorization - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior authorization"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.prior_authorization_tpa_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Authorization - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="601f72 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior authorization"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.prior_authorization_tpa_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Authorization - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Prior Authorization - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="825327 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for prior authorization"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.prior_authorization_tpa_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Prior Authorization - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="c0eb78 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Prior Authorization - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="b5b47f - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]

class SendClaimSubmission(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Submission - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Submission - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="df2a7e - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Submission - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Claim Submission - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="c0d994 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Submission - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="5a5e00 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Claim Submission - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="2e8cc6 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]

class SendClaimChecker(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim checker"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Checker - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url = self.defaults.get('claim_checker').get('old_system').get('production_url')
            else:
                url = self.defaults.get('claim_checker').get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim checker"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Checker - New System"):
            url = self.get_new_system_claim_checker_url()
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="df2a7e - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim checker"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Checker - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url = self.defaults.get('claim_checker').get('old_system').get('production_url')
            else:
                url = self.defaults.get('claim_checker').get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Claim Checker - New System"):
            new_url = self.get_new_system_claim_checker_url()
            allure.attach(
                f"URL: {new_url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="c0d994 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=new_url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim checker"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Checker - Old System Production"):
            url = self.defaults.get('claim_checker').get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="5a5e00 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Claim Checker - Old System PTE"):
            url = self.defaults.get('claim_checker').get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="2e8cc6 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]

class SendClaimCheckerZipped(SendDualSystemRequest):

    def send_request_old_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for claim checker"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Checker Zipped - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url = self.defaults.get('claim_checker').get('old_system').get('production_url')
            else:
                url = self.defaults.get('claim_checker').get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for claim checker"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Checker Zipped - New System"):
            url = self.get_new_system_claim_checker_url()
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="df2a7e - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for claim checker"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Checker Zipped - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url = self.defaults.get('claim_checker').get('old_system').get('production_url')
            else:
                url = self.defaults.get('claim_checker').get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Claim Checker Zipped - New System"):
            new_url = self.get_new_system_claim_checker_url()
            allure.attach(
                f"URL: {new_url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="c0d994 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=new_url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for claim checker"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Checker Zipped - Old System Production"):
            url = self.defaults.get('claim_checker').get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="5a5e00 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Claim Checker Zipped - Old System PTE"):
            url = self.defaults.get('claim_checker').get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="2e8cc6 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]

class SendClaimSubmissionZipped(SendDualSystemRequest):

    def send_request_old_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for claim submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Submission Zipped - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url = self.defaults.get('old_system').get('production_url')
            else:
                url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for claim submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Submission Zipped - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="df2a7e - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for claim submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Submission Zipped - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url = self.defaults.get('old_system').get('production_url')
            else:
                url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Claim Submission Zipped - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="c0d994 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for claim submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Submission Zipped - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="5a5e00 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Claim Submission Zipped - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="2e8cc6 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]


class SendClaimReSubmission(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim resubmission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Resubmission - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim resubmission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Resubmission - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="f9c32d - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim resubmission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Resubmission - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Claim Resubmission - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="ae2a40 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for claim resubmission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Claim Resubmission - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="e5c02a - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Claim Resubmission - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="ac43ea - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]

class SendRemittanceAdvice(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for remittance advice"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.remittance_advice_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Remittance Advice - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for remittance advice"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.remittance_advice_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Remittance Advice - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="a6a12d - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for remittance advice"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.remittance_advice_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Remittance Advice - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Remittance Advice - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="f94a22 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for remittance advice"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.remittance_advice_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Remittance Advice - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="117cdc - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Remittance Advice - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="ce7fdf - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]


class SendPayForQuality(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for pay for quality"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.pay_for_quality_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Pay For Quality - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="3b7e91 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for pay for quality"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.pay_for_quality_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Pay For Quality - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="c2f4a8 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for pay for quality"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.pay_for_quality_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Pay For Quality - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="3b7e91 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Pay For Quality - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="c2f4a8 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for pay for quality"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.pay_for_quality_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "payer")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Pay For Quality - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="8d1f3c - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Pay For Quality - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="5a9b2e - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]


class SendRemittanceAdviceTPA(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for remittance advice"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.remittance_advice_tpa_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Remittance Advice - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for remittance advice"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.remittance_advice_tpa_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Remittance Advice - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="a6a12d - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for remittance advice"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.remittance_advice_tpa_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Remittance Advice - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Remittance Advice - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="f94a22 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for remittance advice"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.remittance_advice_tpa_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "tpa")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Remittance Advice - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="117cdc - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Remittance Advice - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="ce7fdf - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]

class SendCostSubmission(SendDualSystemRequest):

    def send_request_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for cost submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.cost_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Cost Submission - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for cost submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.cost_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Cost Submission - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="5dbe57 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for cost submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.cost_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Cost Submission - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url=self.defaults.get('old_system').get('production_url')
            else:
                url=self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Cost Submission - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="ad22c9 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        encoded_template = encode_xml(self.template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};" + self.variables
        with allure.step("Get upload transaction request for cost submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.cost_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Cost Submission - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="a387b7 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Cost Submission - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="66108b - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]


class SendCostSubmissionZipped(SendDualSystemRequest):

    def send_request_old_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for cost submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.cost_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Cost Submission Zipped - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url = self.defaults.get('old_system').get('production_url')
            else:
                url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for cost submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.cost_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Cost Submission Zipped - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="5dbe57 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_dual_systems(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for cost submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.cost_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Cost Submission Zipped - Old System"):
            if os.environ.get(EnvVar.TARGET_ENVIRONMENT) == "production":
                url = self.defaults.get('old_system').get('production_url')
            else:
                url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_old = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_old['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Cost Submission Zipped - New System"):
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="ad22c9 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_new = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_new['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_old, response_new]

    def send_request_dual_old_system(self):
        zipped_template = zip_file(self.template)
        encoded_template = encode_zipped(zipped_template)
        self.variables = f"Body.UploadTransaction.fileContent={encoded_template};Body.UploadTransaction.fileName={generate_filename(extension='zip')};" + self.variables
        with allure.step("Get upload transaction request for cost submission"):
            template, variables, live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.cost_submission_upload_transaction.value, live_data=self.variables)
            namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(template, encoding="unicode")).group(1)
            template = change_login(template, namespace_value, "provider")
            if live_data is not None and live_data != '':
                raise Exception(f"Live data not fully consumed. The following entries could not be matched to any field in the template:\n{_format_unused_live_data(live_data)}")
        with allure.step(f"Send Cost Submission Zipped - Old System Production"):
            url = self.defaults.get('old_system').get('production_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="a387b7 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_prod = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_prod['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        with allure.step(f"Send Cost Submission Zipped - Old System PTE"):
            url = self.defaults.get('old_system').get('pte_url')
            allure.attach(
                f"URL: {url}\nAction: {namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}",
                name="66108b - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response_pte = APIClient().send_request(
                url=url,
                xml_body=ET.tostring(template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.UPLOAD_TRANSACTION.value}'
            )
            allure.attach(
                response_pte['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
        return [response_prod, response_pte]


class SendSearchTransactions(SendRequest):

    def send_request_new_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Search Transactions - New System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.SEARCH_TRANSACTIONS.value}",
                name="8c4001 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.SEARCH_TRANSACTIONS.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Search Transactions - Old System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('pte_url')}\nAction: {namespace_value}{SoapAction.SEARCH_TRANSACTIONS.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('pte_url'),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.SEARCH_TRANSACTIONS.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

class SendClaimCountConciliation(SendRequest):

    def send_request_new_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Count Claim Reconciliation - New System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.GET_CLAIM_COUNT_RECONCILIATION.value}",
                name="8c4001 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.GET_CLAIM_COUNT_RECONCILIATION.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Count Claim Reconciliation - Old System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('pte_url')}\nAction: {namespace_value}{SoapAction.GET_CLAIM_COUNT_RECONCILIATION.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('pte_url'),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.GET_CLAIM_COUNT_RECONCILIATION.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

class SendGetPersonInsuranceHistory(SendRequest):

    def send_request_new_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Get Person Insurance History - New System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.GET_PERSON_INSURANCE_HISTORY.value}",
                name="8c9901 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98excb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.GET_PERSON_INSURANCE_HISTORY.value}'
            )
            allure.attach(
                response['content'],
                name="a43wd4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Get Person Insurance History - Old System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('pte_url')}\nAction: {namespace_value}{SoapAction.GET_PERSON_INSURANCE_HISTORY.value}",
                name="511ss8 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98345b - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('pte_url'),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.GET_PERSON_INSURANCE_HISTORY.value}'
            )
            allure.attach(
                response['content'],
                name="33fgt9 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

class SendGetNewPriorAuthorizationTransactions(SendRequest):

    def send_request_new_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Get New Prior Authorization Transactions - New System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.GET_NEW_PRIOR_AUTHORIZATION_TRANSACTIONS.value}",
                name="9b425b - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.GET_NEW_PRIOR_AUTHORIZATION_TRANSACTIONS.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Get New Prior Authorization Transactions - Old System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('pte_url')}\nAction: {namespace_value}{SoapAction.GET_NEW_PRIOR_AUTHORIZATION_TRANSACTIONS.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('pte_url'),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.GET_NEW_PRIOR_AUTHORIZATION_TRANSACTIONS.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

class SendGetNewTransaction(SendRequest):

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Get Transaction - Old System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('pte_url')}\nAction: {namespace_value}{SoapAction.GET_NEW_TRANSACTIONS.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('pte_url'),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.GET_NEW_TRANSACTIONS.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Get Transaction - New System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.GET_NEW_TRANSACTIONS.value}",
                name="b1632b - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.GET_NEW_TRANSACTIONS.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

class SendDownloadTransaction(SendRequest):

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Download Transaction - Old System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('pte_url')}\nAction: {namespace_value}{SoapAction.DOWNLOAD_TRANSACTION_FILE.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('pte_url'),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.DOWNLOAD_TRANSACTION_FILE.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Download Transaction - New System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.DOWNLOAD_TRANSACTION_FILE.value}",
                name="8c9a40 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.DOWNLOAD_TRANSACTION_FILE.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

class SendSetTransactionDownloaded(SendRequest):

    def send_request_old_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Set Transaction Downloaded - Old System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.defaults.get('old_system').get('pte_url')}\nAction: {namespace_value}{SoapAction.SET_TRANSACTION_DOWNLOADED.value}",
                name="502a68 - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.defaults.get('old_system').get('pte_url'),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.SET_TRANSACTION_DOWNLOADED.value}'
            )
            allure.attach(
                response['content'],
                name="33a829 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response

    def send_request_new_system(self):
        namespace_value = re.search(r'xmlns:ns1="([^"]+)"', ET.tostring(self.template, encoding="unicode")).group(1)
        with allure.step(f"Send Set Transaction Downloaded - New System"):
            if self.variables is not None and self.variables != '':
                raise Exception(f"Live data not fully consumed. This request type does not accept live data, but the following was provided:\n{_format_unused_live_data(self.variables)}")
            allure.attach(
                f"URL: {self.get_new_system_url()}\nAction: {namespace_value}{SoapAction.SET_TRANSACTION_DOWNLOADED.value}",
                name="43a0fd - Request URL and action",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                ET.tostring(self.template, encoding="unicode"),
                name="98efcb - Request",
                attachment_type=allure.attachment_type.XML,
            )
            response = APIClient().send_request(
                url=self.get_new_system_url(),
                xml_body=ET.tostring(self.template, encoding="unicode"),
                soap_action=f'{namespace_value}{SoapAction.SET_TRANSACTION_DOWNLOADED.value}'
            )
            allure.attach(
                response['content'],
                name="a4b5d4 - Response",
                attachment_type=allure.attachment_type.XML,
            )
            return response
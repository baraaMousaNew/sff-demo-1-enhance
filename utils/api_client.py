"""
API Client - Handles HTTP requests to SOAP APIs
"""

import requests
from datetime import datetime

class APIClient:
    def __init__(self):
        self.default_headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '',  # Will be set per request
            'User-Agent': 'Python-SOAP-Client/1.0'
        }

    def send_request(self, url, xml_body, soap_action=None, timeout=30, debug=False):
        """
        Send SOAP request and return response details

        Args:
            url (str): API endpoint URL
            xml_body (str): XML/SOAP body content
            soap_action (str): SOAPAction header value for this specific request
            timeout (int): Request timeout in seconds
            debug (bool): Print request details for debugging

        Returns:
            dict: Response details including status, content, timing
        """
        start_time = datetime.now()

        # Use provided SOAPAction or default
        headers = self.default_headers.copy()
        if soap_action:
            # Auto-add quotes if not present, but don't double-quote
            if not (soap_action.startswith('"') and soap_action.endswith('"')):
                # headers['SOAPAction'] = f'"{soap_action}"'
                headers['SOAPAction'] = f'{soap_action}'
            else:
                headers['SOAPAction'] = soap_action
        elif not headers['SOAPAction']:
            # Set default if none provided
            headers['SOAPAction'] = '"https://www.shafafiya.org/v2/UploadTransaction"'

        try:
            if debug:
                print("=== REQUEST DEBUG ===")
                print(f"URL: {url}")
                print(f"Headers: {headers}")
                print(f"Body: {xml_body[:500]}..." if len(xml_body) > 500 else f"Body: {xml_body}")
                print("=== END DEBUG ===")

            response = requests.post(
                url=url,
                data=xml_body,
                headers=headers,
                timeout=timeout
            )

            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds() * 1000

            return {
                'status_code': response.status_code,
                'content': response.text,
                'response_time': response_time,
                'timestamp': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'success': response.status_code == 200,
                'request_headers': dict(headers),
                'response_headers': dict(response.headers),
                'request_xml': xml_body  # Add the final XML that was sent
            }

        except requests.exceptions.Timeout:
            raise Exception(f"Request timeout after {timeout} seconds")
        except requests.exceptions.ConnectionError:
            raise Exception("Connection error - check URL and network")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")
"""
XML Utilities - XML formatting and Base64 encoding/decoding functions
"""

import xml.dom.minidom
import base64
import re

def format_xml(xml_string):
    """
    Format XML string with proper indentation

    Args:
        xml_string (str): Raw XML string

    Returns:
        str: Formatted XML string or None if invalid
    """
    try:
        dom = xml.dom.minidom.parseString(xml_string)
        formatted = dom.toprettyxml(indent="  ")
        # Remove empty lines and XML declaration duplicates
        lines = [line for line in formatted.split('\n') if line.strip()]
        return '\n'.join(lines)

    except Exception:
        return None

def encode_xml_to_base64(xml_string):
    """
    Encode XML string to Base64

    Args:
        xml_string (str): XML content to encode

    Returns:
        str: Base64 encoded string
    """
    return base64.b64encode(xml_string.encode('utf-8')).decode('utf-8')

def decode_base64_to_xml(base64_string):
    """
    Decode Base64 string to XML

    Args:
        base64_string (str): Base64 encoded content

    Returns:
        str: Decoded XML string
    """
    return base64.b64decode(base64_string).decode('utf-8')

def detect_base64_content(text):
    """
    Detect Base64 encoded content in text, specifically looking for XML elements

    Args:
        text (str): Text to search for Base64 content

    Returns:
        list: List of tuples (element_name, base64_content) found
    """
    import re

    # Pattern to find XML elements that might contain Base64
    element_pattern = r'<(\w+)>([A-Za-z0-9+/]{50,}={0,2})</\1>'
    matches = re.findall(element_pattern, text)

    valid_matches = []
    for element_name, base64_content in matches:
        try:
            # Try to decode to validate it's actually Base64
            decoded = base64.b64decode(base64_content)
            # Check if it looks like valid content (not just binary garbage)
            if len(decoded) > 10:
                valid_matches.append((element_name, base64_content))
        except:
            continue

    return valid_matches

def decode_base64_content_manually(base64_content):
    """
    Manually decode Base64 content provided by user

    Args:
        base64_content (str): Base64 content to decode

    Returns:
        str: Decoded content with file type detection
    """
    try:
        # Clean up the input (remove whitespace, newlines)
        base64_content = ''.join(base64_content.split())

        # Decode the Base64
        decoded_bytes = base64.b64decode(base64_content)

        # Detect file type and handle accordingly
        file_info = detect_file_type(decoded_bytes)

        result = f"=== DECODED CONTENT ===\n"
        result += f"File Type: {file_info['type']}\n"
        result += f"Size: {len(decoded_bytes)} bytes\n\n"
        result += f"Content:\n{file_info['content']}"

        return result

    except Exception as e:
        return f"Decode Error: {str(e)}\n\nMake sure you've pasted valid Base64 content."

def detect_file_type(data_bytes):
    """
    Detect file type from binary data and extract content if possible

    Args:
        data_bytes (bytes): Binary data to analyze

    Returns:
        dict: File type info and extracted content
    """
    # Check for ZIP file signature
    if data_bytes.startswith(b'PK'):
        try:
            import zipfile
            import io

            zip_buffer = io.BytesIO(data_bytes)
            with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                file_list = zip_file.namelist()
                content = f"ZIP Archive containing {len(file_list)} files:\n"

                for filename in file_list:
                    content += f"- {filename}\n"
                    # Try to read text files
                    if filename.endswith(('.txt', '.csv', '.xml', '.json')):
                        try:
                            file_content = zip_file.read(filename).decode('utf-8')
                            content += f"\n=== Content of {filename} ===\n{file_content}\n"
                        except:
                            content += f"\n=== {filename} (binary file) ===\n"

                return {'type': 'ZIP', 'content': content}
        except:
            return {'type': 'ZIP (corrupted)', 'content': 'Could not extract ZIP contents'}

    # Check for CSV/text content
    try:
        text_content = data_bytes.decode('utf-8')
        if ',' in text_content and '\n' in text_content:
            return {'type': 'CSV/Text', 'content': text_content}
        else:
            return {'type': 'Text', 'content': text_content}
    except:
        pass

    # Unknown binary format
    return {'type': 'Binary', 'content': f'Binary data ({len(data_bytes)} bytes) - cannot display as text'}

def is_valid_xml(xml_string):
    """
    Check if string is valid XML

    Args:
        xml_string (str): String to validate

    Returns:
        bool: True if valid XML, False otherwise
    """
    try:
        xml.dom.minidom.parseString(xml_string)
        return True
    except:
        return False
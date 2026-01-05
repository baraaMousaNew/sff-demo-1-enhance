"""
Custom Functions for SOAP API Testing
Add your own functions here for specific business logic
"""
import gzip
import io
import random
import os
import string
import zipfile
from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
import threading
import xml.etree.ElementTree as ET
from functools import lru_cache


# Counter for generating sequential IDs
_counters = {}

# Add these new lines at the top of your file:
# Global cache for loaded data - thread-safe
_data_cache = {}
_cache_lock = threading.Lock()


users = {'T001_Malaffi':{'login':'MalaffiPayertest','password':'Haad@2016'},'T002_Malaffi':{'login':'MalaffiPayertest','password':'Haad@2016'},'TF001_Malaffi':{'login':'MalaffiProvidertest','password':'Haad@2016'},'PF001_Malaffi':{'login':'MalaffiProvidertest','password':'Haad@2016'}}


def _get_cached_excel_data(file_path, sheet_name=None, usecols=None):
    """Load and cache Excel data - FIXED VERSION"""
    cache_key = f"{file_path}:{sheet_name}:{str(usecols)}"

    with _cache_lock:
        if cache_key not in _data_cache:
            try:
                if file_path.endswith('.xls'):
                    if sheet_name is None and usecols is None:
                        # Special case: load all sheets (for Facilities.xls)
                        _data_cache[cache_key] = pd.read_excel(file_path, sheet_name=None, engine='xlrd')
                    else:
                        # Single sheet
                        _data_cache[cache_key] = pd.read_excel(file_path, sheet_name=sheet_name, usecols=usecols,
                                                               engine='xlrd')
                else:
                    # .xlsx files
                    _data_cache[cache_key] = pd.read_excel(file_path, sheet_name=sheet_name, usecols=usecols,
                                                           engine='openpyxl')
                print(f"Loaded and cached: {cache_key}")
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                _data_cache[cache_key] = None

        return _data_cache[cache_key]


def generate_numbers_id(preceding='', length='10'):
    number_length = int(length)
    """Generate patient ID in healthcare format"""
    numeric_value = ''.join(random.choices('0123456789', k=number_length))

    if preceding == '' or len(preceding) == 0:
        return numeric_value
    else:
        return preceding + '-' + numeric_value

def get_random_provider_login():
    providers = ['MalaffiProvidertest']
    return random.choice(providers)

def get_random_payer_id():
    payers = ['T001_Malaffi','T002_Malaffi']
    return random.choice(payers)

def get_random_provider_id():
    providers = ['TF001_Malaffi','PF001_Malaffi']
    return random.choice(providers)

def get_random_payer_login():
    payers = ['MalaffiPayertest']
    return random.choice(payers)

def get_login_from_id(key):
    try:
        return users[key].get('login')
    except KeyError:
        raise KeyError(f'{key} is not valid for login credentials')

def get_password_from_id(key):
    return users[key].get('password')

def generate_random_number(n='5'):
    n = int(n)
    lower = 10 ** (n - 1)
    upper = (10 ** n) - 1
    return random.randint(lower, upper)

def generate_random_digit_string(length='10'):
    length = int(length)
    # Combine letters (both cases) and digits
    characters = string.ascii_letters + string.digits
    # Generate random string
    return ''.join(random.choice(characters) for _ in range(length))

def generate_person_data(data_type):
    """Generate realistic test data"""
    data_type = data_type.lower()
    if data_type == "phone":
        return f"+971-{random.randint(50, 59)}-{random.randint(1000000, 9999999)}"
    elif data_type == "passport":
        characters = string.ascii_uppercase + string.digits  # Uppercase letters and digits
        passport_number = ''.join(random.choice(characters) for i in range(8))
        return passport_number
    elif data_type == "email":
        domains = ["test.ae", "example.com", "demo.org", "healthcare.test"]
        return f"test{random.randint(1000, 9999)}@{random.choice(domains)}"
    elif data_type == "emirates_id":
        # return f"{random.randint(100, 999)}-{random.randint(1000, 9999)}-{random.randint(1000000, 9999999)}-{random.randint(1, 9)}"
        prefix = "784"
        # Year of birth between 1950 and current year
        year = random.randint(1950, datetime.now().year)
        # Unique identifier: 7 digits
        unique_id = random.randint(1000000, 9999999)
        unique_end = random.randint(0, 9)
        emirates_id = f"{prefix}-{year:04d}-{unique_id:07d}-{unique_end}"
        return emirates_id

    elif data_type == "emirates_unified_number":
        return str(random.randint(100000000, 999999999))
    elif data_type == "member_id":
        return random.randint(100000, 999999)
    elif data_type == "nationality":
        try:
            df = _get_cached_excel_data('resources/Nationalities.xlsx', usecols=['Code'])
            if df is not None and hasattr(df, 'columns') and 'Code' in df.columns:
                return random.choice(df['Code'].dropna().tolist())
            else:
                return "Column 'Code' not found in the Excel file."
        except Exception as e:
            return f"Error reading file: {e}"
    elif data_type == "location":
        try:
            df = _get_cached_excel_data('resources/Location.xlsx', usecols=['City'])
            if df is not None and hasattr(df, 'columns') and 'City' in df.columns:
                return random.choice(df['City'].dropna().tolist())
            else:
                return "Column 'City' not found in the Excel file."
        except Exception as e:
            return f"Error reading file: {e}"
    elif data_type == "emirate":
        try:
            df = _get_cached_excel_data('resources/Emirates.xlsx', usecols=['Code'])
            if df is not None and hasattr(df, 'columns') and 'Code' in df.columns:
                code = random.choice(df['Code'].dropna().tolist())
                return code
            else:
                return "Column 'Code' not found in the Excel file."
        except Exception as e:
            return f"Error reading file: {e}"
    elif data_type == "first_name":
        first_names = [
            "Liam", "Olivia", "Noah", "Emma", "Oliver",
            "Ava", "Elijah", "Sophia", "James", "Isabella",
            "William", "Mia", "Benjamin", "Charlotte", "Lucas"
        ]
        return random.choice(first_names)

    elif data_type == "last_name":
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones",
            "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
            "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson"
        ]
        return random.choice(last_names)
    else:
        return f"<Error with data type: {data_type}>"

def generate_filename(extension='xml', include_timestamp=True):
    """Generate dynamic filenames"""
    timestamp = f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}" if include_timestamp else ""
    characters = string.ascii_letters + string.digits  # a-z, A-Z, 0-9
    string_value = ''.join(random.choice(characters) for _ in range(6))
    return f"test_file_{string_value}_{timestamp}.{extension}"

def get_current_date_time():
    current_datetime = datetime.now()
    return current_datetime.strftime("%d/%m/%Y %H:%M")

def add_minutes_to_current_date_time(minutes="5"):
    minutes = int(minutes)
    current_datetime = datetime.now()
    print(f"Current time: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    new_datetime = current_datetime + timedelta(minutes=minutes)
    return new_datetime.strftime("%d/%m/%Y %H:%M")

def sub_minutes_to_current_date_time(minutes="5"):
    minutes = int(minutes)
    current_datetime = datetime.now()
    print(f"Current time: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    new_datetime = current_datetime - timedelta(minutes=minutes)
    return new_datetime.strftime("%d/%m/%Y %H:%M")

def add_days_to_current_date_time(days="5"):
    days = int(days)
    current_datetime = datetime.now()
    print(f"Current time: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    new_datetime = current_datetime + timedelta(days=days)
    return new_datetime.strftime("%d/%m/%Y %H:%M")

def sub_days_to_current_date_time(days="5"):
    days = int(days)
    current_datetime = datetime.now()
    print(f"Current time: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    new_datetime = current_datetime - timedelta(days=days)
    return new_datetime.strftime("%d/%m/%Y %H:%M")

def add_days_to_current_date(days="5"):
    days = int(days)
    current_datetime = datetime.now()
    print(f"Current time: {current_datetime.strftime('%Y-%m-%d')}")
    new_datetime = current_datetime + timedelta(days=days)
    return new_datetime.strftime("%d/%m/%Y")

def sub_days_to_current_date(days="5"):
    days = int(days)
    current_datetime = datetime.now()
    print(f"Current time: {current_datetime.strftime('%Y-%m-%d')}")
    new_datetime = current_datetime - timedelta(days=days)
    return new_datetime.strftime("%d/%m/%Y")

def generate_dob(min_age="18"):
    """
    Generates a random date of birth for someone older than 18 years old.
    """
    today = datetime.today()
    today = datetime.today()
    age_int = int(min_age)
    latest_birth_date = today - timedelta(days=age_int * 365)
    earliest_birth_date = today - timedelta(days=100 * 365)  # Assuming max age is 100

    random_birth_date = earliest_birth_date + timedelta(
        days=random.randint(0, (latest_birth_date - earliest_birth_date).days)
    )
    return random_birth_date.strftime("%d/%m/%Y")

def get_random_facility_license():
    """Get random facility license from cached data - FIXED"""
    try:
        # For .xls files with multiple sheets, we get a dict of DataFrames
        xls_data = _get_cached_excel_data('resources/Facilities.xls')

        license_values = []
        if xls_data and isinstance(xls_data, dict):  # Multiple sheets
            for sheet_name, sheet_df in xls_data.items():
                if hasattr(sheet_df, 'columns'):
                    for col in sheet_df.columns:
                        if isinstance(col, str) and "DoH Facility License" in col:
                            license_values.extend(sheet_df[col].dropna().astype(str).tolist())
        elif xls_data and hasattr(xls_data, 'columns'):  # Single sheet
            for col in xls_data.columns:
                if isinstance(col, str) and "DoH Facility License" in col:
                    license_values.extend(xls_data[col].dropna().astype(str).tolist())

        if license_values:
            return random.choice(license_values)
        else:
            return "No 'DoH Facility License' values found."
    except Exception as e:
        return f"Error: {e}"

def get_random_encounter_type():
    facility_types = {
        1: "No Bed + No Emergency Room",
        2: "No Bed + Emergency Room",
        3: "Inpatient Bed + No Emergency Room",
        4: "Inpatient Bed + Emergency Room",
        5: "Daycase Bed + No Emergency Room",
        6: "Daycase Bed + Emergency Room",
        7: "Nationals Screening",
        8: "New Visa Screening",
        9: "Renewal Visa Screening",
        10: "Telemedicine",
        12: "Home",
        13: "Assisted Living Facility",
        15: "Mobile Unit",
        41: "Ambulance – Land",
        42: "Ambulance – Air or Water"
    }
    key = random.choice(list(facility_types.keys()))
    return key

def get_random_diagnosis_type():
    diagnosis_types = [
        "Principal",
        "Secondary",
        "Admitting",
        "ReasonForVisit"
    ]
    return random.choice(diagnosis_types)


def get_random_icd_code():
    """Get random ICD code from cached data - FIXED"""
    try:
        df = _get_cached_excel_data('resources/CM-Codes-1.xlsx', sheet_name="Full_List", usecols=["ICD_10_CM_Code"])

        if df is not None and hasattr(df, 'columns') and "ICD_10_CM_Code" in df.columns:
            codes = df["ICD_10_CM_Code"].dropna().tolist()
            if codes:
                return random.choice(codes)
            else:
                return "No ICD codes found in data"
        else:
            return "Column 'ICD_10_CM_Code' not found."
    except Exception as e:
        return f"Error: {e}"

def zip_file(xml):
    xml_string = ET.tostring(xml, encoding='unicode')
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('context.xml', xml_string)
    zip_data = zip_buffer.getvalue()
    return zip_data


def get_random_clinician_license():
    """Get random ICD code from cached data - FIXED"""
    try:
        df = _get_cached_excel_data('resources/Clinicians.xlsx', sheet_name="Sheet1", usecols=["Clinician License"])

        if df is not None and hasattr(df, 'columns') and "Clinician License" in df.columns:
            codes = df["Clinician License"].dropna().tolist()
            if codes:
                return random.choice(codes)
            else:
                return "No Clinician License found in data"
        else:
            return "Column 'Clinician License' not found."
    except Exception as e:
        return f"Error: {e}"

def get_random_code_type():
    code_types = {
        3: "CPT",
        4: "HCPCS",
        5: "Trade Drug",
        6: "Dental",
        8: "Service Code",
        9: "IR-DRG",
        10: "Generic Drug"
    }
    key = random.choice(list(code_types.keys()))
    return key


def get_random_cpt_code():
    """Get random CPT code from cached data - FIXED"""
    try:
        # Use the corrected caching function
        df = _get_cached_excel_data('resources/CPT-Codes.xlsx', usecols=['CPT Codes'])

        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'CPT Codes' in df.columns:
                auth_values = df['CPT Codes'].dropna().tolist()
                if auth_values:
                    # Return a random value like A001, A002, etc.
                    return random.choice(auth_values)
                else:
                    return "No CPT Codes values found in data"
            else:
                # Debug what we actually got
                return f"Unexpected data structure. Columns: {getattr(df, 'columns', 'No columns attr')}"
        else:
            return "Failed to load Excel file"

    except Exception as e:
        return f"Error reading file: {e}"

def get_random_hcpcs_code():
    """Get random CPT code from cached data - FIXED"""
    try:
        # Use the corrected caching function
        df = _get_cached_excel_data('resources/HCPCS-Codes.xlsx', usecols=['Code'])

        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'Code' in df.columns:
                auth_values = df['Code'].dropna().tolist()
                if auth_values:
                    # Return a random value like A001, A002, etc.
                    return random.choice(auth_values)
                else:
                    return "No Code values found in data"
            else:
                # Debug what we actually got
                return f"Unexpected data structure. Columns: {getattr(df, 'columns', 'No columns attr')}"
        else:
            return "Failed to load Excel file"

    except Exception as e:
        return f"Error reading file: {e}"

def get_random_service_code():
    """Get random CPT code from cached data - FIXED"""
    try:
        # Use the corrected caching function
        df = _get_cached_excel_data('resources/Service-Codes.xlsx', usecols=['Code'])

        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'Code' in df.columns:
                auth_values = df['Code'].dropna().tolist()
                if auth_values:
                    # Return a random value like A001, A002, etc.
                    return random.choice(auth_values)
                else:
                    return "No Code values found in data"
            else:
                # Debug what we actually got
                return f"Unexpected data structure. Columns: {getattr(df, 'columns', 'No columns attr')}"
        else:
            return "Failed to load Excel file"

    except Exception as e:
        return f"Error reading file: {e}"

def get_random_uscls_code():
    """Get random CPT code from cached data - FIXED"""
    try:
        # Use the corrected caching function
        df = _get_cached_excel_data('resources/USCLS-Codes.xlsx', usecols=['Code'])

        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'Code' in df.columns:
                auth_values = df['Code'].dropna().tolist()
                if auth_values:
                    # Return a random value like A001, A002, etc.
                    return random.choice(auth_values)
                else:
                    return "No Code values found in data"
            else:
                # Debug what we actually got
                return f"Unexpected data structure. Columns: {getattr(df, 'columns', 'No columns attr')}"
        else:
            return "Failed to load Excel file"

    except Exception as e:
        return f"Error reading file: {e}"

def get_random_drg_code():
    """Get random CPT code from cached data - FIXED"""
    try:
        # Use the corrected caching function
        df = _get_cached_excel_data('resources/DRG-Codes.xlsx', usecols=['Code'])

        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'Code' in df.columns:
                auth_values = df['Code'].dropna().tolist()
                if auth_values:
                    # Return a random value like A001, A002, etc.
                    return random.choice(auth_values)
                else:
                    return "No Code values found in data"
            else:
                # Debug what we actually got
                return f"Unexpected data structure. Columns: {getattr(df, 'columns', 'No columns attr')}"
        else:
            return "Failed to load Excel file"

    except Exception as e:
        return f"Error reading file: {e}"


def get_random_observation_type():
    formats = [
        "CPT", "HL7v3 Native", "LOINC", "SNOMED CT",
        "Text", "File", "Flags", "Universal Dental", "Episode"
    ]
    return random.choice(formats)

def remove_last_chars_from_string(value, characters_remove):
    remove = int(characters_remove)
    remove = remove - 2 * remove
    return value[:remove]

def get_random_loinc():
    
    try:
        # Use the corrected caching function
        df = _get_cached_excel_data('resources/Loinc.xlsx', usecols=['LOINC_NUM'])

        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'LOINC_NUM' in df.columns:
                auth_values = df['LOINC_NUM'].dropna().tolist()
                if auth_values:
                    # Return a random value like A001, A002, etc.
                    return random.choice(auth_values)
                else:
                    return "No LOINC_NUM values found in data"
            else:
                # Debug what we actually got
                return f"Unexpected data structure. Columns: {getattr(df, 'columns', 'No columns attr')}"
        else:
            return "Failed to load Excel file"

    except Exception as e:
        return f"Error reading file: {e}"

def get_random_dha_license():
    
    try:
        # Use the corrected caching function
        df = _get_cached_excel_data('resources/DHA-Licenses.xlsx', usecols=['Facility License'])

        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'Facility License' in df.columns:
                auth_values = df['Facility License'].dropna().tolist()
                if auth_values:
                    # Return a random value like A001, A002, etc.
                    return random.choice(auth_values)
                else:
                    return "No Facility License values found in data"
            else:
                # Debug what we actually got
                return f"Unexpected data structure. Columns: {getattr(df, 'columns', 'No columns attr')}"
        else:
            return "Failed to load Excel file"

    except Exception as e:
        return f"Error reading file: {e}"

def get_random_moh_license():
    
    try:
        # Use the corrected caching function
        df = _get_cached_excel_data('resources/MOH-Licenses.xlsx', usecols=['Facility License'])

        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'Facility License' in df.columns:
                auth_values = df['Facility License'].dropna().tolist()
                if auth_values:
                    # Return a random value like A001, A002, etc.
                    return random.choice(auth_values)
                else:
                    return "No Facility License values found in data"
            else:
                # Debug what we actually got
                return f"Unexpected data structure. Columns: {getattr(df, 'columns', 'No columns attr')}"
        else:
            return "Failed to load Excel file"

    except Exception as e:
        return f"Error reading file: {e}"

def get_random_tooth_numbering():
    try:
        # Use the corrected caching function
        df = _get_cached_excel_data('resources/Universal-Tooth-Numbering.xlsx', usecols=['Code'])

        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'Code' in df.columns:
                auth_values = df['Code'].dropna().tolist()
                if auth_values:
                    # Return a random value like A001, A002, etc.
                    return random.choice(auth_values)
                else:
                    return "No Code values found in data"
            else:
                # Debug what we actually got
                return f"Unexpected data structure. Columns: {getattr(df, 'columns', 'No columns attr')}"
        else:
            return "Failed to load Excel file"

    except Exception as e:
        return f"Error reading file: {e}"

def clear_excel_cache():
    """Clear the Excel data cache"""
    global _data_cache
    with _cache_lock:
        _data_cache.clear()
    print("Excel cache cleared")


def get_cache_info():
    """Get cache information"""
    with _cache_lock:
        return {
            'cached_files': len(_data_cache),
            'cache_keys': list(_data_cache.keys())
        }


def preload_excel_files():
    """Pre-load all Excel files for better performance"""
    print("Pre-loading Excel files...")
    files_to_preload = [
        ('resources/Insurers-Only.xlsx', None, ['Auth.No']),
        ('resources/Broker-Or-TPA.xlsx', None, ['Auth.No']),
        ('resources/Facilities.xls', None, None),
        ('resources/CM-Codes-1.xlsx', 'Full_List', ['ICD_10_CM_Code']),
        ('resources/CPT-Codes.xlsx', None, ['CPT Codes']),
        ('resources/Loinc.xlsx', None, ['LOINC_NUM']),
        ('resources/Location.xlsx', None, ['City']),
        ('resources/Nationalities.xlsx', None, ['Code']),
        ('resources/Emirates.xlsx', None, ['Code']),
        ('resources/Clinicians.xlsx', None, ['Clinician License']),
        ('resources/DRG-Codes.xlsx', None, ['Code']),
        ('resources/HCPCS-Codes.xlsx', None, ['Code']),
        ('resources/Service-Codes.xlsx', None, ['Code']),
        ('resources/USCLS-Codes.xlsx', None, ['Code']),
        ('resources/MOH-Licenses.xlsx', None, ['Facility License']),
        ('resources/DHA-Licenses.xlsx', None, ['Facility License']),
        ('resources/Universal-Tooth-Numbering.xlsx', None, ['Code'])
    ]

    for file_path, sheet_name, usecols in files_to_preload:
        if os.path.exists(file_path):
            _get_cached_excel_data(file_path, sheet_name, usecols)
        else:
            print(f"Warning: {file_path} not found")
    print("Pre-loading complete")


# Auto-preload when module is imported
try:
    preload_excel_files()
except Exception as e:
    print(f"Warning: Could not pre-load files: {e}")













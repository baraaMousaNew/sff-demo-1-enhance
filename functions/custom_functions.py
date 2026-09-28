"""
Custom Functions for SOAP API Testing
Add your own functions here for specific business logic
"""
import base64
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
from utils.env_vars import EnvVar


# Counter for generating sequential IDs
_counters = {}

# Add these new lines at the top of your file:
# Global cache for loaded data - thread-safe
_data_cache = {}
_cache_lock = threading.Lock()


users = {
    'T001_Malaffi':{
        'type':'payer',
        'login':'MalaffiPayertest',
        'password':'Haad@2016'
    },
    'T002_Malaffi':{
        'type':'tpa',
        'login':'MalaffiPayer2test',
        'password':'Haad@2016'
    },
    'TF001_Malaffi':{
         'type':'provider',
         'login':'MalaffiProvidertest',
         'password':'Haad@2016'}
    ,
    'PF001_Malaffi':{
        'type':'pharmacy',
        'login':'MalaffiProvider2test',
        'password':'Haad@2016'},
    'HAAD':{
        'type':'haad',
        'login':'MalaffiPayertest',
        'password':'Haad@2016'}
}


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


def _get_cached_csv_data(file_path, usecols=None):
    """Load and cache CSV data - thread-safe"""
    cache_key = f"{file_path}:csv:{str(usecols)}"

    with _cache_lock:
        if cache_key not in _data_cache:
            try:
                _data_cache[cache_key] = pd.read_csv(file_path, usecols=usecols, low_memory=False)
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

def generate_numbers_id_hash(preceding='', length='10'):
    number_length = int(length)
    """Generate patient ID in healthcare format"""
    numeric_value = ''.join(random.choices('0123456789', k=number_length))

    if preceding == '' or len(preceding) == 0:
        return numeric_value
    else:
        return preceding + '#' + numeric_value

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
        user = users[key]
    except KeyError:
        raise KeyError(f'{key} is not valid for login credentials')
    if os.environ.get(EnvVar.USE_SPECIFIC_LOGIN) == "true":
        _type_to_env = {
            'payer':    EnvVar.PAYER_VALUE,
            'tpa':      EnvVar.TPA_VALUE,
            'provider': EnvVar.PROVIDER_VALUE,
            'pharmacy': EnvVar.PHARMACY_VALUE,
        }
        env_key = _type_to_env.get(user.get('type'))
        if env_key:
            return os.environ.get(env_key, user.get('login'))
    return user.get('login')

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

def generate_claim_id(prefix='MF3505'):
    part1 = generate_numbers_id('', 6)
    part2 = generate_random_digit_string(6)
    part3 = generate_random_number(1)
    return f"{prefix}-{part1}-{part2}-{part3}"

def generate_random_digit_string_with_whitespaces(length='10', whitespaces='3', start_end_whitespaces='0'):
    """Generate a random alphanumeric string with randomly placed and/or anchored whitespace characters.

    Args:
        length:               Total length of the resulting string (alphanumeric + all whitespaces combined).
        whitespaces:          Number of whitespace characters to insert at random positions in the interior.
        start_end_whitespaces: Number of whitespace characters to place at the very start and end of the
                              string. They are split evenly (half at the start, half at the end); if the
                              count is odd, the extra space goes to the start.

    Returns:
        A string of the given total length where `start_end_whitespaces` spaces are anchored at the
        boundaries and `whitespaces` spaces are randomly distributed in between. The remaining
        characters are random letters/digits.

    Example:
        generate_random_digit_string_with_whitespaces('12', '2', '4')
        # Total 12 chars: 2 leading spaces + 2 trailing spaces + 2 random interior spaces + 6 alnum
        # e.g. "  aB k9mQ  "
    """
    length = int(length)
    whitespaces = int(whitespaces)
    start_end_whitespaces = int(start_end_whitespaces)

    # Clamp totals so they never exceed total length
    total_spaces = min(whitespaces + start_end_whitespaces, length)
    start_end_whitespaces = min(start_end_whitespaces, total_spaces)
    whitespaces = total_spaces - start_end_whitespaces

    # Split start_end_whitespaces: odd remainder goes to the start
    spaces_at_end = start_end_whitespaces // 2
    spaces_at_start = start_end_whitespaces - spaces_at_end

    characters = string.ascii_letters + string.digits
    alphanumeric_count = length - total_spaces

    # Build the alphanumeric interior
    result = list(random.choice(characters) for _ in range(alphanumeric_count))

    # Insert random interior spaces
    for _ in range(whitespaces):
        insert_pos = random.randint(0, len(result))
        result.insert(insert_pos, ' ')

    # Prepend and append the anchored spaces
    result = [' '] * spaces_at_start + result + [' '] * spaces_at_end

    return ''.join(result)

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
        year = random.randint(1950, 2005)
        seq = str(random.randint(0, 9999999)).zfill(7)
        partial = f"784{year}{seq}"

        # Luhn algorithm to compute check digit
        total = 0
        for i, digit in enumerate(reversed(partial)):
            n = int(digit)
            if i % 2 == 0:
                n *= 2
                if n > 9:
                    n -= 9
            total += n

        check_digit = (10 - (total % 10)) % 10
        return f"784-{year}-{seq}-{check_digit}"

    elif data_type == "emirates_unified_number":
        return str(random.randint(100000000000, 999999999999))
    elif data_type == "member_id":
        return random.randint(100000000, 999999999)
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

def get_current_date():
    current_datetime = datetime.now()
    return current_datetime.strftime("%d/%m/%Y")

def get_current_date_iso():
    current_datetime = datetime.now()
    return current_datetime.strftime("%Y-%m-%d")

def get_current_year():
    return str(datetime.now().year)

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

def add_hours_to_current_date_time(hours="1"):
    hours = int(hours)
    current_datetime = datetime.now()
    print(f"Current time: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    new_datetime = current_datetime + timedelta(hours=hours)
    return new_datetime.strftime("%d/%m/%Y %H:%M")

def sub_hours_to_current_date_time(hours="1"):
    hours = int(hours)
    current_datetime = datetime.now()
    print(f"Current time: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    new_datetime = current_datetime - timedelta(hours=hours)
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

def get_date_offset(days="5"):
    days = int(days)
    if days < 0:
        return sub_days_to_current_date(days=abs(days))
    return add_days_to_current_date(days=days)

def format_date_to_iso(date_text):
    if date_text is None:
        return ""
    try:
        # Split by space to handle potential time component
        date_part = str(date_text).split(' ')[0]
        # Parse from DD/MM/YYYY and format to YYYY-MM-DD
        date_obj = datetime.strptime(date_part, "%d/%m/%Y")
        return date_obj.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error formatting date {date_text}: {e}")
        return str(date_text)

def format_datetime_to_iso(date_text):
    if date_text is None:
        return ""
    try:
        date_str = str(date_text).strip()
        # Check if it has time component
        if ' ' in date_str:
            # Parse DD/MM/YYYY HH:MM and format to YYYY-MM-DD HH:MM
            date_obj = datetime.strptime(date_str, "%d/%m/%Y %H:%M")
            return date_obj.strftime("%Y-%m-%d %H:%M")
        else:
            # Parse date only
            date_obj = datetime.strptime(date_str, "%d/%m/%Y")
            return date_obj.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error formatting datetime {date_text}: {e}")
        return str(date_text)

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

def get_dob_for_age(age):
    """
    Generates a date of birth for a person who is exactly the given age today.

    Args:
        age: The exact age in years (e.g. '55').

    Returns:
        The date of birth as a string in DD/MM/YYYY format.
    """
    from dateutil.relativedelta import relativedelta
    age_int = int(age)
    dob = datetime.today() - relativedelta(years=age_int)
    return dob.strftime("%d/%m/%Y")

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

def get_random_facility_license_number_by_status(status='Active'):
    """Get a random Facility License Number filtered by status from Facility Licensing History.xlsx.

    Reads the 'Facility Licensing Status' sheet and returns a random license number
    whose Status column matches the given status (case-insensitive).

    Args:
        status: The license status to filter by. Accepted values are 'Active' or 'Inactive'.
                Defaults to 'Active'.

    Returns:
        A random matching Facility License Number string, or an error/info message if none found.
    """
    try:
        df = _get_cached_excel_data(
            'resources/Facility Licensing History.xlsx',
            sheet_name='Facility Licensing Status',
            usecols=['Facility License Number', 'Status']
        )

        if df is None or not hasattr(df, 'columns'):
            return "Failed to load 'Facility Licensing History.xlsx'"

        required_cols = {'Facility License Number', 'Status'}
        if not required_cols.issubset(set(df.columns)):
            missing = required_cols - set(df.columns)
            return f"Missing columns in 'Facility Licensing History.xlsx': {missing}"

        filtered = df[df['Status'].astype(str).str.strip().str.lower() == status.strip().lower()]
        license_numbers = filtered['Facility License Number'].dropna().astype(str).tolist()

        if license_numbers:
            return random.choice(license_numbers)
        else:
            return f"No Facility License Number found with status '{status}'"

    except Exception as e:
        return f"Error reading 'Facility Licensing History.xlsx': {e}"


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


def get_random_icd_code(is_expired='false'):
    """Get random ICD code from cached data - reads from All ICD codes.csv.

    Args:
        is_expired: When the string 'true', returns a code that has an expiry date.
                    Any other value returns a code from the full list.
    """
    try:
        if is_expired == 'true':
            df = _get_cached_csv_data('resources/All ICD codes.csv', usecols=["DIAGNOSIS_CODE_ID", "EXPIRY_DATE"])
            if df is not None and hasattr(df, 'columns') and "DIAGNOSIS_CODE_ID" in df.columns:
                expired_df = df[df["EXPIRY_DATE"].notna()]
                codes = expired_df["DIAGNOSIS_CODE_ID"].dropna().tolist()
                if codes:
                    return random.choice(codes)
                else:
                    return "No expired ICD codes found in data"
            else:
                return "Column 'DIAGNOSIS_CODE_ID' not found."
        else:
            df = _get_cached_csv_data('resources/All ICD codes.csv', usecols=["DIAGNOSIS_CODE_ID"])
            if df is not None and hasattr(df, 'columns') and "DIAGNOSIS_CODE_ID" in df.columns:
                codes = df["DIAGNOSIS_CODE_ID"].dropna().tolist()
                if codes:
                    return random.choice(codes)
                else:
                    return "No ICD codes found in data"
            else:
                return "Column 'DIAGNOSIS_CODE_ID' not found."
    except Exception as e:
        return f"Error: {e}"

def get_icd_code_effective_date(code):
    """Get the effective date of a given ICD code from the CSV data.

    Args:
        code: The ICD diagnosis code to look up (DIAGNOSIS_CODE_ID).

    Returns:
        The effective date as a string, an empty string if no effective date exists,
        or an error message if the code is not found.
    """
    try:
        df = _get_cached_csv_data('resources/All ICD codes.csv', usecols=["DIAGNOSIS_CODE_ID", "EFFECTIVE_DATE"])
        if df is not None and hasattr(df, 'columns') and "DIAGNOSIS_CODE_ID" in df.columns:
            match = df[df["DIAGNOSIS_CODE_ID"] == code]
            if match.empty:
                return f"ICD code '{code}' not found in data"
            effective_date = match.iloc[0]["EFFECTIVE_DATE"]
            if pd.isna(effective_date):
                return ""
            return str(effective_date)
        else:
            return "Column 'DIAGNOSIS_CODE_ID' not found."
    except Exception as e:
        return f"Error: {e}"


def get_icd_code_expiry_date(code):
    """Get the expiry date of a given ICD code from the CSV data.

    Args:
        code: The ICD diagnosis code to look up (DIAGNOSIS_CODE_ID).

    Returns:
        The expiry date as a string, an empty string if no expiry date exists,
        or an error message if the code is not found.
    """
    try:
        df = _get_cached_csv_data('resources/All ICD codes.csv', usecols=["DIAGNOSIS_CODE_ID", "EXPIRY_DATE"])
        if df is not None and hasattr(df, 'columns') and "DIAGNOSIS_CODE_ID" in df.columns:
            match = df[df["DIAGNOSIS_CODE_ID"] == code]
            if match.empty:
                return f"ICD code '{code}' not found in data"
            expiry_date = match.iloc[0]["EXPIRY_DATE"]
            if pd.isna(expiry_date):
                return ""
            return str(expiry_date)
        else:
            return "Column 'DIAGNOSIS_CODE_ID' not found."
    except Exception as e:
        return f"Error: {e}"


def zip_file(xml):
    xml_string = ET.tostring(xml, encoding='unicode')
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('context.xml', xml_string)
    zip_data = zip_buffer.getvalue()
    return zip_data

def zip_files(*args):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for i, xml in enumerate(args):
            xml_string = ET.tostring(xml, encoding='unicode')
            zip_file.writestr(f'context_{i}.xml', xml_string)
    zip_data = zip_buffer.getvalue()
    return zip_data


def _get_active_clinician_licenses():
    """Get the cached list of clinician license numbers currently active.

    Reads 'Clinician Licensing History.xlsx' (sheet 'Clinician Licensing Status'), where each
    license number has multiple rows recording status changes over time. A license is considered
    active if its most recent status change as of now is 'ACTIVE'. The computed list is cached
    since the underlying sheet has ~500k+ rows.

    Returns:
        A list of active license number strings, or an error message string on failure.
    """
    cache_key = 'active_clinician_licenses'
    with _cache_lock:
        active_licenses = _data_cache.get(cache_key)

    if active_licenses is not None:
        return active_licenses

    df = _get_cached_excel_data(
        'resources/Clinician Licensing History.xlsx',
        sheet_name='Clinician Licensing Status',
        usecols=['License Number', 'Effective Date', 'Status']
    )

    if df is None or not hasattr(df, 'columns'):
        return "Failed to load 'Clinician Licensing History.xlsx'"

    required_cols = {'License Number', 'Effective Date', 'Status'}
    if not required_cols.issubset(set(df.columns)):
        missing = required_cols - set(df.columns)
        return f"Missing columns in 'Clinician Licensing History.xlsx': {missing}"

    current = df[df['Effective Date'] <= datetime.now()]
    latest = current.sort_values('Effective Date').groupby('License Number').tail(1)
    active_licenses = latest[
        latest['Status'].astype(str).str.strip().str.upper() == 'ACTIVE'
    ]['License Number'].dropna().astype(str).tolist()

    with _cache_lock:
        _data_cache[cache_key] = active_licenses

    return active_licenses


def get_random_clinician_license():
    """Get a random clinician license that is currently active.

    Returns:
        A random currently-active clinician license number, or an error/info message if none found.
    """
    try:
        active_licenses = _get_active_clinician_licenses()
        if isinstance(active_licenses, str):
            return active_licenses

        if active_licenses:
            return random.choice(active_licenses)
        else:
            return "No active clinician license found"
    except Exception as e:
        return f"Error reading 'Clinician Licensing History.xlsx': {e}"

def get_clinician_license_starting_with(major, profession, category):
    """Get a random clinician license from Clinicians.xlsx filtered by major, profession, and category.

    Each parameter supports a "starts with" match (case-insensitive).
    To negate a filter (i.e. "does NOT start with"), prefix the value with "! ".
    For example, passing major="! pharma" returns licenses where major does NOT start with "pharma".

    Only clinicians whose license is currently active per 'Clinician Licensing History.xlsx' are
    considered (the 'To' date in Clinicians.xlsx is unreliable and is no longer used).

    Args:
        major:      The major to filter by, or "! <value>" to exclude entries starting with <value>.
        profession: The profession to filter by, or "! <value>" to exclude entries starting with <value>.
        category:   The category to filter by, or "! <value>" to exclude entries starting with <value>.

    Returns:
        A random matching clinician license string, or an error/info message if none are found.
    """
    try:
        df = _get_cached_excel_data(
            'resources/Clinicians.xlsx',
            sheet_name="Sheet1",
            usecols=["Clinician License", "Major", "Profession", "Category"]
        )

        if df is None or not hasattr(df, 'columns'):
            return "Failed to load Clinicians.xlsx"

        required_cols = {"Clinician License", "Major", "Profession", "Category"}
        if not required_cols.issubset(set(df.columns)):
            missing = required_cols - set(df.columns)
            return f"Missing columns in Clinicians.xlsx: {missing}"

        def _apply_starts_with_filter(dataframe, column, param):
            """Filter dataframe rows where column starts with (or does NOT start with) param."""
            param = str(param).strip()
            if param.startswith("! "):
                prefix = param[2:].strip()
                return dataframe[~dataframe[column].astype(str).str.lower().str.startswith(prefix.lower())]
            else:
                return dataframe[dataframe[column].astype(str).str.lower().str.startswith(param.lower())]

        filtered = df.dropna(subset=["Clinician License", "Major", "Profession", "Category"])
        filtered = _apply_starts_with_filter(filtered, "Major", major)
        filtered = _apply_starts_with_filter(filtered, "Profession", profession)
        filtered = _apply_starts_with_filter(filtered, "Category", category)

        active_licenses = _get_active_clinician_licenses()
        if isinstance(active_licenses, str):
            return active_licenses

        active_set = set(active_licenses)
        licenses = [lic for lic in filtered["Clinician License"].dropna().tolist() if lic in active_set]

        if licenses:
            return random.choice(licenses)
        else:
            return (
                f"No active clinician license found where Major starts with '{major}', "
                f"Profession starts with '{profession}', Category starts with '{category}'"
            )

    except Exception as e:
        return f"Error reading Clinicians.xlsx: {e}"


def get_clinician_license_containing(major, profession, category):
    """Get a random clinician license from Clinicians.xlsx filtered by major, profession, and category.

    Each parameter performs a case-insensitive "contains but not at the start" match —
    the value must appear somewhere in the field, but NOT as the leading characters.
    For example, major="pharma" matches "master of pharmacy" but NOT "pharmacy technician".
    To negate a filter (i.e. the value is NOT contained after position 0), prefix with "! ".
    For example, major="! pharma" excludes entries where major contains "pharma" after position 0.

    Args:
        major:      The major to filter by, or "! <value>" to exclude entries containing <value>.
        profession: The profession to filter by, or "! <value>" to exclude entries containing <value>.
        category:   The category to filter by, or "! <value>" to exclude entries containing <value>.

    Returns:
        A random matching clinician license string, or an error/info message if none are found.
    """
    try:
        df = _get_cached_excel_data(
            'resources/Clinicians.xlsx',
            sheet_name="Sheet1",
            usecols=["Clinician License", "Major", "Profession", "Category"]
        )

        if df is None or not hasattr(df, 'columns'):
            return "Failed to load Clinicians.xlsx"

        required_cols = {"Clinician License", "Major", "Profession", "Category"}
        if not required_cols.issubset(set(df.columns)):
            missing = required_cols - set(df.columns)
            return f"Missing columns in Clinicians.xlsx: {missing}"

        def _apply_contains_filter(dataframe, column, param):
            """Filter rows where column contains param AFTER position 0 (not at the very start).
            Step 1 (always): exclude rows where value STARTS WITH the substring.
            Step 2:
              - Positive (pharma):   keep rows where substring EXISTS after position 0.
              - Negation (! pharma): also exclude rows where substring appears ANYWHERE else.
            """
            param = str(param).strip()
            col_lower = dataframe[column].astype(str).str.lower()
            if param.startswith("! "):
                substring = param[2:].strip().lower()
                # Negation: substring must not appear at start OR anywhere else (not at all)
                contains_mask = col_lower.str.contains(substring, regex=False)
                return dataframe[~contains_mask]
            else:
                # Positive: substring must be present but NOT at the very start
                substring = param.lower()
                contains_mask = col_lower.str.contains(substring, regex=False)
                starts_mask   = col_lower.str.startswith(substring)
                return dataframe[contains_mask & ~starts_mask]

        filtered = df.dropna(subset=["Clinician License", "Major", "Profession", "Category"])
        filtered = _apply_contains_filter(filtered, "Major", major)
        filtered = _apply_contains_filter(filtered, "Profession", profession)
        filtered = _apply_contains_filter(filtered, "Category", category)

        licenses = filtered["Clinician License"].dropna().tolist()
        if licenses:
            return random.choice(licenses)
        else:
            return (
                f"No clinician license found where Major contains (not at start) '{major}', "
                f"Profession contains (not at start) '{profession}', "
                f"Category contains (not at start) '{category}'"
            )

    except Exception as e:
        return f"Error reading Clinicians.xlsx: {e}"


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
    """Get random CPT code from cached data"""
    try:
        df = _get_cached_excel_data('resources/CPT-Codes.xlsx', usecols=['Code'])
        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]
        if hasattr(df, 'columns') and 'Code' in df.columns:
            values = df['Code'].dropna().tolist()
            if values:
                return random.choice(values)
            return "No Code values found in data"
        return f"Column 'Code' not found. Columns: {getattr(df, 'columns', 'N/A')}"
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

def get_random_haad_license():
    """Get a random License from HAAD-Licenses.xls."""
    try:
        xls_data = _get_cached_excel_data('resources/HAAD-Licenses.xls')

        license_values = []
        if xls_data and isinstance(xls_data, dict):  # Multiple sheets
            for sheet_name, sheet_df in xls_data.items():
                if hasattr(sheet_df, 'columns'):
                    for col in sheet_df.columns:
                        if isinstance(col, str) and col.strip() == 'License':
                            license_values.extend(sheet_df[col].dropna().astype(str).tolist())
        elif xls_data is not None and hasattr(xls_data, 'columns'):  # Single sheet
            for col in xls_data.columns:
                if isinstance(col, str) and col.strip() == 'License':
                    license_values.extend(xls_data[col].dropna().astype(str).tolist())

        if license_values:
            return random.choice(license_values)
        else:
            return "No 'License' values found in HAAD-Licenses.xls."
    except Exception as e:
        return f"Error reading HAAD-Licenses.xls: {e}"

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

def get_random_insurer():
    """Get a random Auth.No from Insurers-Only.xlsx."""
    try:
        df = _get_cached_excel_data('resources/Insurers-Only.xlsx', usecols=['Auth.No'])

        if df is not None:
            if isinstance(df, dict):
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'Auth.No' in df.columns:
                auth_values = df['Auth.No'].dropna().tolist()
                if auth_values:
                    return random.choice(auth_values)
                else:
                    return "No Auth.No values found in Insurers-Only.xlsx"
            else:
                return f"Column 'Auth.No' not found. Available columns: {getattr(df, 'columns', 'N/A').tolist()}"
        else:
            return "Failed to load Insurers-Only.xlsx"

    except Exception as e:
        return f"Error reading Insurers-Only.xlsx: {e}"


def get_random_broker_or_tpa(classification):
    """Get a random Auth.No from Broker-Or-TPA.xlsx filtered by classification.

    Args:
        classification: The classification value to filter by (e.g. 'Broker', 'TPA').
                        Matching is case-insensitive.

    Returns:
        A random Auth.No string matching the given classification, or an error message.
    """
    try:
        df = _get_cached_excel_data('resources/Broker-Or-TPA.xlsx', usecols=['Classification', 'Auth.No'])

        if df is not None:
            if isinstance(df, dict):
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'Auth.No' in df.columns and 'Classification' in df.columns:
                filtered_df = df[df['Classification'].astype(str).str.lower() == classification.lower()]
                auth_values = filtered_df['Auth.No'].dropna().tolist()
                if auth_values:
                    return random.choice(auth_values)
                else:
                    return f"No Auth.No values found for classification '{classification}' in Broker-Or-TPA.xlsx"
            else:
                return f"Required columns not found. Available columns: {getattr(df, 'columns', 'N/A').tolist()}"
        else:
            return "Failed to load Broker-Or-TPA.xlsx"

    except Exception as e:
        return f"Error reading Broker-Or-TPA.xlsx: {e}"


def add_months_to_current_date(months, days=0, date_format="%d/%m/%Y"):
    """Add months and days to the current date.

    Args:
        months: Number of months to add (integer).
        days: Number of additional days to add (integer, default 0).
        date_format: Output date format string (default: '%d/%m/%Y').

    Returns:
        A date string with the months and days added.
    """
    from dateutil.relativedelta import relativedelta
    result = datetime.now() + relativedelta(months=int(months)) + timedelta(days=int(days))
    return result.strftime(date_format)


def subtract_months_from_current_date(months, days=0, date_format="%d/%m/%Y"):
    """Subtract months and days from the current date.

    Args:
        months: Number of months to subtract (integer).
        days: Number of additional days to subtract (integer, default 0).
        date_format: Output date format string (default: '%d/%m/%Y').

    Returns:
        A date string with the months and days subtracted.
    """
    from dateutil.relativedelta import relativedelta
    result = datetime.now() - relativedelta(months=int(months)) - timedelta(days=int(days))
    return result.strftime(date_format)


def get_image_as_base64(image_name):
    """Search for an image by name under the resources folder, encode it to base64, and return the value.

    Args:
        image_name: The filename of the image to look up (e.g. '6_4_image.jpeg').

    Returns:
        A base64-encoded string of the image content, or an error message if the file is not found.
    """
    try:
        image_path = os.path.join('resources', image_name)
        if not os.path.isfile(image_path):
            return f"Image '{image_name}' not found in resources folder."
        with open(image_path, 'rb') as image_file:
            encoded = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded
    except Exception as e:
        return f"Error encoding image '{image_name}': {e}"


def zip_xml_templates_as_base64(template1, template2=None):
    """Locate one or two XML files by name under the xml_templates folder, zip them,
    and return the base64-encoded content of the resulting zip archive.

    Args:
        template1: The filename of the first XML template (e.g. 'claim_submission_template.xml').
        template2: (Optional) The filename of the second XML template. If omitted, only
                   template1 is zipped and encoded.

    Returns:
        A base64-encoded string of the zipped XML file(s), or an error message if a file is not found.
    """
    try:
        xml_templates_dir = 'xml_templates'
        template2 = template2 if template2 and str(template2).strip() else None

        path1 = os.path.join(xml_templates_dir, template1)
        if not os.path.isfile(path1):
            return f"Template '{template1}' not found in xml_templates folder."

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(path1, arcname=template1)

            if template2 is not None:
                path2 = os.path.join(xml_templates_dir, template2)
                if not os.path.isfile(path2):
                    return f"Template '{template2}' not found in xml_templates folder."
                zf.write(path2, arcname=template2)

        encoded = base64.b64encode(zip_buffer.getvalue()).decode('utf-8')
        return encoded

    except Exception as e:
        return f"Error zipping xml templates: {e}"


def get_random_denial_code(status):
    """Get a random denial code from 'denial codes.xlsx' filtered by status.

    Args:
        status: The status to filter by (e.g. 'Same', 'New', 'Retired').
                Matching is case-insensitive.

    Returns:
        A random Code string matching the given status, or an error/info message.
    """
    try:
        df = _get_cached_excel_data(
            'resources/denial codes.xlsx',
            sheet_name='Denial',
            usecols=['Code', 'Status']
        )

        if df is None or not hasattr(df, 'columns'):
            return "Failed to load 'denial codes.xlsx'"

        if 'Code' not in df.columns or 'Status' not in df.columns:
            return f"Required columns not found. Available columns: {df.columns.tolist()}"

        filtered = df[df['Status'].astype(str).str.strip().str.lower() == status.strip().lower()]
        codes = filtered['Code'].dropna().tolist()

        if codes:
            return random.choice(codes)
        else:
            return f"No denial codes found with status '{status}'"

    except Exception as e:
        return f"Error reading 'denial codes.xlsx': {e}"


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


def get_random_icd9_diagnosis_code():
    """Get a random ICD-9 diagnosis code from ICD9_DATASET.xlsx.

    Returns:
        A random Diagnosis_Codes_Proper string, or an error/info message if none found.
    """
    try:
        df = _get_cached_excel_data(
            'resources/ICD9_DATASET.xlsx',
            sheet_name='Sheet1',
            usecols=['Diagnosis_Codes_Proper']
        )

        if df is None or not hasattr(df, 'columns'):
            return "Failed to load 'ICD9_DATASET.xlsx'"

        if 'Diagnosis_Codes_Proper' not in df.columns:
            return "Column 'Diagnosis_Codes_Proper' not found in 'ICD9_DATASET.xlsx'"

        codes = df['Diagnosis_Codes_Proper'].dropna().astype(str).tolist()
        if codes:
            return random.choice(codes)
        else:
            return "No ICD-9 diagnosis codes found in 'ICD9_DATASET.xlsx'"

    except Exception as e:
        return f"Error reading 'ICD9_DATASET.xlsx': {e}"


def get_random_icd10_diagnosis_code():
    """Get a random ICD-10-CM code from ICD10_DATASET.xlsx.

    Returns:
        A random ICD_10_CM_Code string, or an error/info message if none found.
    """
    try:
        df = _get_cached_excel_data(
            'resources/ICD10_DATASET.xlsx',
            sheet_name='Full_List',
            usecols=['ICD_10_CM_Code']
        )

        if df is None or not hasattr(df, 'columns'):
            return "Failed to load 'ICD10_DATASET.xlsx'"

        if 'ICD_10_CM_Code' not in df.columns:
            return "Column 'ICD_10_CM_Code' not found in 'ICD10_DATASET.xlsx'"

        codes = df['ICD_10_CM_Code'].dropna().astype(str).tolist()
        if codes:
            return random.choice(codes)
        else:
            return "No ICD-10-CM codes found in 'ICD10_DATASET.xlsx'"

    except Exception as e:
        return f"Error reading 'ICD10_DATASET.xlsx': {e}"


def preload_excel_files():
    """Pre-load all Excel files for better performance"""
    print("Pre-loading Excel files...")
    files_to_preload = [
        ('resources/Insurers-Only.xlsx', None, ['Auth.No']),
        ('resources/Broker-Or-TPA.xlsx', None, ['Auth.No']),
        ('resources/Facilities.xls', None, None),
        ('resources/All ICD codes.csv', None, ['DIAGNOSIS_CODE']),
        ('resources/CPT-Codes.xlsx', None, ['Code']),
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
        ('resources/HAAD-Licenses.xls', None, None),
        ('resources/Universal-Tooth-Numbering.xlsx', None, ['Code']),
        ('resources/denial codes.xlsx', 'Denial', ['Code', 'Status']),
        ('resources/ICD10_DATASET.xlsx', 'Full_List', ['ICD_10_CM_Code']),
        ('resources/ICD9_DATASET.xlsx', 'Sheet1', ['Diagnosis_Codes_Proper']),
        ('resources/consultation mandatory tarrif.xlsx', 'Sheet1', ['CODE']),
        ('resources/Clinician Licensing History.xlsx', 'Clinician Licensing Status',
         ['License Number', 'Effective Date', 'Status']),
        ('resources/all_NE_facilities.xlsx', None, ['LicenseNumber']),
    ]

    for file_path, sheet_name, usecols in files_to_preload:
        if os.path.exists(file_path):
            _get_cached_excel_data(file_path, sheet_name, usecols)
        else:
            print(f"Warning: {file_path} not found")
    print("Pre-loading complete")


def add_to_number(value, amount):
    """Add amount to value and return the result as a string."""
    return str(int(value) + int(amount))


def sub_from_number(value, amount):
    """Subtract amount from value and return the result as a string."""
    return str(int(value) - int(amount))


# Auto-preload when module is imported
try:
    preload_excel_files()
except Exception as e:
    print(f"Warning: Could not pre-load files: {e}")


def append_time_to_date(date_str, time_str="00:00"):
    """
    Appends a time (HH:MM) to a date string and returns the combined value,
    preserving the original date format.

    :param date_str: Date string (e.g. "2026-04-02" or "02/04/2026")
    :param time_str: Time string in HH:MM format (default "00:00")
    :return: Combined datetime string with the same date format as the input
    """
    parsed_date = None
    matched_fmt = None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            matched_fmt = fmt
            break
        except ValueError:
            continue

    if parsed_date is None:
        raise ValueError(f"Unrecognized date format: {date_str}")

    parsed_time = datetime.strptime(time_str, "%H:%M")
    combined = parsed_date.replace(hour=parsed_time.hour, minute=parsed_time.minute)
    return combined.strftime(f"{matched_fmt} %H:%M")


def convert_to_uppercase(value):
    return str(value).upper()

def remove_chars(value, n='0'):
    n = int(n)
    if n > 0:
        return str(value)[n:]
    elif n < 0:
        return str(value)[:n]
    return str(value)

def get_random_ne_facility_license():
    """Get a random License Number from all_NE_facilities.xlsx."""
    try:
        df = _get_cached_excel_data('resources/all_NE_facilities.xlsx', usecols=['LicenseNumber'])

        if df is not None:
            if isinstance(df, dict):
                df = list(df.values())[0]

            if hasattr(df, 'columns') and 'LicenseNumber' in df.columns:
                license_values = df['LicenseNumber'].dropna().astype(str).tolist()
                if license_values:
                    return random.choice(license_values)
                else:
                    return "No LicenseNumber values found in data"
            else:
                return f"Column 'LicenseNumber' not found. Columns: {getattr(df, 'columns', 'N/A')}"
        else:
            return "Failed to load Excel file"

    except Exception as e:
        return f"Error reading file: {e}"


def get_random_consultation_tariff_code():
    """Get random CPT code from cached data"""
    try:
        df = _get_cached_excel_data('resources/consultation mandatory tarrif.xlsx', usecols=['CODE'])
        if df is not None:
            # Make sure it's a DataFrame, not a dict
            if isinstance(df, dict):
                # If somehow we got multiple sheets, take the first one
                df = list(df.values())[0]
        if hasattr(df, 'columns') and 'CODE' in df.columns:
            values = df['CODE'].dropna().tolist()
            if values:
                return random.choice(values)
            return "No CODE values found in data"
        return f"Column 'CODE' not found. Columns: {getattr(df, 'columns', 'N/A')}"
    except Exception as e:
        return f"Error reading file: {e}"













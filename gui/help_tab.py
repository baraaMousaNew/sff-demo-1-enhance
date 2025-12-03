"""
Comprehensive Batch Testing Documentation
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from utils.variable_processor import VariableProcessor
import inspect
import functions.custom_functions as custom_functions

class HelpTab:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.variable_processor = VariableProcessor()
        self.create_widgets()

    def create_widgets(self):
        """Create comprehensive batch testing documentation"""
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create notebook for different batch testing sections
        help_notebook = ttk.Notebook(main_frame)
        help_notebook.pack(fill=tk.BOTH, expand=True)

        # Batch Testing Overview
        self.create_batch_overview_tab(help_notebook)

        # Excel Structure & Configuration
        self.create_excel_structure_tab(help_notebook)

        # Variable System & Processing
        self.create_variable_system_tab(help_notebook)

        # Custom Functions Reference
        self.create_custom_functions_tab(help_notebook)

        # Request Mapping & Flow
        self.create_request_mapping_tab(help_notebook)

        # XML Processing & Encoding
        self.create_xml_processing_tab(help_notebook)

        # Dual System Testing
        self.create_dual_system_tab(help_notebook)

        # Allure Reporting
        # self.create_allure_reporting_tab(help_notebook)

        # Complete Examples
        # self.create_complete_examples_tab(help_notebook)

        # Troubleshooting
        # self.create_troubleshooting_tab(help_notebook)

    def create_batch_overview_tab(self, notebook):
        """Create batch testing overview documentation"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Batch Testing Overview")

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        overview_content = """
═══════════════════════════════════════════════════════════════════════════════
                        BATCH TESTING COMPREHENSIVE GUIDE
═══════════════════════════════════════════════════════════════════════════════

WHAT IS BATCH TESTING?

Batch testing allows you to execute multiple SOAP API test cases automatically from 
Excel files. It's designed for regression testing, integration testing, and 
validating business rules across different systems.

KEY FEATURES:
• Excel-driven test execution
• Variable processing and substitution
• Multi-step test workflows with response extraction
• Dual-system comparison testing (legacy vs new)
• Allure HTML reporting with comprehensive analytics
• Error validation and business rule checking
• Base64 XML encoding support
• Custom function integration

═══════════════════════════════════════════════════════════════════════════════

BATCH TESTING ARCHITECTURE:

1. EXCEL TEST CASES
   ↓ Load test data from Excel sheets
   
2. VARIABLE PROCESSING
   ↓ Replace {{variables}} with actual values
   
3. REQUEST MAPPING
   ↓ Map transaction types to request handlers
   
4. XML TEMPLATE GENERATION
   ↓ Create XML requests using decorator pattern
   
5. DUAL SYSTEM EXECUTION
   ↓ Send requests to old and/or new systems
   
6. RESPONSE VALIDATION
   ↓ Extract values, validate errors, run assertions
   
7. ALLURE REPORTING
   ↓ Generate comprehensive HTML reports

═══════════════════════════════════════════════════════════════════════════════

SUPPORTED TRANSACTION TYPES:

The framework supports five main healthcare transaction workflows:

1. PERSON REGISTER
   • Basic patient registration
   • Single-step transaction
   • Foundation for other workflows

2. PRIOR REQUEST  
   • Requires person registration first
   • Two-step workflow: register → prior request
   • Used for authorization requests

3. PRIOR AUTHORIZATION
   • Three-step workflow: register → prior request → authorization
   • Complex dependency chain
   • Validates authorization logic

4. CLAIM SUBMISSION
   • Three-step workflow: register → prior request → claim submission
   • Healthcare claim processing
   • Business rule validation

5. REMITTANCE ADVICE
   • Four-step workflow: register → prior → claim → remittance
   • Complete claim lifecycle
   • Final settlement processing

═══════════════════════════════════════════════════════════════════════════════

EXECUTION MODES:

SINGLE SYSTEM MODE (system1_only):
• Tests against legacy system only
• Used for baseline validation
• Faster execution
• Good for debugging

DUAL SYSTEM MODE (both_systems - default):
• Tests both legacy and new systems
• Compares responses automatically
• Regression testing
• Validates migration accuracy

═══════════════════════════════════════════════════════════════════════════════

REPORTING OPTIONS:

EXCEL RESULTS:
• Traditional Excel output
• Test results in tabular format
• Error details in separate columns
• Good for quick analysis

ALLURE HTML REPORTS:
• Rich interactive reports
• Timeline views
• Request/response attachments
• Advanced analytics
• Professional presentation
• Trend analysis across runs

═══════════════════════════════════════════════════════════════════════════════

PARALLEL EXECUTION:

The framework supports parallel test execution using pytest-xdist:
• Multiple test cases run simultaneously
• Worker distribution for speed
• Thread-safe variable processing
• Improved performance for large test suites

Configuration:
• Set worker count in execution settings
• Automatic load balancing
• Independent test isolation

═══════════════════════════════════════════════════════════════════════════════

BATCH TESTING WORKFLOW:

1. PREPARE EXCEL FILE
   • Define test cases with required columns
   • Set up variable definitions
   • Configure response extraction rules
   • Add assertion definitions

2. CONFIGURE EXECUTION
   • Select Excel file and sheets
   • Choose execution mode (single/dual system)
   • Set reporting preferences
   • Configure parallel settings

3. RUN TESTS
   • Framework loads and validates Excel data
   • Variables are processed for each test case
   • Requests are mapped to appropriate handlers
   • XML templates are generated with decorators
   • API calls are executed against configured systems
   • Responses are validated and errors extracted

4. ANALYZE RESULTS
   • Review Excel results or Allure reports
   • Identify failed tests and error patterns
   • Compare system behaviors in dual mode
   • Track regression trends over time

═══════════════════════════════════════════════════════════════════════════════

INTEGRATION FEATURES:

ERROR VALIDATION:
• Automatic extraction of Base64 error reports
• CSV parsing of error details
• Business rule validation
• Expected vs actual error comparison

RESPONSE EXTRACTION:
• Capture values from API responses
• Use extracted values in subsequent tests
• Multi-step test case support
• Variable persistence within test cases

ASSERTION TESTING:
• Define pass/fail criteria for responses
• Multiple assertion types available
• Integration with extracted variables
• Detailed validation reporting

═══════════════════════════════════════════════════════════════════════════════

NEXT STEPS:

→ Review "Excel Structure" tab for file format requirements
→ Check "Variable System" tab for dynamic content processing  
→ Explore "Custom Functions" tab for available helper functions
→ Understand "Request Mapping" tab for transaction workflows
→ Learn "XML Processing" tab for template handling
→ Configure "Dual System Testing" for regression validation
→ Set up "Allure Reporting" for comprehensive analytics

This comprehensive framework enables automated, scalable SOAP API testing with 
professional reporting and advanced validation capabilities.
"""

        text.insert("1.0", overview_content)
        text.configure(state='disabled')

    def create_excel_structure_tab(self, notebook):
        """Create Excel structure documentation"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Excel Structure")

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        excel_content = """
═══════════════════════════════════════════════════════════════════════════════
                            EXCEL FILE STRUCTURE GUIDE
═══════════════════════════════════════════════════════════════════════════════

REQUIRED COLUMNS:

These columns MUST be present for batch testing to work:

TC ID:
• Unique test case identifier
• Used for tracking and reporting
• Example: TEST_001, REG_001, CLAIM_123

Transaction Type:
• Defines which request handler to use
• Supported values:
  - "person register"
  - "prior request" 
  - "prior authorization"
  - "claim submission"
  - "remittance advice"

Rule ID:
• Business rule identifier for validation
• Used in error checking and assertions
• Example: RULE_001, BR_PATIENT_001

Test Data:
• Live data values for XML processing
• Format: key=value;key2=value2
• Example: patient_id=12345;claim_type=inpatient

Name:
• Human-readable test case name
• Used in reports and documentation
• Example: "Valid Patient Registration"

Description:
• Detailed test case description
• Explains test purpose and expected behavior
• Used in Allure reports

Objective (Expected Result):
• Expected test outcome (Pass/Fail)
• Controls error validation logic
• Values: "Pass", "Fail", or detailed description

═══════════════════════════════════════════════════════════════════════════════

OPTIONAL COLUMNS:

Variable_Definitions:
• Define reusable variables for the test case
• Format: var_name={{FUNCTION()}};var2={{CUSTOM.func()}}
• Example: txn_ref={{CUSTOM.generate_transaction_ref()}};batch_id={{RUN_ID()}}

XML_Body:
• Main XML content for the request
• Supports all variable types and substitutions
• Can reference Raw_XML_* encoded content

Raw_XML_* Columns:
• Any column starting with "Raw_XML_" (e.g., Raw_XML_Patient)
• Contains XML that gets Base64 encoded
• Supports variable processing before encoding
• Placeholder: {{ENCODED_XML_Patient}} in main XML

Response_Extraction:
• Rules for extracting values from API responses
• Format: var_name=extraction_pattern;var2=pattern2
• Example: patient_id=PatientID;status=StatusCode

Assertions:
• Validation rules for response content
• Format: type:element:expected_value;type2:element2:value2
• Example: exists:PatientID;equals:StatusCode:0

System1_Endpoint_URL / System2_Endpoint_URL:
• Override default system URLs for specific tests
• Useful for testing different environments
• Example: https://dev-api.example.com/soap

Execute:
• Controls whether test case should run
• Values: TRUE (run), FALSE (skip), blank (run)
• Useful for temporarily disabling tests

Priority:
• Test case priority level
• Used for organizing and filtering tests
• Values: High, Medium, Low, Critical

Notes:
• Additional information about the test case
• Troubleshooting notes, references, etc.
• Appears in reports for context

Extracted_Variables:
• Auto-populated during execution
• Shows values captured from responses
• Read-only - managed by framework

═══════════════════════════════════════════════════════════════════════════════

MULTI-SHEET SUPPORT:

The framework supports multiple Excel sheets in a single file:

CONFIGURATION:
• Select specific sheets to test: "Sheet1,Sheet2,Sheet3"
• Each sheet can have different test categories
• Common use cases:
  - Smoke_Tests (critical functionality)
  - Regression_Tests (full suite)
  - Error_Tests (negative scenarios)

SHEET NAMING CONVENTIONS:
• Use descriptive names: "Patient_Registration", "Claim_Processing"
• Avoid spaces if possible: "Patient_Reg", "Claim_Proc"
• Organize by feature or business area

═══════════════════════════════════════════════════════════════════════════════

EXCEL TEMPLATE STRUCTURE:

| TC ID    | Transaction Type | Rule ID | Name           | Description      | Test Data        | Objective |
|----------|------------------|---------|----------------|------------------|------------------|-----------|
| TEST_001 | person register  | BR_001  | Valid Patient  | Register patient | patient_id=12345 | Pass      |
| TEST_002 | person register  | BR_002  | Invalid ID     | Bad patient ID   | patient_id=      | Fail      |

EXTENDED TEMPLATE WITH VARIABLES:

| TC ID    | Variable_Definitions              | XML_Body                    | Raw_XML_Patient      |
|----------|-----------------------------------|-----------------------------|----------------------|
| TEST_001 | ref={{CUSTOM.generate_ref()}}    | <Request>{{VAR.ref}}</Req>  | <Patient>{{VAR.id}}  |
| TEST_002 | id={{RANDOM(5)}}                  | <Req>{{ENCODED_XML_Pat}}</> | <Pat>{{EXTRACT.pid}} |

═══════════════════════════════════════════════════════════════════════════════

The Excel structure provides the foundation for all batch testing operations,
supporting complex scenarios while maintaining simplicity and readability.
"""

        text.insert("1.0", excel_content)
        text.configure(state='disabled')

    def create_variable_system_tab(self, notebook):
        """Create variable system documentation"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Variable System")

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        variable_content = """
═══════════════════════════════════════════════════════════════════════════════
                          VARIABLE PROCESSING SYSTEM
═══════════════════════════════════════════════════════════════════════════════

OVERVIEW:

The variable processing system enables dynamic content generation in batch tests.
Variables are placeholders in XML that get replaced with actual values during 
execution, supporting data-driven testing and realistic test scenarios.

═══════════════════════════════════════════════════════════════════════════════

VARIABLE TYPES:

1. BUILT-IN VARIABLES:
   • System-provided functions
   • No additional setup required
   • Consistent across all tests

2. CUSTOM VARIABLES:
   • User-defined functions in custom_functions.py
   • Business-specific logic
   • Reusable across test suites

3. DECLARED VARIABLES:
   • Test-specific variables defined in Variable_Definitions
   • Calculated once per test case
   • Reusable within same test

4. EXTRACTED VARIABLES:
   • Values captured from API responses
   • Enable multi-step test workflows
   • Persist within test case scope

5. ENCODED VARIABLES:
   • Base64-encoded XML content
   • Automatic processing of Raw_XML_* columns
   • Seamless integration with main XML

═══════════════════════════════════════════════════════════════════════════════

BUILT-IN VARIABLE FUNCTIONS:

DATE FUNCTIONS:
{{DATE()}}                    - Current date (YYYY-MM-DD)
{{DATE(YYYY-MM-DD)}}         - Custom format
{{DATE(DD/MM/YYYY)}}         - Alternative format
{{DATE(MM-DD-YYYY)}}         - US format
{{DATE_TIME()}}              - Current date and time
{{DATE_TIME(YYYY-MM-DD HH:mm:ss)}} - Custom datetime format

RANDOM FUNCTIONS:
{{RANDOM()}}                 - Random 10-digit number
{{RANDOM(5)}}               - Random 5-digit number
{{RANDOM_STRING()}}         - Random alphanumeric string
{{RANDOM_STRING(8)}}        - Random 8-character string
{{RANDOM_ALPHA()}}          - Random alphabetic string
{{RANDOM_ALPHA(6)}}         - Random 6-letter string

UNIQUE IDENTIFIERS:
{{UUID()}}                  - Generate UUID v4
{{RUN_ID()}}               - Unique execution run identifier
{{TIMESTAMP()}}            - Unix timestamp
{{EPOCH()}}                - Milliseconds since epoch

SEQUENCE FUNCTIONS:
{{SEQUENCE()}}             - Auto-incrementing number (1, 2, 3...)
{{SEQUENCE(100)}}          - Start sequence at 100
{{SEQUENCE_RESET()}}       - Reset sequence counter to 1

═══════════════════════════════════════════════════════════════════════════════

DECLARED VARIABLES:

DEFINITION SYNTAX:
Variable_Definitions: var_name={{FUNCTION()}};var2={{FUNCTION2()}}

USAGE SYNTAX:
{{VAR.var_name}}

EXAMPLES:
Definition: txn_ref={{CUSTOM.generate_transaction_ref()}};patient_id={{RANDOM(8)}}
Usage: <TransactionRef>{{VAR.txn_ref}}</TransactionRef>
       <PatientID>{{VAR.patient_id}}</PatientID>

SCOPE:
• Variables are calculated once per test case
• Same value used throughout the test case
• Variables reset for each new test case

BENEFITS:
• Consistent values across multiple XML sections
• Performance optimization (calculate once)
• Easier test data management

═══════════════════════════════════════════════════════════════════════════════

EXTRACTED VARIABLES:

EXTRACTION DEFINITION:
Response_Extraction: var_name=extraction_pattern;var2=pattern2

USAGE SYNTAX:
{{EXTRACT.var_name}}

EXTRACTION PATTERNS:

1. SIMPLE ELEMENT NAME:
   patient_id=PatientID
   Extracts from: <PatientID>12345</PatientID>
   Result: {{EXTRACT.patient_id}} = "12345"

2. XPATH EXPRESSION:
   status=//StatusCode
   result=//soap:Body/ns:Response/ns:Result

3. REGEX PATTERN:
   id=regex:<ID>(.*?)</ID>
   error=regex:Error: (.+)

MULTI-STEP EXAMPLE:
Step 1: Response_Extraction: patient_id=PatientID
Step 2: XML_Body: <GetPatient><ID>{{EXTRACT.patient_id}}</ID></GetPatient>

═══════════════════════════════════════════════════════════════════════════════

ENCODED VARIABLES:

RAW_XML PROCESSING:
Raw_XML_Patient: <Patient><ID>{{VAR.patient_id}}</ID></Patient>
Raw_XML_Claim: <Claim><PatientRef>{{EXTRACT.patient_id}}</PatientRef></Claim>

AUTOMATIC PLACEHOLDERS:
{{ENCODED_XML_Patient}} - Base64 encoded content of Raw_XML_Patient
{{ENCODED_XML_Claim}}   - Base64 encoded content of Raw_XML_Claim

PROCESSING FLOW:
1. Process variables in Raw_XML_* content
2. Base64 encode the processed XML
3. Replace {{ENCODED_XML_*}} placeholders in main XML

═══════════════════════════════════════════════════════════════════════════════

VARIABLE PROCESSING ORDER:

1. DECLARE VARIABLES
   • Process Variable_Definitions column
   • Execute functions and store results
   • Variables available as {{VAR.name}}

2. PROCESS RAW XML
   • Replace variables in Raw_XML_* columns
   • Base64 encode processed content
   • Create {{ENCODED_XML_*}} placeholders

3. PROCESS MAIN XML
   • Replace all variable types in XML_Body
   • Include declared, extracted, and encoded variables
   • Generate final request XML

4. EXTRACT RESPONSES
   • Execute API call
   • Apply Response_Extraction rules
   • Store extracted values for next step

5. REPEAT FOR MULTI-STEP
   • Process next row with same TC ID
   • Extracted variables from previous steps available

═══════════════════════════════════════════════════════════════════════════════

The variable system provides powerful capabilities for dynamic test content while
maintaining simplicity and performance. It enables realistic test scenarios with
data-driven testing and multi-step workflows.
"""

        text.insert("1.0", variable_content)
        text.configure(state='disabled')

    def create_custom_functions_tab(self, notebook):
        """Create custom functions documentation with dynamic content"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Custom Functions")

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Get available custom functions dynamically
        try:
            custom_function_list = []
            for name, obj in inspect.getmembers(custom_functions):
                if inspect.isfunction(obj) and not name.startswith('_'):
                    sig = inspect.signature(obj)
                    doc = inspect.getdoc(obj) or "No documentation available"
                    custom_function_list.append(f"• {name}{sig}\n  {doc}\n")
        except Exception as e:
            custom_function_list = [f"Error loading custom functions: {str(e)}"]

        functions_text = "\n".join(custom_function_list) if custom_function_list else "No custom functions found"

        custom_functions_content = f"""
═══════════════════════════════════════════════════════════════════════════════
                            CUSTOM FUNCTIONS REFERENCE
═══════════════════════════════════════════════════════════════════════════════

OVERVIEW:

Custom functions extend the built-in variable system with business-specific logic.
They are defined in functions/custom_functions.py and provide specialized data 
generation, validation, and processing capabilities for SOAP API testing.

═══════════════════════════════════════════════════════════════════════════════

USAGE SYNTAX:

In Variable_Definitions:
var_name={{{{CUSTOM.function_name()}}}}
var_with_params={{{{CUSTOM.function_name(param1, param2)}}}}

In XML content:
<Element>{{{{CUSTOM.function_name()}}}}</Element>
<Element>{{{{VAR.custom_variable}}}}</Element>

In Test Data:
patient_id={{{{CUSTOM.generate_patient_id()}}}}

═══════════════════════════════════════════════════════════════════════════════

AVAILABLE CUSTOM FUNCTIONS:

{functions_text}

═══════════════════════════════════════════════════════════════════════════════

CREATING NEW CUSTOM FUNCTIONS:

FUNCTION TEMPLATE:
def your_function_name(param1=None, param2=None):
    \"\"\"
    Brief description of what the function does
    
    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2
        
    Returns:
        Description of return value (usually string for XML compatibility)
    \"\"\"
    try:
        # Your implementation logic here
        result = "generated_value"
        return result
    except Exception as e:
        return f"ERROR: {{str(e)}}"

BEST PRACTICES:
✓ Include comprehensive docstrings
✓ Handle errors gracefully
✓ Return string values for XML compatibility
✓ Use meaningful parameter names
✓ Validate input parameters
✓ Include usage examples in docstring

EXAMPLE IMPLEMENTATION:
def generate_patient_mrn():
    \"\"\"
    Generate a unique Medical Record Number
    
    Returns:
        str: Formatted MRN (e.g., 'MRN1234567')
    \"\"\"
    import random
    number = random.randint(1000000, 9999999)
    return f"MRN{{number}}"

def calculate_age(birth_date):
    \"\"\"
    Calculate age from birth date
    
    Args:
        birth_date (str): Birth date in YYYY-MM-DD format
        
    Returns:
        str: Age in years
    \"\"\"
    try:
        from datetime import datetime
        birth = datetime.strptime(birth_date, "%Y-%m-%d")
        today = datetime.now()
        age = today.year - birth.year
        if today.month < birth.month or (today.month == birth.month and today.day < birth.day):
            age -= 1
        return str(age)
    except Exception as e:
        return f"ERROR: Invalid date format - {{str(e)}}"

After adding functions, restart the application to load new functions.
"""

        text.insert("1.0", custom_functions_content)
        text.configure(state='disabled')

    def create_request_mapping_tab(self, notebook):
        """Create request mapping documentation"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Request Mapping & Flow")

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        request_mapping_content = """
═══════════════════════════════════════════════════════════════════════════════
                         REQUEST MAPPING & EXECUTION FLOW
═══════════════════════════════════════════════════════════════════════════════

OVERVIEW:

Request mapping translates "Transaction Type" values from Excel into specific 
request handlers and XML templates. It orchestrates complex multi-step workflows 
where later requests depend on earlier responses.

═══════════════════════════════════════════════════════════════════════════════

SUPPORTED TRANSACTION TYPES:

1. PERSON REGISTER
   Excel Value: "person register"
   Handler: PersonRegister
   Template: xml_templates/person_register_template.xml
   Dependencies: None
   Description: Basic patient registration

2. PRIOR REQUEST
   Excel Value: "prior request"
   Handler: PriorRequest
   Dependencies: Person Register (auto-executed)
   Description: Prior authorization request

3. PRIOR AUTHORIZATION
   Excel Value: "prior authorization" 
   Handler: PriorAuthorization
   Dependencies: Person Register → Prior Request (auto-executed)
   Description: Authorization approval/denial

4. CLAIM SUBMISSION
   Excel Value: "claim submission"
   Handler: ClaimSubmission
   Dependencies: Person Register → Prior Request (auto-executed)
   Description: Healthcare claim processing

5. REMITTANCE ADVICE
   Excel Value: "remittance advice"
   Handler: RemittanceAdvice
   Dependencies: Person Register → Prior Request → Claim Submission (auto-executed)
   Description: Payment/settlement notification

═══════════════════════════════════════════════════════════════════════════════

REQUEST EXECUTION FLOW:

STEP 1: REQUEST MAPPING
do_requests(transaction_type) → Returns appropriate handler class

STEP 2: TEMPLATE GENERATION
GetRequestTemplate().get_template_request(request_name, live_data, variables)

STEP 3: DECORATOR CHAIN PROCESSING
GetTemplateDecorator → Load XML template
↓
GetVariablesDecorator → Extract {{variable}} placeholders
↓
GenerateVariablesValuesDecorator → Execute functions and generate values
↓
ReplaceTemplateVariablesValuesDecorator → Replace variables with values
↓
ReplaceLiveValueDecorator → Apply test data overrides

STEP 4: REQUEST EXECUTION
SendRequestContext().send_request(system, request_handler)

STEP 5: VALIDATION
XMLAsserter(response).assert_no_errors() (for dependency steps)

═══════════════════════════════════════════════════════════════════════════════

DEPENDENCY HANDLING:

AUTOMATIC DEPENDENCY EXECUTION:
When a transaction requires dependencies, they are executed automatically:

Prior Request Flow:
1. Check if person_register_template exists
2. If not, execute Person Register request
3. Validate Person Register response (assert_no_errors)
4. Execute Prior Request with context from Person Register
5. Return Prior Request response

Prior Authorization Flow:
1. Execute Person Register (if not already done)
2. Execute Prior Request (if not already done)
3. Validate both previous responses
4. Execute Prior Authorization with accumulated context
5. Return Prior Authorization response

VARIABLE PERSISTENCE:
Variables from dependency steps are passed forward:
• Person Register generates base variables
• Prior Request inherits and adds new variables  
• Prior Authorization inherits all previous variables
• Chain continues through all dependencies

FAILURE HANDLING:
If any dependency step fails:
• assert_no_errors() throws exception
• Entire test case fails immediately
• No subsequent steps are executed
• Error details captured in reporting

═══════════════════════════════════════════════════════════════════════════════

TEMPLATE PROCESSING DECORATORS:

GET TEMPLATE DECORATOR:
Purpose: Load XML template from file
Input: Template file path (string)
Output: XML Element Tree object

GET VARIABLES DECORATOR:
Purpose: Find all {{variable}} placeholders in XML
Input: XML Element Tree
Output: List of variables with metadata

GENERATE VARIABLES VALUES DECORATOR:
Purpose: Execute functions and generate actual values
Input: Variable list with function calls
Output: Variable list with calculated values

REPLACE TEMPLATE VARIABLES VALUES DECORATOR:
Purpose: Replace {{variables}} with actual values in XML
Input: XML tree + variable values
Output: XML with variables replaced

REPLACE LIVE VALUE DECORATOR:
Purpose: Apply test-specific data overrides
Input: XML + test data from Excel
Output: Final XML with all substitutions

═══════════════════════════════════════════════════════════════════════════════

REQUEST CONTEXT MANAGEMENT:

SYSTEM SELECTION:
SendRequestContext manages which system to target:
• Systems.OLD_SYSTEM (legacy system)
• Systems.NEW_SYSTEM (re-engineered system)
• Automatic routing based on execution mode

REQUEST HANDLERS:
Each transaction type has specific send methods:
• send_request_old_system(): Legacy system implementation
• send_request_new_system(): New system implementation  

UPLOAD TRANSACTION WRAPPER:
All requests are wrapped in UploadTransaction envelope:
• Base64 encode the business XML
• Embed in UploadTransaction SOAP structure
• Set appropriate fileContent and fileName
• Extract namespace for SOAPAction header

This request mapping system provides a flexible, extensible framework for 
complex multi-step SOAP API testing with comprehensive dependency management.
"""

        text.insert("1.0", request_mapping_content)
        text.configure(state='disabled')

    def create_xml_processing_tab(self, notebook):
        """Create XML processing documentation"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="XML Processing & Encoding")

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        xml_content = """
═══════════════════════════════════════════════════════════════════════════════
                         XML PROCESSING & BASE64 ENCODING
═══════════════════════════════════════════════════════════════════════════════

OVERVIEW:

XML processing handles template loading, variable substitution, Base64 encoding, 
and SOAP envelope generation. The system supports complex XML structures with 
nested encoding and dynamic content generation.

═══════════════════════════════════════════════════════════════════════════════

XML PROCESSING PIPELINE:

1. TEMPLATE LOADING
   ↓ Load XML templates from files
   
2. VARIABLE EXTRACTION  
   ↓ Find {{variable}} placeholders
   
3. VARIABLE GENERATION
   ↓ Execute functions and generate values
   
4. RAW XML PROCESSING
   ↓ Process Raw_XML_* columns separately
   
5. BASE64 ENCODING
   ↓ Encode processed Raw XML content
   
6. MAIN XML PROCESSING
   ↓ Replace all variables including encoded content
   
7. SOAP ENVELOPE WRAPPING
   ↓ Wrap in UploadTransaction structure
   
8. FINAL XML GENERATION
   ↓ Ready for API transmission

═══════════════════════════════════════════════════════════════════════════════

XML TEMPLATE STRUCTURE:

BUSINESS LOGIC TEMPLATES:
Location: xml_templates/{transaction_type}_template.xml
Purpose: Define business data structure
Content: XML with {{variable}} placeholders

Example - person_register_template.xml:
<?xml version="1.0" encoding="utf-8"?>
<PersonRegister>
    <TransactionRef>{{CUSTOM.generate_transaction_ref()}}</TransactionRef>
    <PatientInfo>
        <FirstName>{{CUSTOM.generate_first_name()}}</FirstName>
        <LastName>{{CUSTOM.generate_last_name()}}</LastName>
        <DateOfBirth>{{DATE(YYYY-MM-DD)}}</DateOfBirth>
        <PatientID>{{RANDOM(8)}}</PatientID>
    </PatientInfo>
    <SubmissionDate>{{DATE_TIME()}}</SubmissionDate>
</PersonRegister>

UPLOAD TRANSACTION TEMPLATES:
Location: xml_templates/upload_transaction_{type}_template.xml
Purpose: SOAP envelope wrapper for API calls
Content: UploadTransaction structure with fileContent placeholder

═══════════════════════════════════════════════════════════════════════════════

VARIABLE PROCESSING IN XML:

VARIABLE TYPES IN TEMPLATES:

1. FUNCTION CALLS:
   {{CUSTOM.generate_transaction_ref()}}
   {{DATE(YYYY-MM-DD)}}
   {{RANDOM(8)}}
   {{UUID()}}

2. DECLARED VARIABLES:
   {{VAR.transaction_ref}}
   {{VAR.patient_id}}
   {{VAR.submission_date}}

3. EXTRACTED VARIABLES:
   {{EXTRACT.patient_id}}
   {{EXTRACT.transaction_id}}
   {{EXTRACT.status_code}}

4. ENCODED XML PLACEHOLDERS:
   {{ENCODED_XML_Patient}}
   {{ENCODED_XML_Claim}}
   {{ENCODED_XML_Attachment}}

PROCESSING ORDER:
1. Extract all {{}} placeholders from XML
2. Categorize by type (function, variable, etc.)
3. Execute functions and retrieve variable values
4. Replace placeholders with actual values
5. Validate resulting XML structure

═══════════════════════════════════════════════════════════════════════════════

RAW XML PROCESSING:

RAW_XML_* COLUMNS:
Any Excel column starting with "Raw_XML_" triggers special processing:

Raw_XML_Patient: Contains XML that will be Base64 encoded
Raw_XML_Claim: Contains claim data XML
Raw_XML_Attachment: Contains attachment XML

PROCESSING FLOW:
1. Identify all Raw_XML_* columns in current test case
2. Process variables within each Raw_XML_* content
3. Base64 encode the processed XML
4. Create corresponding {{ENCODED_XML_*}} placeholders
5. Replace placeholders in main XML with encoded content

EXAMPLE:
Excel Column: Raw_XML_Patient
Content: <Patient><ID>{{VAR.patient_id}}</ID><Name>{{VAR.patient_name}}</Name></Patient>

Processing:
1. Replace {{VAR.patient_id}} with actual value: "12345"
2. Replace {{VAR.patient_name}} with actual value: "John Doe"
3. Processed XML: <Patient><ID>12345</ID><Name>John Doe</Name></Patient>
4. Base64 encode: PHBhdGllbnQ+PElEPjEyMzQ1PC9JRD48TmFtZT5Kb2huIERvZTwvTmFtZT48L1BhdGllbnQ+
5. Create placeholder: {{ENCODED_XML_Patient}}

Main XML Usage:
<Request>
    <PatientData>{{ENCODED_XML_Patient}}</PatientData>
</Request>

Result:
<Request>
    <PatientData>PHBhdGllbnQ+PElEPjEyMzQ1PC9JRD48TmFtZT5Kb2huIERvZTwvTmFtZT48L1BhdGllbnQ+</PatientData>
</Request>

═══════════════════════════════════════════════════════════════════════════════

BASE64 ENCODING SYSTEM:

ENCODING PROCESS:
1. Process variables in Raw_XML_* content
2. Convert processed XML to UTF-8 bytes
3. Apply Base64 encoding
4. Return as ASCII string for XML inclusion

ENCODING FUNCTION:
def encode_xml(template):
    string_xml = ET.tostring(template).decode("utf-8")
    bytes_xml = string_xml.encode("utf-8")
    base64_xml = base64.b64encode(bytes_xml)
    base64_string_xml = base64_xml.decode("utf-8")
    return base64_string_xml

PLACEHOLDER GENERATION:
Raw_XML_Suffix → {{ENCODED_XML_Suffix}}

Examples:
Raw_XML_Patient → {{ENCODED_XML_Patient}}
Raw_XML_Claim → {{ENCODED_XML_Claim}}
Raw_XML_AttachmentData → {{ENCODED_XML_AttachmentData}}

DECODING SUPPORT:
The framework also supports decoding Base64 content:
• Manual decoding in XML Encoder tab
• Automatic decoding of response content
• Error report parsing from Base64

═══════════════════════════════════════════════════════════════════════════════

SOAP ENVELOPE PROCESSING:

UPLOAD TRANSACTION STRUCTURE:
All business XML is wrapped in UploadTransaction SOAP envelope:

<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <ns1:UploadTransaction xmlns:ns1="https://www.shafafiya.org/v2/">
            <ns1:fileName>{{generated_filename}}</ns1:fileName>
            <ns1:fileContent>{{base64_encoded_business_xml}}</ns1:fileContent>
        </ns1:UploadTransaction>
    </soap:Body>
</soap:Envelope>

NAMESPACE EXTRACTION:
Dynamic namespace and SOAPAction header generation based on template structure.

This XML processing system provides comprehensive capabilities for handling 
complex SOAP API requirements while maintaining performance and reliability.
"""

        text.insert("1.0", xml_content)
        text.configure(state='disabled')

    def create_dual_system_tab(self, notebook):
        """Create dual system testing documentation"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Dual System Testing")

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        dual_system_content = """
═══════════════════════════════════════════════════════════════════════════════
                            DUAL SYSTEM TESTING GUIDE
═══════════════════════════════════════════════════════════════════════════════

OVERVIEW:

Dual system testing enables regression testing between legacy and re-engineered 
systems. The same test cases are executed against both systems simultaneously,
with automatic comparison of responses, error patterns, and business logic results.

═══════════════════════════════════════════════════════════════════════════════

EXECUTION MODES:

SYSTEM1_ONLY MODE:
• Tests against legacy system only
• Used for baseline validation
• Faster execution for development testing
• Good for debugging test cases

Environment Variable: SOAP_EXECUTION_MODE=system1_only

DUAL_SYSTEM MODE (Default):
• Tests both legacy and new systems
• Compares responses automatically
• Full regression validation
• Identifies behavioral differences

Environment Variable: SOAP_EXECUTION_MODE=both_systems

═══════════════════════════════════════════════════════════════════════════════

SYSTEM CONFIGURATION:

SYSTEM DEFINITIONS:
Systems.OLD_SYSTEM (Value: 1) - Legacy system
Systems.NEW_SYSTEM (Value: 2) - Re-engineered system

DEFAULT CONFIGURATION:
Located: resources/system_defaults.json

{
    "old_system": {
        "url": "https://legacy-api.example.com/soap",
        "timeout": 30,
        "retry_count": 3
    },
    "new_system": {
        "url": "https://new-api.example.com/soap", 
        "timeout": 30,
        "retry_count": 3
    }
}

OVERRIDE OPTIONS:
Per-test overrides via Excel columns:
• System1_Endpoint_URL: Override legacy system URL
• System2_Endpoint_URL: Override new system URL

═══════════════════════════════════════════════════════════════════════════════

DUAL SYSTEM EXECUTION FLOW:

SINGLE SYSTEM MODE:
1. Load test case from Excel
2. Process variables and generate XML
3. Execute request against OLD_SYSTEM
4. Validate response for expected errors
5. Generate result report

DUAL SYSTEM MODE:
1. Load test case from Excel
2. Process variables and generate XML (same for both)
3. Execute request against OLD_SYSTEM
4. Validate OLD_SYSTEM response for expected errors
5. Execute same request against NEW_SYSTEM  
6. Compare responses between systems
7. Validate response consistency
8. Generate comparison report

═══════════════════════════════════════════════════════════════════════════════

REQUEST ROUTING:

CONTEXT-BASED ROUTING:
SendRequestContext handles system selection:

def send_request(self, system: Systems, request_type: SendRequest):
    if system == Systems.NEW_SYSTEM:
        return request_type.send_request_new_system()
    else:
        return request_type.send_request_old_system()

HANDLER IMPLEMENTATION:
Each request handler supports both systems with automatic fallback.

═══════════════════════════════════════════════════════════════════════════════

RESPONSE COMPARISON:

ERROR COMPARISON:
XMLAsserter(old_response).assert_responses_errors(new_response)

Compares:
• Error report presence (both should have or both should not have)
• Error count consistency
• Error type matching (ERROR vs WARNING)
• Rule ID consistency
• Error message patterns

BUSINESS RULE VALIDATION:
Test cases specify expected outcome in "Objective" column:

PASS TEST CASES:
Objective: "Pass" or similar
Validation: XMLAsserter(response).assert_error_doesnt_exist(rule_id)
Expected: No errors with specified Rule ID

FAIL TEST CASES:
Objective: "Fail" or error description
Validation: XMLAsserter(response).assert_error_exists(rule_id)
Expected: Specific error with Rule ID present

DUAL SYSTEM CONSISTENCY:
Both systems should:
• Pass the same test cases
• Fail the same test cases with same errors
• Return consistent business logic results
• Handle edge cases identically

═══════════════════════════════════════════════════════════════════════════════

PARALLEL EXECUTION:

PYTEST-XDIST INTEGRATION:
The framework supports parallel execution with proper worker coordination.

WORKER COORDINATION:
• Each worker gets same test parameterization
• Pytest-xdist distributes tests automatically
• Independent execution per worker
• Results aggregated in final report

THREAD SAFETY:
• Variable processor isolated per test
• Request context managed per execution
• No shared state between workers
• Independent system connections

PERFORMANCE BENEFITS:
• Faster execution with multiple workers
• Better resource utilization
• Reduced total execution time
• Parallel system comparison

═══════════════════════════════════════════════════════════════════════════════

The dual system testing framework provides comprehensive regression validation
capabilities ensuring successful system migrations with minimal risk and
maximum confidence in behavioral consistency.
"""

        text.insert("1.0", dual_system_content)
        text.configure(state='disabled')

    def create_allure_reporting_tab(self, notebook):
        """Create Allure reporting documentation"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Allure Reporting")

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        allure_content = """
═══════════════════════════════════════════════════════════════════════════════
                           ALLURE REPORTING SYSTEM
═══════════════════════════════════════════════════════════════════════════════

OVERVIEW:

Allure provides professional-grade HTML reporting for batch test execution.
It creates interactive reports with timeline views, detailed test analysis,
request/response attachments, and comprehensive analytics for both single
and dual-system testing scenarios.

═══════════════════════════════════════════════════════════════════════════════

ALLURE INTEGRATION ARCHITECTURE:

PYTEST INTEGRATION:
The framework integrates with pytest through allure-pytest plugin:
• @allure.feature() - Categorizes tests by functionality
• @allure.story() - Groups related test scenarios
• allure.step() - Documents test execution steps
• allure.attach() - Adds files and content to reports

ALLURE WRAPPER:
utils/allure_wrapper.py provides pytest-compatible test execution:
• Converts Excel test cases to pytest parameters
• Manages xdist parallel execution
• Handles dual-system test orchestration
• Integrates with existing framework components

REPORTING COMPONENTS:
• AllureReporter - Framework reporting interface
• AssertionAllureWrapper - Assertion-specific reporting  
• Built-in pytest fixtures for test metadata
• Automatic attachment generation

═══════════════════════════════════════════════════════════════════════════════

REPORT GENERATION PROCESS:

EXECUTION PHASE:
1. Load Excel test cases
2. Convert to pytest parameterized tests  
3. Execute tests with allure data collection
4. Generate raw results in allure-results/ directory

REPORT GENERATION PHASE:
1. Process raw allure results
2. Generate HTML report in allure-report/ directory
3. Create interactive web interface
4. Launch browser for report viewing

COMMAND LINE EXECUTION:
# Execute tests with Allure
pytest --alluredir=allure-results test_file.py

# Generate HTML report
allure generate allure-results --clean -o allure-report

# Serve report (optional)
allure serve allure-results

═══════════════════════════════════════════════════════════════════════════════

REPORT STRUCTURE:

OVERVIEW DASHBOARD:
• Total test count and pass/fail statistics
• Execution duration and performance metrics
• Test category breakdown
• Trend analysis across multiple runs

CATEGORIES:
• Feature-based organization (SOAP API Testing)
• Story-based grouping (Dual System Comparison)
• Severity levels (Critical, Normal, Minor)
• Custom labels and tags

TIMELINE VIEW:
• Test execution timeline with parallel workers
• Duration analysis and bottleneck identification
• System response time comparison
• Resource utilization patterns

BEHAVIORS:
• Epic and feature organization
• User story mapping
• Requirement traceability
• Business scenario coverage

PACKAGES:
• Test module organization
• Package-level statistics
• Code coverage integration
• Test distribution analysis

═══════════════════════════════════════════════════════════════════════════════

TEST EXECUTION DETAILS:

TEST CASE INFORMATION:
Each test case includes:
• Test ID and description from Excel
• Execution timestamp and duration
• Worker ID for parallel execution tracking
• System execution mode (single/dual)

EXECUTION STEPS:
Detailed step breakdown with attachments:
• Template processing steps
• Variable generation and replacement
• Request execution for each system
• Response validation and error checking
• Assertion execution and results

ATTACHMENTS:
Rich content attached to each test:
• Original Excel test case data
• Processed XML templates
• Request XML sent to systems
• Response XML from systems
• Error reports and validation results
• Variable processing details

ENVIRONMENT INFORMATION:
• System configuration details
• Endpoint URLs and settings
• Execution parameters
• Worker distribution details

═══════════════════════════════════════════════════════════════════════════════

DUAL SYSTEM REPORTING:

SYSTEM COMPARISON:
For dual-system tests, reports include:
• Side-by-side system execution details
• Request/response pairs for both systems
• Response comparison results
• Error pattern analysis
• Performance comparison metrics

REGRESSION ANALYSIS:
• Behavioral difference detection
• Error consistency validation
• Performance deviation analysis
• Business rule compliance checking

SYSTEM-SPECIFIC DETAILS:
Each system execution tracked separately:
• Individual request/response attachments
• System-specific error reports
• Performance metrics per system
• Validation results per system

COMPARATIVE ATTACHMENTS:
• Response difference analysis
• Error report comparisons
• Performance benchmarking
• Consistency validation results

═══════════════════════════════════════════════════════════════════════════════

PARALLEL EXECUTION REPORTING:

XDIST INTEGRATION:
pytest-xdist parallel execution support:
• Multiple worker coordination
• Test distribution visualization
• Worker-specific reporting
• Load balancing analysis

WORKER TRACKING:
Each test execution includes:
• Worker ID identification
• Test distribution patterns
• Execution timeline per worker
• Resource utilization per worker

PERFORMANCE ANALYSIS:
• Parallel execution efficiency
• Worker utilization patterns
• Bottleneck identification
• Scalability assessment

═══════════════════════════════════════════════════════════════════════════════

CUSTOMIZATION OPTIONS:

REPORT THEMES:
• Multiple visual themes available
• Custom branding options
• Logo and color customization
• Layout configuration

FILTERING AND SEARCH:
• Advanced filtering options
• Full-text search capabilities
• Category-based filtering
• Time-range selection

EXPORT OPTIONS:
• PDF report generation
• Excel data export
• JSON raw data export
• CSV summary reports

INTEGRATION FEATURES:
• CI/CD pipeline integration
• Email report distribution
• Slack/Teams notifications
• JIRA integration for failures

═══════════════════════════════════════════════════════════════════════════════

The Allure reporting system provides comprehensive, professional-grade test
reporting that enables effective analysis, debugging, and communication of
batch testing results across development and business stakeholders.
"""

        text.insert("1.0", allure_content)
        text.configure(state='disabled')

    def create_complete_examples_tab(self, notebook):
        """Create complete examples documentation"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Complete Examples")

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        examples_content = """
═══════════════════════════════════════════════════════════════════════════════
                          COMPLETE BATCH TESTING EXAMPLES
═══════════════════════════════════════════════════════════════════════════════

EXAMPLE 1: BASIC PATIENT REGISTRATION

EXCEL TEST CASE:
TC ID: PAT_REG_001
Transaction Type: person register
Rule ID: BR_PATIENT_VALID
Name: Valid Patient Registration
Description: Register a new patient with valid demographics and insurance
Test Data: patient_type=individual;insurance_class=A;coverage_type=full
Variable_Definitions: ref={{CUSTOM.generate_transaction_ref()}};batch_id={{RUN_ID()}}
XML_Body: (blank - uses template)
Response_Extraction: patient_id=PatientID;registration_status=RegistrationResult
Assertions: exists:PatientID;equals:RegistrationResult:0
Objective: Pass
Priority: High
Execute: TRUE

EXPECTED EXECUTION FLOW:
1. Load person_register_template.xml
2. Process variables: ref and batch_id generated
3. Apply test data: patient_type, insurance_class, coverage_type
4. Generate final XML with substituted values
5. Wrap in UploadTransaction envelope
6. Send to configured system(s)
7. Extract patient_id and registration_status from response
8. Validate assertions: PatientID exists and RegistrationResult equals 0
9. Generate success report

═══════════════════════════════════════════════════════════════════════════════

EXAMPLE 2: MULTI-STEP CLAIM PROCESSING

EXCEL TEST CASE - STEP 1 (Patient Registration):
TC ID: CLAIM_PROC_001
Transaction Type: person register
Rule ID: BR_PATIENT_VALID
Name: Patient Registration for Claim Processing
Description: Create patient before claim submission
Test Data: patient_type=individual;insurance_class=A
Variable_Definitions: patient_ref={{CUSTOM.generate_patient_ref()}};batch={{RUN_ID()}}
Response_Extraction: patient_id=PatientID;reg_status=RegistrationResult
Assertions: exists:PatientID;equals:RegistrationResult:0
Objective: Pass

EXCEL TEST CASE - STEP 2 (Claim Submission):
TC ID: CLAIM_PROC_001
Transaction Type: claim submission
Rule ID: BR_CLAIM_VALID
Name: Submit Claim for Registered Patient
Description: Submit medical claim using patient ID from previous step
Test Data: claim_type=inpatient;service_date=2024-10-31;amount=1500.00
Variable_Definitions: claim_ref={{CUSTOM.generate_claim_ref()}};submit_date={{DATE()}}
XML_Body: <Claim><PatientRef>{{EXTRACT.patient_id}}</PatientRef><Type>{{claim_type}}</Type></Claim>
Response_Extraction: claim_id=ClaimID;claim_status=ClaimResult
Assertions: exists:ClaimID;equals:ClaimResult:0;contains:ClaimResponse:{{EXTRACT.patient_id}}
Objective: Pass

EXECUTION FLOW:
1. Execute Step 1 - Patient Registration
   • Process variables and test data
   • Submit patient registration
   • Extract patient_id and reg_status
   • Validate patient creation successful

2. Execute Step 2 - Claim Submission  
   • Execute person register dependency automatically
   • Execute prior request dependency automatically
   • Process variables including {{EXTRACT.patient_id}}
   • Submit claim with patient reference
   • Extract claim_id and claim_status
   • Validate claim submission and patient ID reference

═══════════════════════════════════════════════════════════════════════════════

EXAMPLE 3: COMPLEX BASE64 ENCODING SCENARIO

EXCEL TEST CASE:
TC ID: ENC_COMPLEX_001
Transaction Type: claim submission
Rule ID: BR_ATTACHMENT_VALID
Name: Claim with Base64 Encoded Attachments
Description: Submit claim with multiple encoded XML attachments
Test Data: claim_type=outpatient;attachment_count=2
Variable_Definitions: claim_ref={{CUSTOM.generate_claim_ref()}};doc_id={{UUID()}}

Raw_XML_PatientData:
<PatientDocument>
    <DocumentID>{{VAR.doc_id}}</DocumentID>
    <PatientReference>{{EXTRACT.patient_id}}</PatientReference>
    <DocumentType>Medical_Record</DocumentType>
    <CreationDate>{{DATE_TIME()}}</CreationDate>
</PatientDocument>

Raw_XML_ClaimDetail:
<ClaimDetails>
    <ClaimReference>{{VAR.claim_ref}}</ClaimReference>
    <ServiceDate>{{DATE()}}</ServiceDate>
    <ServiceCode>{{CUSTOM.generate_service_code()}}</ServiceCode>
    <Amount>{{CUSTOM.calculate_service_amount()}}</Amount>
</ClaimDetails>

XML_Body:
<ComplexClaim>
    <ClaimHeader>
        <Reference>{{VAR.claim_ref}}</Reference>
        <SubmissionDate>{{DATE_TIME()}}</SubmissionDate>
    </ClaimHeader>
    <EncodedPatientData>{{ENCODED_XML_PatientData}}</EncodedPatientData>
    <EncodedClaimData>{{ENCODED_XML_ClaimDetail}}</EncodedClaimData>
</ComplexClaim>

PROCESSING FLOW:
1. Process variables in Raw_XML_PatientData
2. Base64 encode processed patient data
3. Process variables in Raw_XML_ClaimDetail  
4. Base64 encode processed claim detail
5. Process main XML_Body with encoded placeholders
6. Generate final XML with all encoded content
7. Submit complex claim with attachments

═══════════════════════════════════════════════════════════════════════════════

EXAMPLE 4: DUAL SYSTEM REGRESSION TESTING

EXCEL CONFIGURATION:
TC ID: DUAL_REG_001
Transaction Type: prior authorization
Rule ID: BR_AUTH_WORKFLOW
Name: Authorization Workflow Regression Test
Description: Compare authorization logic between old and new systems
Test Data: authorization_type=inpatient;urgency=routine;amount=5000.00
Variable_Definitions: auth_ref={{CUSTOM.generate_auth_ref()}};req_date={{DATE()}}
System1_Endpoint_URL: https://legacy-api.healthcare.com/soap
System2_Endpoint_URL: https://new-api.healthcare.com/soap
Response_Extraction: auth_id=AuthorizationID;auth_result=AuthorizationResult
Assertions: exists:AuthorizationID;equals:AuthorizationResult:0
Objective: Pass

EXECUTION MODES:

Single System (system1_only):
1. Execute against legacy system only
2. Validate business rules against legacy behavior
3. Generate baseline results
4. Use for test development and debugging

Dual System (both_systems):
1. Execute person register → prior request → prior authorization on legacy
2. Validate each step succeeds on legacy system
3. Execute same workflow on new system
4. Compare responses between systems:
   • Same authorization result codes
   • Same error patterns (if any)
   • Consistent business logic application
   • Similar response structure
5. Generate comparison report

EXPECTED DUAL SYSTEM BEHAVIOR:
• Both systems should approve/deny consistently
• Error reports should contain same rule violations
• Response timing should be comparable
• Business logic should produce identical outcomes

═══════════════════════════════════════════════════════════════════════════════

EXAMPLE 5: ERROR VALIDATION TESTING

NEGATIVE TEST CASE:
TC ID: ERR_VAL_001
Transaction Type: person register
Rule ID: BR_PATIENT_INVALID_ID
Name: Invalid Patient ID Validation
Description: Test that system properly validates patient ID format
Test Data: patient_id=INVALID_ID_FORMAT;insurance_class=A
Variable_Definitions: ref={{CUSTOM.generate_transaction_ref()}}
Expected_Errors: BR_PATIENT_INVALID_ID
Response_Extraction: error_code=ErrorCode;error_message=ErrorMessage
Assertions: exists:ErrorCode;equals:ErrorCode:-1;contains:ErrorMessage:Invalid
Objective: Fail

EXPECTED EXECUTION:
1. Submit patient registration with invalid ID format
2. System should reject registration
3. Extract error report from response (Base64 decoded)
4. Validate that BR_PATIENT_INVALID_ID error is present
5. Confirm error message contains appropriate details
6. Verify response indicates failure (ErrorCode: -1)

ERROR VALIDATION LOGIC:
• Decode Base64 error report from response
• Parse CSV error data
• Locate error with Rule ID: BR_PATIENT_INVALID_ID
• Verify error type is "ERROR" (not "WARNING")
• Confirm error was expected based on test objective

═══════════════════════════════════════════════════════════════════════════════

These examples demonstrate the full power and flexibility of the batch testing
framework, enabling comprehensive SOAP API validation with professional
reporting and advanced debugging capabilities.
"""

        text.insert("1.0", examples_content)
        text.configure(state='disabled')

    def create_troubleshooting_tab(self, notebook):
        """Create troubleshooting documentation"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Troubleshooting")

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        troubleshooting_content = """
═══════════════════════════════════════════════════════════════════════════════
                           TROUBLESHOOTING GUIDE
═══════════════════════════════════════════════════════════════════════════════

EXCEL FILE ISSUES:

PROBLEM: "Column not found" or "Missing required columns" errors
DIAGNOSIS:
1. Check that all required columns are present:
   • TC ID, Transaction Type, Rule ID, Name, Description, Objective
2. Verify column names match exactly (case-sensitive)
3. Check for extra spaces in column headers
4. Ensure columns are in header row (row 1)

RESOLUTION:
✓ Add missing required columns
✓ Fix column name spelling and case
✓ Remove extra spaces from headers
✓ Verify Excel file structure matches template

PROBLEM: "Empty TC ID" or "Invalid Transaction Type" errors
DIAGNOSIS:
1. Check for empty TC ID cells
2. Verify Transaction Type values match supported types:
   • "person register", "prior request", "prior authorization"
   • "claim submission", "remittance advice"
3. Look for typos in Transaction Type column

RESOLUTION:
✓ Fill in all TC ID values
✓ Use exact Transaction Type spellings
✓ Remove leading/trailing spaces
✓ Use consistent naming conventions

═══════════════════════════════════════════════════════════════════════════════

VARIABLE PROCESSING ISSUES:

PROBLEM: Variables not being replaced ({{VAR.name}} appears in final XML)
DIAGNOSIS:
1. Check variable definition syntax in Variable_Definitions:
   ✗ var={{FUNCTION()}} (missing closing brace)
   ✓ var={{FUNCTION()}}
2. Verify variable usage syntax:
   ✗ {{var.name}} (wrong case)
   ✓ {{VAR.name}}
3. Check for circular references
4. Validate function names and parameters

RESOLUTION:
✓ Fix syntax errors in variable definitions
✓ Use correct variable reference format
✓ Avoid circular variable dependencies
✓ Test variables in Manual Testing tab first

PROBLEM: Custom functions not working
DIAGNOSIS:
1. Verify function exists in functions/custom_functions.py
2. Check function name spelling and case
3. Validate function parameters
4. Test function execution independently

RESOLUTION:
✓ Import custom functions module properly
✓ Use exact function names
✓ Provide correct parameter types
✓ Add error handling to custom functions

═══════════════════════════════════════════════════════════════════════════════

XML PROCESSING ISSUES:

PROBLEM: XML syntax errors or malformed XML
DIAGNOSIS:
1. Validate XML structure in XML Encoder tab
2. Check for unescaped special characters
3. Look for missing closing tags
4. Verify namespace declarations

RESOLUTION:
✓ Use XML validation tools
✓ Escape special characters: &lt; &gt; &amp;
✓ Balance opening and closing tags
✓ Use proper namespace prefixes

PROBLEM: Base64 encoding issues
DIAGNOSIS:
1. Check Raw_XML_* column names match placeholders
2. Verify Raw_XML content has valid XML structure
3. Test encoding manually in XML Encoder tab
4. Check for character encoding issues

RESOLUTION:
✓ Match Raw_XML column names to placeholders exactly
✓ Validate Raw_XML content before encoding
✓ Use UTF-8 character encoding consistently
✓ Test encoding process in isolation

═══════════════════════════════════════════════════════════════════════════════

NETWORK AND CONNECTIVITY ISSUES:

PROBLEM: Connection timeouts or network errors
DIAGNOSIS:
1. Test connectivity to endpoint URLs manually
2. Check firewall and proxy settings
3. Verify DNS resolution
4. Test with different timeout values

RESOLUTION:
✓ Verify endpoint URLs are accessible
✓ Configure firewall exceptions
✓ Use appropriate proxy settings
✓ Increase timeout values if needed
✓ Implement retry logic for transient failures

PROBLEM: Authentication or authorization failures
DIAGNOSIS:
1. Verify credentials are correct
2. Check authentication method (Basic, OAuth, etc.)
3. Test authentication manually
4. Validate token expiration

RESOLUTION:
✓ Update credentials in configuration
✓ Use correct authentication method
✓ Implement token refresh logic
✓ Test authentication independently

═══════════════════════════════════════════════════════════════════════════════

DUAL SYSTEM TESTING ISSUES:

PROBLEM: Response comparison failures
DIAGNOSIS:
1. Compare responses manually
2. Check for timing-dependent data
3. Verify data synchronization between systems
4. Look for environment-specific differences

RESOLUTION:
✓ Synchronize reference data between systems
✓ Handle timing-dependent fields appropriately
✓ Use normalized comparison logic
✓ Account for acceptable differences

PROBLEM: One system fails while other succeeds
DIAGNOSIS:
1. Check system configurations
2. Verify same input data to both systems
3. Compare system versions and updates
4. Review business rule implementations

RESOLUTION:
✓ Align system configurations
✓ Ensure consistent input data
✓ Update systems to same version/patch level
✓ Review and align business rule logic

═══════════════════════════════════════════════════════════════════════════════

DEBUGGING TECHNIQUES:

ISOLATION TESTING:
• Test individual components separately
• Use Manual Testing tab for single requests
• Test variable processing in isolation
• Validate XML generation step by step

LOGGING AND MONITORING:
• Enable detailed logging
• Monitor resource usage
• Track execution timing
• Review error logs systematically

PREVIEW FEATURES:
• Use Preview Variables functionality
• Test XML processing before execution
• Validate encoding/decoding manually
• Review processed content before sending

STEP-BY-STEP DEBUGGING:
1. Start with simplest test case
2. Add complexity incrementally
3. Test each component individually
4. Validate assumptions at each step

═══════════════════════════════════════════════════════════════════════════════

DIAGNOSTIC TOOLS:

BUILT-IN TOOLS:
• Manual Testing tab
• XML Encoder tab
• Preview Variables functionality
• Error files output

EXTERNAL TOOLS:
• XML validators (online or standalone)
• Base64 encoders/decoders
• Network connectivity tools (ping, telnet)
• HTTP clients (Postman, curl)

LOG FILES:
• Framework execution logs
• System error logs
• Network access logs
• Application performance logs

PREVENTION STRATEGIES:
✓ Test with minimal examples first
✓ Validate Excel structure before large runs
✓ Test connectivity before batch execution
✓ Use version control for test configurations

This troubleshooting guide provides systematic approaches to identifying and
resolving issues in batch testing scenarios, enabling efficient problem
resolution and continuous improvement of testing processes.
"""

        text.insert("1.0", troubleshooting_content)
        text.configure(state='disabled')
"""
Variable Processor - Enhanced with response value extraction capabilities
"""

import re
import string
import uuid
import random
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import importlib.util
import os

from utils.template_generator.health_check.health_checker import HealthChecker


class VariableProcessor:
    # Class-level cache — loaded once per worker process, never re-executed on subsequent instantiations.
    _cached_custom_functions = None
    _custom_functions_loaded = False

    def __init__(self):
        self.run_id = None
        self.test_index = 0
        self.sequences = {}
        self.declared_variables = {}  # Store declared variables for reuse
        self.extracted_variables = {}  # Store values extracted from responses
        self.load_custom_functions()

    @property
    def custom_functions(self):
        return VariableProcessor._cached_custom_functions

    @custom_functions.setter
    def custom_functions(self, value):
        VariableProcessor._cached_custom_functions = value

    def load_custom_functions(self):
        """Load custom functions from functions/custom_functions.py — only once per process."""
        if VariableProcessor._custom_functions_loaded:
            return  # Already loaded — skip re-execution entirely
        try:
            custom_file_path = os.path.join("functions", "custom_functions.py")
            if os.path.exists(custom_file_path):
                spec = importlib.util.spec_from_file_location("custom_functions", custom_file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                VariableProcessor._cached_custom_functions = module
                VariableProcessor._custom_functions_loaded = True
                print(f"Loaded custom functions from {custom_file_path}")
            else:
                print(f"No custom functions file found at {custom_file_path}")
                VariableProcessor._custom_functions_loaded = True  # Don't retry on every call
        except Exception as e:
            print(f"Failed to load custom functions: {e}")
            VariableProcessor._cached_custom_functions = None
            VariableProcessor._custom_functions_loaded = True  # Mark as attempted to avoid retry loop

    def set_batch_context(self, run_id=None):
        """Set context for the entire batch run"""
        self.run_id = run_id or f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.test_index = 0
        self.sequences = {}  # Reset sequences for new batch
        self.declared_variables = {}  # Reset declared variables for new batch
        self.extracted_variables = {}  # Reset extracted variables for new batch

    def set_test_context(self, test_index):
        """Set context for current test"""
        self.test_index = test_index
        # Note: Don't reset declared_variables here as they should persist across steps within a test

    def extract_values_from_response(self, response_content, extraction_rules):
        """
        Extract values from response content using XPath or regex patterns

        Args:
            response_content (str): XML response content
            extraction_rules (str): Semicolon-separated extraction rules
                                   Format: var_name=xpath_expression;var_name2=regex_pattern

        Returns:
            dict: Extracted variable names and values
        """
        extracted = {}

        if not extraction_rules or not extraction_rules.strip():
            return extracted

        try:
            rules = extraction_rules.split(';')

            for rule in rules:
                rule = rule.strip()
                if not rule or '=' not in rule:
                    continue

                var_name, extraction_expr = rule.split('=', 1)
                var_name = var_name.strip()
                extraction_expr = extraction_expr.strip()

                try:
                    # Try XPath extraction first (for XML responses)
                    if extraction_expr.startswith('//') or extraction_expr.startswith('/'):
                        value = self._extract_by_xpath(response_content, extraction_expr)
                    # Try regex extraction
                    elif extraction_expr.startswith('regex:'):
                        regex_pattern = extraction_expr[6:]  # Remove 'regex:' prefix
                        value = self._extract_by_regex(response_content, regex_pattern)
                    # HTML-encoded inner XML extraction
                    elif extraction_expr.startswith('decoded_xml:'):
                        value = self._extract_from_decoded_xml(response_content, extraction_expr[12:])
                    # Inner XML query via >> syntax
                    elif '>>' in extraction_expr:
                        value = self._query_inner_xml(response_content, extraction_expr)
                    # Simple element name extraction (convenience method)
                    else:
                        value = self._extract_by_element_name(response_content, extraction_expr)

                    if value:
                        extracted[var_name] = value
                        # Also store in extracted_variables for future use
                        self.extracted_variables[var_name] = value
                        print(f"Extracted variable: {var_name} = {value}")
                    else:
                        print(f"No value found for extraction rule: {var_name} = {extraction_expr}")

                except Exception as e:
                    print(f"Error extracting {var_name} with rule '{extraction_expr}': {e}")

        except Exception as e:
            print(f"Error processing extraction rules: {e}")

        return extracted

    def _extract_by_xpath(self, xml_content, xpath_expression):
        """Extract value using XPath expression"""
        try:
            # Parse XML
            root = ET.fromstring(xml_content)

            # Handle namespaces by creating a namespace map
            namespaces = {}
            for prefix, uri in self._extract_namespaces(xml_content).items():
                namespaces[prefix] = uri

            # Find element using XPath
            if namespaces:
                elements = root.findall(xpath_expression, namespaces)
            else:
                elements = root.findall(xpath_expression)

            if elements:
                return elements[0].text.strip() if elements[0].text else ""

        except Exception as e:
            print(f"XPath extraction error: {e}")

        return None

    def _extract_by_regex(self, content, regex_pattern):
        """Extract value using regex pattern"""
        try:
            match = re.search(regex_pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                # Return first group if groups exist, otherwise return full match
                return match.group(1) if match.groups() else match.group(0)
        except Exception as e:
            print(f"Regex extraction error: {e}")

        return None

    def _extract_from_decoded_xml(self, xml_content: str, expression: str):
        """
        Extract a value from HTML-encoded XML embedded inside an outer element.

        Expression format:  outer_element::inner_expression
          outer_element  — element name or XPath pointing to the element whose text
                           content is the HTML-encoded inner XML (e.g. foundTransactions)
          inner_expression — one of:
            .//Tag/@Attr       attribute value from first matching element
            count(.//Tag)      number of matching elements as a string
            .//Tag             text content of first matching element

        Examples:
            foundTransactions::.//File/@IsDownloaded
            foundTransactions::count(.//File)
            foundTransactions::.//File[1]/@FileName
        """
        import html as _html
        if '::' not in expression:
            return None

        outer, inner_expr = expression.split('::', 1)
        outer = outer.strip()
        inner_expr = inner_expr.strip()

        # Extract encoded text — try XPath first, fall back to element name
        if outer.startswith('/'):
            encoded_text = self._extract_by_xpath(xml_content, outer)
            if not encoded_text:
                element_name = outer.lstrip('/').split(':')[-1]
                encoded_text = self._extract_by_element_name(xml_content, element_name)
        else:
            encoded_text = self._extract_by_element_name(xml_content, outer)

        if not encoded_text:
            return None

        decoded = _html.unescape(encoded_text).strip()
        decoded = re.sub(r'<!\[CDATA\[(.*?)]]>', lambda m: m.group(1), decoded, flags=re.DOTALL)
        if not decoded:
            return ""

        try:
            root = ET.fromstring(decoded)
        except ET.ParseError:
            try:
                root = ET.fromstring(f'<_root_>{decoded}</_root_>')
            except ET.ParseError:
                return None

        # count(...)
        count_m = re.match(r'^count\((.+)\)$', inner_expr, re.IGNORECASE)
        if count_m:
            return str(len(root.findall(count_m.group(1))))

        # attribute path  (.//Tag/@Attr  or  .//Tag[pred]/@Attr)
        attr_m = re.match(r'^(.*?)/@([A-Za-z_][\w.-]*)$', inner_expr)
        if attr_m:
            xpath_part = attr_m.group(1).strip()
            attr_name  = attr_m.group(2)
            elements   = [root] if xpath_part in ('', '.') else root.findall(xpath_part)
            if elements:
                return elements[0].get(attr_name, "")
            return None

        # text content
        elements = root.findall(inner_expr)
        if elements:
            return elements[0].text.strip() if elements[0].text else ""
        return None

    def _query_inner_xml(self, xml_content: str, selector: str):
        """
        Query HTML-encoded inner XML using the >> selector syntax.

        Selector format:
            outer_element>>Path.Element[attr1=val1,attr2=val2]
            outer_element>>Path.Element[attr1=val1,attr2=val2].AttrName

        - outer_element : element name (or XPath) whose text is HTML-encoded XML
        - Path.Element  : dot-notation path to target elements inside the decoded XML
        - [...]         : comma-separated attribute filters (single = , variables resolved)
        - .AttrName     : optional — if present, returns that attribute value from the
                          first matching element; if absent, returns the match count string

        Returns:
            str  — attribute value (AttrName mode) or count string ("0", "1", "2", …)
            None — outer element not found or parse error (AttrName mode only)
        """
        import html as _html

        if '>>' not in selector:
            return None

        outer, inner_query = selector.split('>>', 1)
        outer       = outer.strip()
        inner_query = inner_query.strip()

        # Detect optional trailing attribute: ...].AttrName
        extract_attr = None
        attr_m = re.match(r'^(.*\])\.([A-Za-z_]\w*)$', inner_query)
        if attr_m:
            inner_query  = attr_m.group(1)
            extract_attr = attr_m.group(2)

        # Parse path and attribute filters
        conditions = {}
        path = inner_query
        cond_m = re.match(r'^(.+?)\[([^\]]+)\]$', inner_query)
        if cond_m:
            path = cond_m.group(1).strip()
            for cond in cond_m.group(2).split(','):
                cond = cond.strip()
                if '=' in cond:
                    k, v = cond.split('=', 1)
                    conditions[k.strip()] = self.process_all_variables(v.strip())

        # Extract and HTML-decode the outer element's text
        if outer.startswith('/'):
            encoded = self._extract_by_xpath(xml_content, outer)
            if not encoded:
                encoded = self._extract_by_element_name(xml_content, outer.lstrip('/').split(':')[-1])
        else:
            encoded = self._extract_by_element_name(xml_content, outer)

        if not encoded:
            return None if extract_attr else "0"

        decoded = _html.unescape(encoded).strip()
        decoded = re.sub(r'<!\[CDATA\[(.*?)]]>', lambda m: m.group(1), decoded, flags=re.DOTALL)
        if not decoded:
            return None if extract_attr else "0"

        try:
            root = ET.fromstring(decoded)
        except ET.ParseError:
            try:
                root = ET.fromstring(f'<_root_>{decoded}</_root_>')
            except ET.ParseError:
                return None if extract_attr else "0"

        # Build XPath from dot-notation path and find candidates.
        # Skip the first component if it matches the root element (e.g. user writes
        # "Files.File" but the decoded XML root IS <Files>, so searching .//Files/File
        # would look for a nested <Files> that doesn't exist).
        parts = [p for p in path.split('.') if p]
        root_local = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        if parts and root_local == parts[0]:
            parts = parts[1:]
        xpath = ('.//' + '/'.join(parts)) if parts else '.'
        candidates = root.findall(xpath)

        # Filter by attribute conditions (variables already resolved above)
        matches = [e for e in candidates if all(e.get(k) == v for k, v in conditions.items())]

        if extract_attr:
            return matches[0].get(extract_attr, "") if matches else None

        return str(len(matches))

    def _extract_by_element_name(self, xml_content, element_name):
        """Extract value by simple element name (convenience method)"""
        try:
            tag = re.escape(element_name)
            # (?:\s[^>]*)? ensures attributes must start with whitespace,
            # preventing <filename> from matching when element_name is "file"
            pattern = rf'<{tag}(?:\s[^>]*)?>(.*?)</{tag}>'
            match = re.search(pattern, xml_content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

            # Also try self-closing elements with text content
            pattern = rf'<{tag}(?:\s[^>]*)?>([^<]*)'
            match = re.search(pattern, xml_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        except Exception as e:
            print(f"Element name extraction error: {e}")

        return None

    def _extract_namespaces(self, xml_content):
        """Extract namespace prefixes from XML content"""
        namespaces = {}
        try:
            # Find namespace declarations
            ns_pattern = r'xmlns:?(\w*)\s*=\s*["\']([^"\']+)["\']'
            matches = re.findall(ns_pattern, xml_content)

            for prefix, uri in matches:
                if prefix:
                    namespaces[prefix] = uri
                else:
                    namespaces['default'] = uri

        except Exception as e:
            print(f"Namespace extraction error: {e}")

        return namespaces

    def process_variables(self, xml_content, excel_row_data=None):
        """
        Process all variables in XML content, including declared variables and encoded XML columns

        Args:
            xml_content (str): XML with variable placeholders
            excel_row_data (dict): Excel row data for encoding columns and variable definitions (optional)

        Returns:
            str: XML with variables replaced with actual values
        """
        if not xml_content:
            return xml_content

        processed_xml = xml_content

        # Step 1: Process variable definitions if excel_row_data is provided
        if excel_row_data:
            self.process_variable_definitions(excel_row_data)

        # Step 2: Handle encoded XML columns if excel_row_data is provided
        if excel_row_data:
            processed_xml = self.process_encoded_columns(processed_xml, excel_row_data)

        # Step 3: Process regular variables (including declared variables and extracted variables)
        processed_xml = self.process_all_variables(processed_xml)

        return processed_xml

    def process_variable_definitions(self, excel_row_data):
        """
        Process Variable_Definitions column to create reusable variables

        Args:
            excel_row_data (dict): Excel row data containing Variable_Definitions column
        """
        variable_definitions = excel_row_data.get('Variable_Definitions', '')
        if not variable_definitions or not str(variable_definitions).strip():
            return

        try:
            # Parse variable definitions: var_name={{FUNCTION()}};var_name2={{FUNCTION2()}}
            definitions = str(variable_definitions).split(';')

            for definition in definitions:
                definition = definition.strip()
                if not definition:
                    continue

                if '=' in definition:
                    var_name, var_expression = definition.split('=', 1)
                    var_name = var_name.strip()
                    var_expression = var_expression.strip()

                    # Process the variable expression to get its value
                    if var_expression.startswith('{{') and var_expression.endswith('}}'):
                        # Remove {{ }} and evaluate the function
                        function_expr = var_expression[2:-2].strip()
                        try:
                            var_value = str(self.evaluate_variable_manual(function_expr))
                            self.declared_variables[var_name] = var_value
                            print(f"Declared variable: {var_name} = {var_value}")
                        except Exception as e:
                            error_msg = f"{{ERROR: Failed to evaluate {function_expr} - {str(e)}}}"
                            self.declared_variables[var_name] = error_msg
                            print(f"Error declaring variable {var_name}: {e}")
                    else:
                        # Static value
                        self.declared_variables[var_name] = var_expression
                        print(f"Declared static variable: {var_name} = {var_expression}")

        except Exception as e:
            print(f"Error processing variable definitions: {e}")

    def process_all_variables(self, xml_content):
        """Process all types of variables in XML content"""
        if not xml_content:
            return xml_content

        # Find all {{FUNCTION(params)}} patterns
        pattern = r'\{\{([^}]+)\}\}'

        def replace_variable(match):
            variable_expr = match.group(1).strip()
            try:
                return str(self.evaluate_variable_manual(variable_expr))
            except Exception as e:
                print(f"Error processing variable '{variable_expr}': {e}")
                return f"{{ERROR: {variable_expr}}}"

        # Replace all variables
        processed_xml = re.sub(pattern, replace_variable, xml_content)
        return processed_xml

    def process_encoded_columns(self, xml_content, excel_row_data):
        """
        Process Raw_XML_* columns and replace {{ENCODED_XML_*}} placeholders

        Args:
            xml_content (str): Main XML with encoded placeholders
            excel_row_data (dict): Excel row data containing Raw_XML_* columns

        Returns:
            str: XML with encoded placeholders replaced
        """
        processed_xml = xml_content

        # Find all Raw_XML_* columns
        encoding_columns = {}
        for column_name, column_value in excel_row_data.items():
            if column_name.startswith('Raw_XML_') and column_value and str(column_value).strip():
                suffix = column_name[8:]  # Remove 'Raw_XML_' prefix
                placeholder = f"{{{{ENCODED_XML_{suffix}}}}}"
                encoding_columns[placeholder] = str(column_value).strip()

        # Process each encoding column
        for placeholder, raw_xml in encoding_columns.items():
            try:
                # First, process variables in the raw XML
                processed_raw_xml = self.process_raw_xml_variables(raw_xml)

                # Then encode the processed XML to Base64
                import base64
                encoded_xml = base64.b64encode(processed_raw_xml.encode('utf-8')).decode('utf-8')

                # Replace the placeholder in main XML
                processed_xml = processed_xml.replace(placeholder, encoded_xml)

                print(f"Processed encoding: {placeholder} -> {len(encoded_xml)} chars")

            except Exception as e:
                error_msg = f"{{ERROR: Failed to encode {placeholder} - {str(e)}}}"
                processed_xml = processed_xml.replace(placeholder, error_msg)
                print(f"Error processing {placeholder}: {e}")

        return processed_xml

    def process_raw_xml_variables(self, raw_xml):
        """
        Process variables in raw XML content (before encoding) - includes declared variables

        Args:
            raw_xml (str): Raw XML with variable placeholders

        Returns:
            str: XML with variables replaced
        """
        if not raw_xml:
            return raw_xml

        print(f"DEBUG: Processing Raw XML variables. Available declared variables: {list(self.declared_variables.keys())}")
        print(f"DEBUG: Available extracted variables: {list(self.extracted_variables.keys())}")

        # Use the same variable processing as main XML (includes declared variables and extracted variables)
        return self.process_all_variables(raw_xml)

    def get_encoding_columns_info(self, excel_row_data):
        """
        Get information about available encoding columns

        Args:
            excel_row_data (dict): Excel row data

        Returns:
            dict: Information about encoding columns
        """
        info = {
            'columns': [],
            'placeholders': [],
            'mapping': {}
        }

        for column_name, column_value in excel_row_data.items():
            if column_name.startswith('Raw_XML_'):
                suffix = column_name[8:]
                placeholder = f"{{{{ENCODED_XML_{suffix}}}}}"
                has_content = bool(column_value and str(column_value).strip())

                info['columns'].append({
                    'name': column_name,
                    'suffix': suffix,
                    'placeholder': placeholder,
                    'has_content': has_content,
                    'content_length': len(str(column_value).strip()) if has_content else 0
                })
                info['placeholders'].append(placeholder)
                info['mapping'][placeholder] = column_name

        return info

    def evaluate_variable(self, variable_expressions, health_checker):
        for variable_expression in variable_expressions:
            if not variable_expression['tag_values']:
                for variable in variable_expression['tag_functions']:
                    if variable.startswith('VAR.'):
                        var_name = variable[4:]  # Remove 'VAR.'
                        variable_value = self.get_from_variables(variable_expressions, var_name)
                        variable_expression['tag_values'].append(variable_value)
                        variable_expression['tag_variables'].append("")
                    elif variable.startswith('CUSTOM.'):
                        value = self.evaluate_custom_function(variable[7:], variable_expression['tag_name'],health_checker)  # Remove 'CUSTOM.'
                        variable_expression['tag_values'].append(value)
                        variable_expression['tag_variables'].append("")
                    elif bool(re.match(r'^VAR\([^)]+\)\.CUSTOM\.', variable)):
                        variable_name = re.match(r'^VAR\(([^)]+)\)\.CUSTOM\.', variable).group(1)
                        value = self.evaluate_custom_function(re.match(r'^VAR\([^)]+\)\.CUSTOM\.(.*)$', variable).group(1), variable_expression['tag_name'], health_checker)
                        variable_expression['tag_values'].append(value)
                        variable_expression['tag_variables'].append(variable_name)

                    elif bool(re.match(r'^VAR\([^)]+\)\.', variable)):
                        variable_name = re.match(r'^VAR\(([^)]+)\)\.', variable).group(1)
                        value = self.evaluate_builtin_function(re.match(r'^VAR\([^)]+\)\.(.*)$', variable).group(1))
                        variable_expression['tag_values'].append(value)
                        variable_expression['tag_variables'].append(variable_name)
                    else:
                        value = self.evaluate_builtin_function(variable)
                        variable_expression['tag_values'].append(value)
                        variable_expression['tag_variables'].append("")

    ## this function is for processing variables of manual tab
    def evaluate_variable_manual(self, variable_expr, variable_expressions=None):
        """
        Evaluate a single variable expression

        Args:
            variable_expr (str): Variable expression like 'DATE(YYYY-MM-DD)', 'VAR.transaction_ref', or 'EXTRACT.transaction_id'

        Returns:
            str: Evaluated result
            :param variable_expr:
            :param variable_expressions:
        """
        # Handle VAR(name).CUSTOM.func() — evaluate function, store in declared_variables, return value
        var_custom_match = re.match(r'^VAR\(([^)]+)\)\.CUSTOM\.(.+)$', variable_expr)
        if var_custom_match:
            var_name  = var_custom_match.group(1).strip()
            func_expr = var_custom_match.group(2).strip()
            value = self.evaluate_custom_function(func_expr, None, None)
            self.declared_variables[var_name] = str(value)
            print(f"Stored VAR({var_name}) = {value}")
            return value

        # Handle VAR(name).<builtin_func>() — evaluate built-in, store in declared_variables, return value
        var_builtin_match = re.match(r'^VAR\(([^)]+)\)\.(.+)$', variable_expr)
        if var_builtin_match:
            var_name  = var_builtin_match.group(1).strip()
            func_expr = var_builtin_match.group(2).strip()
            value = self.evaluate_builtin_function(func_expr)
            self.declared_variables[var_name] = str(value)
            print(f"Stored VAR({var_name}) = {value}")
            return value

        # Handle declared variables
        if variable_expr.startswith('VAR.'):
            var_name = variable_expr[4:]  # Remove 'VAR.'
            if var_name in self.declared_variables:
                return self.declared_variables[var_name]
            variable_value = self.get_from_variables(variable_expressions, var_name)
            return variable_value

        # Handle extracted variables (from responses)
        if variable_expr.startswith('EXTRACT.'):
            var_name = variable_expr[8:]  # Remove 'EXTRACT.'
            if var_name in self.extracted_variables:
                return self.extracted_variables[var_name]
            else:
                return f"{{ERROR: Undefined extracted variable '{var_name}'}}"

        # Handle custom functions
        if variable_expr.startswith('CUSTOM.'):
            return self.evaluate_custom_function(variable_expr[7:], None, None)  # Remove 'CUSTOM.'

        # Handle built-in functions
        return self.evaluate_builtin_function(variable_expr)


    def get_from_variables(self, variable_expressions, variable_name):
        for variable_expression in reversed(variable_expressions):
            variables = variable_expression['tag_variables']
            for index, variable in enumerate(variables):
                if variable.lower() == variable_name.lower():
                    return variable_expression['tag_values'][index]
        return f"{{Error while retrieving variable {variable_name} value}}"



    def evaluate_custom_function(self, func_expr, tag, health_checker: HealthChecker):
        """Evaluate custom function"""
        if not self.custom_functions:
            return f"{{ERROR: No custom functions loaded}}"

        # Parse function name and parameters
        if '(' in func_expr:
            func_name = func_expr[:func_expr.index('(')]
            params_str = func_expr[func_expr.index('(')+1:func_expr.rindex(')')]
            params = [p.strip().strip('"\'') for p in params_str.split(',') if p.strip()]
        else:
            func_name = func_expr
            params = []

        # Execute custom function
        if hasattr(self.custom_functions, func_name):
            func = getattr(self.custom_functions, func_name)
            if callable(func):
                already_used = True
                value = None
                counter = 1
                while already_used == True and counter <= 10:
                    if params:
                        value = func(*params)
                        if health_checker:
                            is_exist = health_checker.check_in_dict(tag, value)
                        else:
                            is_exist = False
                        already_used = is_exist
                    else:
                        value = func()
                        if health_checker:
                            is_exist = health_checker.check_in_dict(tag, value)
                        else:
                            is_exist = False
                        already_used = is_exist
                    counter += 1
                if already_used and counter == 10:
                    raise Exception(f'Error while generating value for 10 attempts: {func_expr}')
                return value

        return f"{{ERROR: Custom function '{func_name}' not found}}"

    def evaluate_builtin_function(self, func_expr):
        """Evaluate built-in function"""
        # Parse function name and parameters
        if '(' in func_expr:
            func_name = func_expr[:func_expr.index('(')]
            params_str = func_expr[func_expr.index('(')+1:func_expr.rindex(')')]
            params = [p.strip().strip('"\'') for p in params_str.split(',') if p.strip()]
        else:
            func_name = func_expr
            params = []

        # Built-in functions
        if func_name == 'DATE':
            format_str = params[0] if params else 'YYYY-MM-DD'
            return self.format_date(datetime.now(), format_str)

        elif func_name == 'DATETIME':
            format_str = params[0] if params else 'YYYY-MM-DD HH:mm:ss'
            return self.format_date(datetime.now(), format_str)

        elif func_name == 'DATE_ADD':
            days = int(params[0]) if params else 1
            format_str = params[1] if len(params) > 1 else 'YYYY-MM-DD'
            future_date = datetime.now() + timedelta(days=days)
            return self.format_date(future_date, format_str)

        elif func_name == 'DATE_SUB':
            days = int(params[0]) if params else 1
            format_str = params[1] if len(params) > 1 else 'YYYY-MM-DD'
            past_date = datetime.now() - timedelta(days=days)
            return self.format_date(past_date, format_str)

        elif func_name == 'RANDOM':
            min_val = int(params[0]) if params else 1
            max_val = int(params[1]) if len(params) > 1 else 100
            return random.randint(min_val, max_val)

        elif func_name == 'RANDOM_DECIMAL':
            min_val = float(params[0]) if params else 1.0
            max_val = float(params[1]) if len(params) > 1 else 100.0
            decimals = int(params[2]) if len(params) > 2 else 2
            return round(random.uniform(min_val, max_val), decimals)

        elif func_name == 'RANDOM_STRING':
            length = int(params[0]) if params else 8
            char_type = params[1].upper() if len(params) > 1 else 'ALPHANUMERIC'
            return self.generate_random_string(length, char_type)

        elif func_name == 'UUID':
            style = params[0].lower() if params else 'full'
            uid = str(uuid.uuid4())
            if style == 'short':
                return uid.split('-')[0]
            return uid

        elif func_name == 'SEQUENCE':
            key = params[0] if params else 'default'
            start = int(params[1]) if len(params) > 1 else 1
            prefix = params[2] if len(params) > 2 else ''
            format_str = params[3] if len(params) > 3 else ''

            if key not in self.sequences:
                self.sequences[key] = start
            else:
                self.sequences[key] += 1

            number = self.sequences[key]
            if format_str:
                number = format(number, format_str)

            return f"{prefix}{number}"

        elif func_name == 'RUN_ID':
            return self.run_id or 'RUN_UNKNOWN'

        elif func_name == 'TEST_INDEX':
            return self.test_index

        elif func_name == 'TIMESTAMP':
            return int(datetime.now().timestamp())

        elif func_name == 'NOW':
            format_str = params[0] if params else 'YYYY-MM-DD HH:mm:ss'
            return self.format_date(datetime.now(), format_str)

        else:
            return f"{{ERROR: Unknown function '{func_name}'}}"

    def format_date(self, date_obj, format_str):
        """Format date according to custom format string"""
        # Convert custom format to Python strftime format
        format_str = format_str.replace('YYYY', '%Y')
        format_str = format_str.replace('MM', '%m')
        format_str = format_str.replace('DD', '%d')
        format_str = format_str.replace('HH', '%H')
        format_str = format_str.replace('mm', '%M')
        format_str = format_str.replace('ss', '%S')

        return date_obj.strftime(format_str)

    def generate_random_string(self, length, char_type):
        """Generate random string of specified type"""
        import string

        if char_type == 'ALPHANUMERIC':
            chars = string.ascii_letters + string.digits
        elif char_type == 'LETTERS':
            chars = string.ascii_letters
        elif char_type == 'UPPERCASE':
            chars = string.ascii_uppercase
        elif char_type == 'LOWERCASE':
            chars = string.ascii_lowercase
        elif char_type == 'DIGITS':
            chars = string.digits
        else:
            chars = string.ascii_letters + string.digits

        return ''.join(random.choice(chars) for _ in range(length))

    def evaluate_assertions(self, response_content: str, assertion_rules: str) -> list:
        """
        Evaluate assertions against response content.

        Format: selector==expected_value;selector2==expected_value2
        Selector: XPath (//...), regex (regex:...), EXTRACT.varname, or element name.
        Expected value may contain {{...}} variable placeholders.

        Returns list of dicts: {selector, expected, actual, passed}
        """
        results = []
        if not assertion_rules or not assertion_rules.strip():
            return results

        for rule in assertion_rules.split(';'):
            rule = rule.strip()
            if not rule or '==' not in rule:
                continue

            selector, expected = rule.split('==', 1)
            selector = selector.strip()
            expected = self.process_all_variables(expected.strip())
            display_selector = self.process_all_variables(selector)

            try:
                if '>>' in selector:
                    result = self._query_inner_xml(response_content, selector)
                    has_attr = bool(re.match(r'^.*\]\.[A-Za-z_]\w*$', selector.split('>>', 1)[1].strip()))
                    if has_attr:
                        actual = result or ""
                        passed = actual == expected
                    else:
                        count  = int(result or "0")
                        actual = f"{count} match(es)"
                        if expected == "found":
                            passed = count >= 1
                        elif expected == "not found":
                            passed = count == 0
                        elif expected == "unique":
                            passed = count == 1
                        else:
                            passed = str(count) == expected
                    results.append({
                        'selector': display_selector,
                        'expected': expected,
                        'actual': actual,
                        'passed': passed,
                    })
                    continue

                if selector.startswith('//') or selector.startswith('/'):
                    actual = self._extract_by_xpath(response_content, selector)
                elif selector.startswith('regex:'):
                    actual = self._extract_by_regex(response_content, selector[6:])
                elif selector.startswith('decoded_xml:'):
                    actual = self._extract_from_decoded_xml(response_content, selector[12:])
                elif selector.startswith('EXTRACT.'):
                    actual = self.extracted_variables.get(selector[8:])
                else:
                    actual = self._extract_by_element_name(response_content, selector)

                actual = actual or ""
                results.append({
                    'selector': display_selector,
                    'expected': expected,
                    'actual': actual,
                    'passed': actual == expected,
                })
            except Exception as e:
                results.append({
                    'selector': display_selector,
                    'expected': expected,
                    'actual': f"ERROR: {e}",
                    'passed': False,
                })

        return results

    def get_all_variables_info(self):
        """Get information about all available variables for debugging"""
        return {
            'declared_variables': dict(self.declared_variables),
            'extracted_variables': dict(self.extracted_variables),
            'sequences': dict(self.sequences),
            'run_id': self.run_id,
            'test_index': self.test_index
        }
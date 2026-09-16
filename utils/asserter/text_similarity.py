from difflib import SequenceMatcher


def calculate_similarity(actual_msg, expected_msg):
    # Remove all whitespaces from both strings before comparison
    actual_msg_no_spaces = actual_msg.replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")
    expected_msg_no_spaces = expected_msg.replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")
    return SequenceMatcher(None, expected_msg_no_spaces, actual_msg_no_spaces).ratio()

def get_strings_difference(expected, actual):
    matcher = SequenceMatcher(None, expected, actual)
    result = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            result.append(expected[i1:i2])
        elif tag == 'delete':
            result.append(f"[-{expected[i1:i2]}-]")
        elif tag == 'insert':
            result.append(f"{{+{actual[j1:j2]}+}}")
        elif tag == 'replace':
            result.append(f"[-{expected[i1:i2]}-]{{+{actual[j1:j2]}+}}")
    return "".join(result)


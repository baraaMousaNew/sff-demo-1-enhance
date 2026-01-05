from difflib import SequenceMatcher

def calculate_similarity(expected_msg, actual_msg):
    return SequenceMatcher(None, expected_msg, actual_msg).ratio()
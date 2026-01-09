import json
import re

def clean_and_parse(raw_text):
    print(f"Testing: {raw_text!r}")
    text = raw_text.strip()
    
    # 1. Try to find JSON block explicitly
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
        
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  Initial Parse Error: {e}")
        # Attempt basic repair: remove trailing commas
        text = re.sub(r',\s*([\]}])', r'\1', text)
        try:
            return json.loads(text)
        except Exception as e2:
            raise ValueError(f"Final Error: {e2}")

def test():
    test_cases = [
        ('{"a": 1}', {'a': 1}), # Clean
        ('```json\n{"a": 1}\n```', {'a': 1}), # Markdown
        ('Here is JSON: {"a": 1}', {'a': 1}), # Prefix garbage
        ('{"a": 1} Note: ended.', {'a': 1}), # Suffix garbage
        ('{"a": 1,}', {'a': 1}), # Trailing comma
        ('```\n{"a": 1,}\n```', {'a': 1}), # Markdown + Trailing comma
    ]
    
    for input_str, expected in test_cases:
        try:
            result = clean_and_parse(input_str)
            if result == expected:
                print("  PASS")
            else:
                print(f"  FAIL: Expected {expected}, got {result}")
        except Exception as e:
            print(f"  CRASH: {e}")

if __name__ == "__main__":
    test()

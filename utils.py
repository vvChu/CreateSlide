import sys

def safe_print(text: str):
    """
    Prints text safely to console, handling UnicodeEncodeError on Windows.
    Ignored characters are replaced with '?'.
    """
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: Encode to utf-8 then decode, replacing errors, 
        # or just encode to console's encoding strictly.
        try:
            # sys.stdout.encoding might be 'cp1252' etc.
            encoding = sys.stdout.encoding or 'utf-8'
            # Encode, replace errors with ?, then decode back to string to print
            safe_text = text.encode(encoding, errors='replace').decode(encoding)
            print(safe_text)
        except Exception:
            # Absolute fallback
            print(text.encode('ascii', errors='replace').decode('ascii'))

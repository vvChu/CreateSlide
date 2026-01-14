import os
import sys
import logging

def suppress_console_output():
    """
    Redirects all output to app.log and disables console output to prevent
    Windows [Errno 22] Invalid argument crashes.
    """
    log_file = "app.log"
    
    # 1. Setup Python Logging
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    
    # Create File Handler
    handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    
    # 2. Redirect sys.stdout and sys.stderr to the file completely
    # We open the file in append mode and assign it to sys.stdout/stderr
    # This gives a real file object with a real descriptor (usually)
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    
    # Keep a reference to the open file to prevent garbage collection
    global _log_file_obj
    _log_file_obj = open(log_file, 'a', encoding='utf-8', buffering=1)
    
    sys.stdout = _log_file_obj
    sys.stderr = _log_file_obj

    # 3. Aggressively Disable Colorama
    # Colorama often wraps stdout/stderr. We need to prevent it or undo it.
    try:
        import colorama
        colorama.deinit()
        # Prevent re-init
        colorama.init = lambda *args, **kwargs: None
    except ImportError:
        pass

    # 4. Patch Click (used by Flask/Mesop)
    # Click attempts to access stream.encoding or isatty(). 
    # Our real file object supports these naturally, so we might not need to patch dummy_echo
    # UNLESS click writes directly to the old fd.
    try:
        import click
        # Force click to use our redirected stdout/stderr or just pass through
        # By default click uses sys.stdout, so we should be good.
        pass
    except ImportError:
        pass

def safe_print(text: str):
    """
    Safe print function that logs to the setup logger or file.
    """
    try:
        # Use the logger if configured
        if logging.getLogger().handlers:
            logging.info(text)
        else:
            # Fallback
            print(text)
    except:
        pass

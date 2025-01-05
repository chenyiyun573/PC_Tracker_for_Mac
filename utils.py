# utils.py
from datetime import datetime
import sys

def print_debug(msg):
    """Print debug messages to stderr."""
    sys.stderr.write(str(msg) + "\n")

def get_current_time():
    """Return current time as string: YYYY-mm-dd_HH:MM:SS."""
    return datetime.now().strftime('%Y-%m-%d_%H:%M:%S')

def get_capslock_state():
    """
    On macOS, no straightforward Python API for caps lock.
    Return 0 to indicate 'off'.
    """
    return 0

def get_element_info_at_position(x, y):
    """
    STUB on macOS for UI element info. Windows had pywinauto; 
    mac would need Apple Accessibility APIs. We'll just return a dict.
    """
    return {"name": "UnknownElement", "coordinates": None}

import logging
import os
import sqlite3
import sys
import traceback
from functools import wraps
from PySide6.QtWidgets import QMessageBox


def get_log_directory():
    """Finds or creates a dedicated log directory in the user's app support folder."""
    app_name = "SecOpsFieldManual" # Use a simple name for the folder

    if sys.platform == "win32":
        # Windows: %APPDATA%\AppName\logs
        log_dir = os.path.join(os.getenv('APPDATA'), app_name, 'logs')
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/AppName/logs
        log_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', app_name, 'logs')
    else:
        # Linux: ~/.local/share/AppName/logs
        log_dir = os.path.join(os.path.expanduser('~'), '.local', 'share', app_name, 'logs')
    
    # Create the directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

LOG_FILE_PATH = os.path.join(get_log_directory(), 'app.log')

def setup_logging():
    """Sets up a central logger for the application."""
    logging.basicConfig(
        filename=LOG_FILE_PATH,
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def safe_db_operation(func):
    """A decorator to wrap database functions in a try...except block."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.Error as e:
            # Log the full error to the file
            error_details = traceback.format_exc()
            logging.error(f"Database error in {func.__name__}: {e}\n{error_details}")
            
            # Show a simple message to the user
            QMessageBox.critical(
                None, 
                "Database Error",
                f"A database error occurred: {e}\n\n"
                "Please check app.log for more details."
            )
            # Return a default value that won't crash the app
            if "search" in func.__name__:
                return [] # Return empty list for search functions
            if "insert" in func.__name__:
                return False, -1 # Return failure for insert
            return None
    return wrapper


def log_uncaught_exceptions(ex_cls, ex, tb):
    """A global exception hook to log any uncaught exceptions."""
    error_details = "".join(traceback.format_tb(tb))
    logging.error(f"Uncaught Exception:\nType: {ex_cls.__name__}\nValue: {ex}\n{error_details}")
    
    QMessageBox.critical(
        None, "Unhandled Error",
        "The application encountered an unexpected error.\n\n"
        f"Details have been logged to:\n{LOG_FILE_PATH}"
    )
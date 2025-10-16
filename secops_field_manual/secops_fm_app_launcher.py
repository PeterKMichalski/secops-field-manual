import sys
import os
import traceback

# Only import the error handler at the top level
from .ui.error_handler import setup_logging, log_uncaught_exceptions, get_log_directory


def main():
    """Main function to initialize and run the application."""
    
    # Determine the base path for the application (works for dev and PyInstaller)
    if getattr(sys, 'frozen', False):
        # The application is frozen (run as a bundle)
        base_path = sys._MEIPASS
    else:
        # The application is running in a normal Python environment
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Change the current working directory to the base path
    os.chdir(base_path)


    # Setup logging as the VERY FIRST step
    setup_logging()
    sys.excepthook = log_uncaught_exceptions

    try:
        # --- Move all other application imports INSIDE the try block ---
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QIcon
        from .ui.main_window import FieldManualApp
        from .data.database import get_default_db_path
        from .ui.constants import DEFAULT_DB_FILENAME, DEFAULT_FOLDER_NAME
        from .ui.utilities import resource_path, load_last_db_path

        # --- PATHING FIX ---
        # Determine the base path for the application
        if getattr(sys, 'frozen', False):
            # The application is frozen (run as a bundle)
            base_path = sys._MEIPASS
        else:
            # The application is running in a normal Python environment
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        # Change the current working directory to the base path
        os.chdir(base_path)

        # Determine DB path
        db_path = load_last_db_path()
        if not db_path or not os.path.exists(db_path):
            db_path = get_default_db_path(DEFAULT_FOLDER_NAME, DEFAULT_DB_FILENAME)

        app = QApplication(sys.argv)
        window = FieldManualApp(db_path)
        
        # Safely set window icon
        try:
             icon_path = resource_path('icon.png')
             if os.path.exists(icon_path):
                window.setWindowIcon(QIcon(icon_path))
        except Exception as e:
             print(f"Could not load window icon: {e}")

        window.show()
        sys.exit(app.exec())
        
    except Exception as e:
        # This will now catch any import errors and log them
        log_dir = get_log_directory()
        error_log_path = os.path.join(log_dir, "startup_error.log")
        with open(error_log_path, "w") as f:
            f.write("--- Critical Application Startup Crash ---\n")
            f.write(traceback.format_exc())
        sys.exit(1)
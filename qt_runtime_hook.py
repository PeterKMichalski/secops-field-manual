import sys
import os

# This is the definitive hook for PySide6 on macOS with PyInstaller.
# It explicitly sets the necessary environment variables for Qt to find its plugins.

if sys.platform == 'darwin' and hasattr(sys, '_MEIPASS'):
    # Get the base path of the bundled app
    base_path = sys._MEIPASS

    # Set the general plugin path
    plugin_path = os.path.join(base_path, 'PySide6', 'Qt', 'plugins')
    os.environ['QT_PLUGIN_PATH'] = plugin_path
    
    # Explicitly set the path for the platform plugin (like "cocoa")
    qpa_plugin_path = os.path.join(base_path, 'PySide6', 'Qt', 'plugins', 'platforms')
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = qpa_plugin_path

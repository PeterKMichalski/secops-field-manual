import sys
import os

# Add the project's root directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from secops_field_manual.secops_fm_app_launcher import main

if __name__ == '__main__':
    sys.exit(main())
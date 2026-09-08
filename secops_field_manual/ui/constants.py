# --- Application Metadata ---
APP_AUTHOR = "Peter Michalski"
APP_VERSION = "1.2"
APP_RELEASE_DATE = "2026-09-02"
APP_THANKS = "Thanks to 13Cubed, PySide6 community, and more."

# --- Static Field Lists ---
OPERATING_SYSTEMS = ["All", "Windows", "Linux", "macOS", "Other"]
MITRE_ATTACK_TACTICS = [
    "Initial Access", "Execution", "Persistence", "Privilege Escalation",
    "Defense Evasion", "Credential Access", "Discovery", "Lateral Movement",
    "Collection", "Command and Control", "Exfiltration", "Impact",
]

# --- Default File Path Configuration ---
DEFAULT_DB_FILENAME = "field_notes.db"
DEFAULT_FOLDER_NAME = "SecOps Field Notes"

# --- List for Dynamic Artifact Field ---
# Define the main types and special types separately
main_artifact_types = [
    "File Path", "File Name", "Command Line", "Process Name", "Registry Key",
    "Service Name", "IP Address", "Domain Name", "User Agent", "Hash Value", "Mutex Name"
]
special_artifact_types = ["Concept", "Other"]

# Sort the main list and then add the special types at the end
ARTIFACT_TYPES = sorted(main_artifact_types) + special_artifact_types
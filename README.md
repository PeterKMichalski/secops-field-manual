# secops-field-manual
Python based desktop application designed as a personal knowledge base for security professionals.


# SecOps Field Manual
A Python based desktop application designed as a personal knowledge base for security professionals. It provides a fast and efficient way to store, organize, and retrieve technical notes, forensic artifacts, and operational procedures.

<img width="1920" height="1056" alt="Screenshot 2025-10-16 at 1 30 47 PM" src="https://github.com/user-attachments/assets/e9afee7c-4d76-4a24-a41c-0cae6d107842" />

# Key Features
* Advanced Search: A powerful, unified search bar that supports:

  * Implicit AND, explicit OR, and exclusion (-) operators.

  * Field-specific filters (e.g., tags:network, os:windows, title:"My Entry").

  * Tab-autocompletion for search fields.

  * Searching for entries with blank fields (e.g., path:blank).

* Rich Content & Linking:

  * Full Markdown support in "Description" and "Notes" fields, including tables, code blocks, and lists.

  * Internal linking between entries using [[Entry Title]] syntax.

  * A dedicated "Resources" field that supports annotated external links with [Display Text](url.com) syntax.

* Structured Data:

  * Entries are categorized by a dynamic Artifact Type (e.g., "File Path," "Registry Key," "Command Line").

  * A robust tagging system allows for multiple tags per entry, with a dedicated management window for renaming and deleting tags.

* Database Management:

  * Import from CSV: A user-friendly wizard to bulk-add entries from a CSV file, with options to add to the current database or create a new one. Includes a template generator.

  * Export to CSV: Export the entire database to a portable CSV file, preserving all content and timestamps.

  * Merge & Compare: A powerful tool to compare two different database files, view a side-by-side "diff" of conflicting entries, and selectively merge content.

  * Undo Operation: A safety net feature that allows for the immediate reversal of any import or merge operation.

* User Experience:

  * Clean, organized UI with resizable panels and group boxes.

  * "Favorite Searches" feature to save and quickly run common queries.

  * "Recent Searches" list for quick access.

  * Customizable zoom level for improved accessibility.

# Technology Stack
* Language: Python

* Framework: PySide6 for the desktop GUI

* Database: SQLite for local, portable data storage

# Setup and Installation (from Source)
To run the application from the source code, follow these steps.

1. Clone the repository:
```   
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
cd your-repo-name
```
2. Create and activate a virtual environment:
```
python3 -m venv venv
source venv/bin/activate
```
3. Install dependencies:
```
pip install -r requirements.txt
```
4. Run the application:
```
python run.py
```
# Building the Application
This project uses PyInstaller to create a standalone application.

1. Make sure you are in your activated virtual environment and have PyInstaller installed (pip install pyinstaller).

2. Run the build command from the project's root directory:
```
pyinstaller "Forensic Field Manual.spec" --clean
```

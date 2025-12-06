# SecOps Field Manual
A Python based desktop application designed as a personal knowledge base for security professionals. It provides a fast and efficient way to store, organize, and retrieve technical notes, forensic artifacts, and operational procedures. This project was developed with AI assistance. 

<img width="1205" height="833" alt="Secops Field Manual Preview" src="https://github.com/user-attachments/assets/729cae0f-2ca8-4008-8aba-dcdd0041f73e" />

# Key Features
* Advanced Search: A powerful, unified search bar that supports:

  * Implicit AND and exclusion (-) operators.

  * Field-specific filters (e.g., `tags:network`, `os:windows`, `title:"My Entry"`).

  * Tab-autocompletion for search fields.

  * Searching for entries with blank fields (e.g., `artifact_value:blank`).

* Rich Content & Linking:

  * Full Markdown support in "Description" and "Notes" fields, including tables, code blocks, and lists.

  * Internal linking between entries using `[[Entry Title]]` syntax.

  * A dedicated "Resources" field that supports annotated external links with `[Display Text](url.com)` syntax.

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
git clone https://github.com/PeterKMichalski/secops-field-manual.git
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
# Building the Application (PyInstaller)
PyInstaller was used to create a standalone application.

1. Generate the `.spec` file:
From the project's root directory, run `pyi-makespec`.
```
pyi-makespec --windowed --name="SecOps Field Manual" run.py
```
2. Edit the `.spec` file:
Open the generated `.spec` file and modify the `Analysis` section to include the icon, any hidden imports, and the possibly the runtime hook for macOS compatibility.
```
a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=[('path/to/your/field_manual_logo.png', '.')],
    hiddenimports=['markdown'],
    hookspath=[],
    # A runtime_hook was used due to issues for macOS to find Qt plugins
    runtime_hooks=['secops_field_manual/qt_runtime_hook.py'],
    ...
)

...

app = BUNDLE(
    exe,
    name='SecOps Field Manual.app',
    icon='path/to/your/field_manual_logo.png',
    bundle_identifier=None,
)
```

3. Build the Application:
Once the .spec file is configured, run the pyinstaller command.
```
pyinstaller "SecOps Field Manual.spec" --clean
```

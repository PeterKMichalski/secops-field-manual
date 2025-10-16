import csv
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QFileDialog, QRadioButton, QTextEdit, QMessageBox, QWidget,
    QApplication
)
from ..data.database import init_db
from .comparison_engine import perform_bulk_import_from_csv, _open_csv_with_fallback
from .undo_dialog import UndoDialog
from .constants import DEFAULT_FOLDER_NAME

class ImportDialog(QDialog):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Entries from CSV")
        self.setMinimumSize(600, 500)
        self.main_app = main_app

        main_layout = QVBoxLayout(self)

        # --- Select Source CSV ---
        source_group = QGroupBox("1. Select Source CSV File")
        source_layout = QVBoxLayout() # Changed to QVBoxLayout
        
        csv_row_layout = QHBoxLayout()
        self.csv_path_input = QLineEdit()
        self.csv_path_input.setPlaceholderText("Path to your .csv file...")
        self.browse_csv_button = QPushButton("Browse...")
        csv_row_layout.addWidget(self.csv_path_input)
        csv_row_layout.addWidget(self.browse_csv_button)
        source_layout.addLayout(csv_row_layout)
        
        self.generate_template_button = QPushButton("Generate Blank CSV Template...")
        source_layout.addWidget(self.generate_template_button)
        
        source_group.setLayout(source_layout)
        main_layout.addWidget(source_group)

        # --- Choose Destination ---
        dest_group = QGroupBox("2. Choose Destination")
        dest_layout = QVBoxLayout()
        self.add_to_current_radio = QRadioButton(f"Add to current database ({os.path.basename(self.main_app.db_file)})")
        self.create_new_radio = QRadioButton("Create a new database from CSV")
        self.add_to_current_radio.setChecked(True)
        
        self.new_db_widget = QWidget()
        new_db_layout = QHBoxLayout(self.new_db_widget)
        self.new_db_path_input = QLineEdit()
        self.new_db_path_input.setPlaceholderText("Path for new .db file...")
        self.browse_new_db_button = QPushButton("Browse...")
        new_db_layout.addWidget(self.new_db_path_input)
        new_db_layout.addWidget(self.browse_new_db_button)
        self.new_db_widget.setVisible(False)

        dest_layout.addWidget(self.add_to_current_radio)
        dest_layout.addWidget(self.create_new_radio)
        dest_layout.addWidget(self.new_db_widget)
        dest_group.setLayout(dest_layout)
        main_layout.addWidget(dest_group)

        # --- Run and Summarize ---
        summary_group = QGroupBox("3. Import & Summary")
        summary_layout = QVBoxLayout()
        self.start_import_button = QPushButton("Start Import")
        self.summary_output = QTextEdit()
        self.summary_output.setReadOnly(True)
        summary_layout.addWidget(self.start_import_button)
        summary_layout.addWidget(self.summary_output)
        summary_group.setLayout(summary_layout)
        main_layout.addWidget(summary_group)
        
        # --- Connections ---
        self.browse_csv_button.clicked.connect(self._browse_csv)
        self.browse_new_db_button.clicked.connect(self._browse_new_db)
        self.generate_template_button.clicked.connect(self._generate_template)
        self.create_new_radio.toggled.connect(self.new_db_widget.setVisible)
        self.start_import_button.clicked.connect(self._start_import)

    def _browse_csv(self):
        default_dir = os.path.join(os.path.expanduser("~"), 'Documents', DEFAULT_FOLDER_NAME)
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV File", default_dir, "CSV Files (*.csv)")
        if path: self.csv_path_input.setText(path)

    def _browse_new_db(self):
        default_dir = os.path.join(os.path.expanduser("~"), 'Documents', DEFAULT_FOLDER_NAME)
        path, _ = QFileDialog.getSaveFileName(self, "Create New Database", default_dir, "SQLite DB (*.db)")
        if path: self.new_db_path_input.setText(path)

    def _generate_template(self):
        default_dir = os.path.join(os.path.expanduser("~"), 'Documents')
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV Template", os.path.join(default_dir, "import_template.csv"), "CSV Files (*.csv)")
        if not path:
            return
        
        # Use the new, correct headers
        headers = ["Title", "Description", "Artifact Type", "Artifact Value", "OS", "MITRE", "Tags", "Notes", "Resources", "Content Modified At"]
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            self.summary_output.append(f"Template saved to {os.path.basename(path)}")
        except IOError as e:
            QMessageBox.critical(self, "Save Error", f"Could not save template file.\n\nError: {e}")

    def _start_import(self):
        csv_path = self.csv_path_input.text().strip()
        if not csv_path or not os.path.exists(csv_path):
            QMessageBox.warning(self, "Input Error", "Please select a valid CSV file.")
            return

        # Header Validation
        try:
            with _open_csv_with_fallback(csv_path) as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                required_headers = ['Title', 'Description', 'Artifact Type', 'Artifact Value', 'OS', 'MITRE', 'Tags', 'Notes', 'Resources']
                if 'Title' not in headers:
                    QMessageBox.critical(self, "Invalid CSV", "The CSV file is missing the required 'Title' column.")
                    return
                
                missing_headers = [h for h in required_headers if h not in headers]
                if missing_headers:
                    reply = QMessageBox.question(self, "Missing Columns", 
                        f"The CSV file is missing some columns: {', '.join(missing_headers)}.\n\n"
                        "The import will proceed, but data for these fields will be empty. Continue?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.No:
                        return
        except Exception as e:
            QMessageBox.critical(self, "File Read Error", f"Could not read the CSV file.\n\nError: {e}")
            return

        # Destination Logic
        target_db_path = ""
        if self.add_to_current_radio.isChecked():
            target_db_path = self.main_app.db_file
        else:
            target_db_path = self.new_db_path_input.text().strip()
            if not target_db_path:
                QMessageBox.warning(self, "Input Error", "Please specify a path for the new database.")
                return
            init_db(target_db_path)
            assets_folder_name = os.path.splitext(os.path.basename(target_db_path))[0] + "_assets"
            assets_path = os.path.join(os.path.dirname(target_db_path), assets_folder_name)
            os.makedirs(assets_path, exist_ok=True)

        self.summary_output.clear()
        self.summary_output.append("Starting import...")
        QApplication.processEvents()
        self.start_import_button.setEnabled(False)

        try:
            source_filename = os.path.basename(csv_path)
            summary = perform_bulk_import_from_csv(target_db_path, csv_path, source_filename)

            self.summary_output.append("\n--- Import Complete ---")
            self.summary_output.append(f"New entries added: {summary['inserted']}")
            self.summary_output.append(f"Conflicts imported as copies: {summary['conflicting']}")
            self.summary_output.append(f"Duplicate entries skipped: {summary['skipped']}")
            
            if self.create_new_radio.isChecked():
                self.main_app._switch_to_new_db(target_db_path)
                self.summary_output.append(f"\nSwitched to new database: {os.path.basename(target_db_path)}")
            
            if summary['new_ids']:
                undo_dialog = UndoDialog(target_db_path, summary['new_ids'], "CSV Import", self)
                if undo_dialog.exec():
                     self.summary_output.append("\nImport was undone.")

        except Exception as e:
            self.summary_output.append(f"\nAn error occurred during import: {e}")
        finally:
            self.start_import_button.setEnabled(True)


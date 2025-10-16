import sqlite3
import re
import os
from PySide6.QtWidgets import (
    QVBoxLayout, QPushButton, QListWidget, QLabel, QMessageBox, 
    QDialog, QDialogButtonBox, QCheckBox, QGroupBox, QHBoxLayout
)
from PySide6.QtCore import Qt
from .diff_dialog import DiffDialog
from .comparison_engine import compare_data_sources, perform_import
from .undo_dialog import UndoDialog

class ToggleSelectionListWidget(QListWidget):
    """A QListWidget that supports single-click to select/deselect items."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.ExtendedSelection)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            # Check for a simple click (no modifier keys)
            if not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                # Toggle selection state
                item.setSelected(not item.isSelected())
            else:
                # If modifier keys are pressed, use the default behavior
                super().mousePressEvent(event)
        else:
            # If clicking in empty space, clear all selections
            self.clearSelection()
            super().mousePressEvent(event)

class CompareDBDialog(QDialog):
    def __init__(self, current_db_path, external_db_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compare and Merge Databases")
        self.setMinimumSize(600, 650)
        
        self.db1_path = current_db_path
        self.db2_path = external_db_path
        self.main_app = parent
        self.comparison_report = None
        self.current_entries_dict = {}
        self.external_entries_dict = {}

        layout = QVBoxLayout(self)
        
        header = QLabel(f"<b>Comparing:</b> {os.path.basename(self.db1_path)} (Current) vs. {os.path.basename(self.db2_path)} (External)")
        layout.addWidget(header)
        
        # --- UI Setup with QGroupBox ---
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout()
        self.metrics_label = QLabel("Running comparison...")
        summary_layout.addWidget(self.metrics_label)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        unique_group = QGroupBox("Entries Unique to External DB")
        unique_layout = QVBoxLayout()
        self.select_all_unique_checkbox = QCheckBox("Select All Unique")
        self.unique_list = ToggleSelectionListWidget() # Use the new custom widget
        unique_layout.addWidget(self.select_all_unique_checkbox)
        unique_layout.addWidget(self.unique_list)
        unique_group.setLayout(unique_layout)
        layout.addWidget(unique_group)

        conflict_group = QGroupBox("Conflicting Entries")
        conflict_layout = QVBoxLayout()
        self.select_all_conflicts_checkbox = QCheckBox("Select All Conflicting")
        self.conflict_list = ToggleSelectionListWidget() # Use the new custom widget
        conflict_layout.addWidget(self.select_all_conflicts_checkbox)
        conflict_layout.addWidget(self.conflict_list)
        conflict_group.setLayout(conflict_layout)
        layout.addWidget(conflict_group)
        
        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        close_button = QPushButton("Close")

        self.view_diff_button = QPushButton("View Differences")
        self.view_diff_button.setEnabled(False)
        self.merge_button = QPushButton("Merge Selected Entries")

        button_layout.addWidget(close_button)
        button_layout.addStretch()
        button_layout.addWidget(self.view_diff_button)
        button_layout.addWidget(self.merge_button)
        
        layout.addLayout(button_layout)

        # --- Connections ---
        self.select_all_unique_checkbox.toggled.connect(lambda checked: self.unique_list.selectAll() if checked else self.unique_list.clearSelection())
        self.select_all_conflicts_checkbox.toggled.connect(lambda checked: self.conflict_list.selectAll() if checked else self.conflict_list.clearSelection())
        self.conflict_list.itemSelectionChanged.connect(self._update_diff_button_state)
        
        close_button.clicked.connect(self.reject) # Close button simply rejects the dialog
        self.view_diff_button.clicked.connect(self._view_differences)
        self.merge_button.clicked.connect(self._perform_merge)

        self._run_comparison()

    def _fetch_db_entries(self, db_path):
        """Loads all entries from a database into a list of dictionaries."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row 
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT 
                    e.*, 
                    (SELECT GROUP_CONCAT(t.name, ', ') 
                     FROM tags t 
                     JOIN entry_tags et ON t.id = et.tag_id 
                     WHERE et.entry_id = e.id 
                     ORDER BY t.name COLLATE NOCASE) as tags
                FROM entries e
            """)
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def _run_comparison(self):
        try:
            current_entries_list = self._fetch_db_entries(self.db1_path)
            external_entries_list = self._fetch_db_entries(self.db2_path)

            # --- Create the dictionary with lowercase keys for case-insensitive comparison ---
            self.current_entries_dict = {str(entry['title']).lower(): entry for entry in current_entries_list}
            
            self.comparison_report = compare_data_sources(self.current_entries_dict, external_entries_list)
            
            self.unique_list.clear()
            self.unique_list.addItems([entry['title'] for entry in self.comparison_report['new']])
            self.conflict_list.clear()
            self.conflict_list.addItems([entry['title'] for entry in self.comparison_report['conflicting']])
            
            summary_text = (
                f"<p><b>New entries to be added:</b> {len(self.comparison_report['new'])}</p>"
                f"<p><b>Conflicting entries to be added as copies:</b> {len(self.comparison_report['conflicting'])}</p>"
                f"<p><b>Duplicate entries to be skipped:</b> {len(self.comparison_report['duplicates'])}</p>"
            )
            self.metrics_label.setText(summary_text)

        except Exception as e:
            QMessageBox.critical(self, "Comparison Error", f"Could not compare databases:\n\n{e}")
            self.close()

    def _perform_merge(self):
        if not self.comparison_report: return

        selected_unique_titles = {item.text() for item in self.unique_list.selectedItems()}
        selected_conflict_titles = {item.text() for item in self.conflict_list.selectedItems()}
        
        entries_to_import = [
            e for e in self.comparison_report['new'] if e['title'] in selected_unique_titles
        ] + [
            e for e in self.comparison_report['conflicting'] if e['title'] in selected_conflict_titles
        ]

        if not entries_to_import:
            QMessageBox.warning(self, "No Selection", "Please select one or more entries to merge.")
            return

        if QMessageBox.question(self, "Confirm Merge", f"Are you sure you want to merge {len(entries_to_import)} selected entries?") == QMessageBox.Yes:
            source_filename = os.path.basename(self.db2_path)
            newly_added_ids = perform_import(self.db1_path, entries_to_import, source_filename)
            
            if newly_added_ids:
                undo_dialog = UndoDialog(self.db1_path, newly_added_ids, "Merge", self)
                if undo_dialog.exec() == QDialog.Accepted:
                    if self.main_app:
                        self.main_app.statusBar().showMessage("Merge operation was undone.", 3000)
            
            self.accept()

    def _update_diff_button_state(self):
        self.view_diff_button.setEnabled(len(self.conflict_list.selectedItems()) == 1)

    def _view_differences(self):
        selected_items = self.conflict_list.selectedItems()
        if not selected_items: return
        selected_title = selected_items[0].text()
        
        current_data_dict = self.current_entries_dict.get(selected_title.lower())
        external_data_dict = next((e for e in self.comparison_report['conflicting'] if e['title'].lower() == selected_title.lower()), None)

        if current_data_dict and external_data_dict:
            dialog = DiffDialog(selected_title, current_data_dict, external_data_dict, self)
            dialog.exec()


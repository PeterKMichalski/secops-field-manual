from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QGridLayout,
    QMessageBox, QInputDialog, QListWidgetItem, QGroupBox, QLineEdit, QDialogButtonBox
)
from PySide6.QtCore import Qt

class ManageSearchesDialog(QDialog):
    def __init__(self, searches_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Saved Searches")
        self.setMinimumSize(300, 500)
        
        self.searches = searches_dict.copy() # Work on a copy
        self.query_to_run = None

        main_layout = QVBoxLayout(self)

        # --- Search GroupBox ---
        search_group = QGroupBox("Filter and Manage Searches")
        group_layout = QVBoxLayout()
        
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter searches by name...")
        self.filter_input.textChanged.connect(self._filter_list)
        group_layout.addWidget(self.filter_input)
        
        self.search_list = QListWidget()
        # --- Enable multi-selection ---
        self.search_list.setSelectionMode(QListWidget.ExtendedSelection)
        group_layout.addWidget(self.search_list)
        
        search_group.setLayout(group_layout)
        main_layout.addWidget(search_group)

        # --- Action Buttons ---
        button_layout = QGridLayout()
        self.run_button = QPushButton("Run Selected")
        self.rename_button = QPushButton("Rename Selected")
        self.edit_button = QPushButton("Edit Query")
        self.delete_button = QPushButton("Delete Selected")
        
        button_layout.addWidget(self.run_button, 0, 0)           
        button_layout.addWidget(self.rename_button, 0, 1)
        button_layout.addWidget(self.edit_button, 1, 0)
        button_layout.addWidget(self.delete_button, 1, 1)
        main_layout.addLayout(button_layout)

        # --- OK/Cancel Buttons ---
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        main_layout.addWidget(dialog_buttons)

        # --- Connections ---
        self.run_button.clicked.connect(self._run_search)
        self.rename_button.clicked.connect(self._rename_search)
        self.edit_button.clicked.connect(self._edit_search)
        self.delete_button.clicked.connect(self._delete_search)
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)

        self._populate_list()

    def _populate_list(self):
        """Populates the list with all saved searches."""
        self.search_list.clear()
        for name, query in sorted(self.searches.items()):
            item = QListWidgetItem(name)
            item.setToolTip(query)
            self.search_list.addItem(item)
        self._filter_list()

    def _filter_list(self):
        """Filters the visible items in the list based on the filter text."""
        filter_text = self.filter_input.text().lower()
        for i in range(self.search_list.count()):
            item = self.search_list.item(i)
            item.setHidden(filter_text not in item.text().lower())

    def _run_search(self):
        """Runs the selected search and closes the dialog."""
        selected_items = self.search_list.selectedItems()
        if len(selected_items) != 1:
            QMessageBox.warning(self, "Selection Error", "Please select a single search to run.")
            return
        
        name = selected_items[0].text()
        self.query_to_run = self.searches.get(name)
        self.accept()

    def _rename_search(self):
        """Renames the selected search's friendly name."""
        selected_items = self.search_list.selectedItems()
        if len(selected_items) != 1:
            QMessageBox.warning(self, "Selection Error", "Please select a single search to rename.")
            return

        current_name = selected_items[0].text()
        current_query = self.searches[current_name]

        new_name, ok = QInputDialog.getText(self, "Rename Search", "Enter new name:", text=current_name)
        if ok and new_name and new_name != current_name:
            if new_name in self.searches:
                QMessageBox.warning(self, "Duplicate Name", "A search with this name already exists.")
                return
            del self.searches[current_name]
            self.searches[new_name] = current_query
            self._populate_list()
    
    def _edit_search(self):
        """Edits the selected search's query string."""
        selected_items = self.search_list.selectedItems()
        if len(selected_items) != 1:
            QMessageBox.warning(self, "Selection Error", "Please select a single search to edit.")
            return

        name = selected_items[0].text()
        current_query = self.searches[name]

        new_query, ok = QInputDialog.getText(self, "Edit Query", f"Enter new query for '{name}':", text=current_query)
        if ok and new_query:
            self.searches[name] = new_query
            self._populate_list()
    
    def _delete_search(self):
        """Deletes all selected searches."""
        selected_items = self.search_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select one or more searches to delete.")
            return
        
        count = len(selected_items)
        prompt = f"Are you sure you want to permanently delete {count} saved search{'es' if count > 1 else ''}?"
        reply = QMessageBox.question(self, "Confirm Delete", prompt, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            for item in selected_items:
                name = item.text()
                if name in self.searches:
                    del self.searches[name]
            self._populate_list()


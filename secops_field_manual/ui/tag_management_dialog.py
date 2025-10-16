from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QMessageBox, QInputDialog, QListWidgetItem, QLineEdit, QGroupBox,
    QDialogButtonBox
)
from PySide6.QtCore import Qt
from ..data.database import get_all_tags, rename_tag, delete_tag

class TagManagementDialog(QDialog):
    def __init__(self, db_file, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Tags")
        self.db_file = db_file
        self.setMinimumSize(400, 500)

        main_layout = QVBoxLayout(self)

        # --- Filter and List GroupBox ---
        list_group = QGroupBox("All Tags")
        list_layout = QVBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter tags...")
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.ExtendedSelection)
        list_layout.addWidget(self.filter_input)
        list_layout.addWidget(self.tag_list)
        list_group.setLayout(list_layout)
        main_layout.addWidget(list_group)

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        self.rename_button = QPushButton("Rename Selected")
        self.delete_button = QPushButton("Delete Selected")
        button_layout.addWidget(self.rename_button)
        button_layout.addWidget(self.delete_button)
        main_layout.addLayout(button_layout)

        # --- OK Button ---
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        main_layout.addWidget(dialog_buttons)

        # --- Connections ---
        self.filter_input.textChanged.connect(self._filter_list)
        self.rename_button.clicked.connect(self._rename_tag)
        self.delete_button.clicked.connect(self._delete_tag)
        dialog_buttons.accepted.connect(self.accept)

        self._load_tags()

    def _load_tags(self):
        """Fetches all tags from the DB and populates the list."""
        self.tag_list.clear()
        all_tags = get_all_tags(self.db_file)
        for tag_id, tag_name in all_tags:
            item = QListWidgetItem(tag_name)
            item.setData(Qt.UserRole, tag_id)
            self.tag_list.addItem(item)

    def _filter_list(self):
        """Hides or shows items in the list based on the filter text."""
        filter_text = self.filter_input.text().lower()
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            item.setHidden(filter_text not in item.text().lower())

    def _rename_tag(self):
        """Renames the selected tag."""
        selected_items = self.tag_list.selectedItems()
        if len(selected_items) != 1:
            QMessageBox.warning(self, "Selection Error", "Please select a single tag to rename.")
            return

        selected_item = selected_items[0]
        tag_id = selected_item.data(Qt.UserRole)
        current_name = selected_item.text()

        new_name, ok = QInputDialog.getText(self, "Rename Tag", "Enter new name:", text=current_name)
        
        if ok and new_name.strip() and new_name.strip().lower() != current_name.lower():
            success, error_message = rename_tag(self.db_file, tag_id, new_name.strip())
            if success:
                self._load_tags()
                self.filter_input.clear() # Clear filter to show the renamed tag
            else:
                QMessageBox.critical(self, "Error", f"Could not rename tag: {error_message}")
    
    def _delete_tag(self):
        """Deletes all selected tags."""
        selected_items = self.tag_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select one or more tags to delete.")
            return

        if len(selected_items) == 1:
            prompt = f"Are you sure you want to permanently delete the tag '{selected_items[0].text()}'?"
        else:
            prompt = f"Are you sure you want to permanently delete these {len(selected_items)} tags?"

        reply = QMessageBox.question(
            self, "Confirm Delete", 
            prompt + "\n\nThey will be removed from all associated entries.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for item in selected_items:
                tag_id = item.data(Qt.UserRole)
                delete_tag(self.db_file, tag_id)
            
            self._load_tags()

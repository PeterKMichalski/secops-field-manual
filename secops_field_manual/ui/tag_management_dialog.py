from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QPushButton, QMessageBox, QInputDialog, QLineEdit, QGroupBox, 
    QDialogButtonBox, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt
# Note: You will need to add 'get_all_tags_with_counts' and 'merge_tags' to your database.py
from ..data.database import get_all_tags_with_counts, rename_tag, delete_tag, merge_tags

class TagManagementDialog(QDialog):
    def __init__(self, db_file, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Tags")
        self.db_file = db_file
        self.resize(500, 600)

        main_layout = QVBoxLayout(self)

        # --- Filter and List GroupBox ---
        list_group = QGroupBox("All Tags")
        list_layout = QVBoxLayout()
        
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter tags...")
        
        # Setup Table
        self.tag_table = QTableWidget()
        self.tag_table.setColumnCount(2)
        self.tag_table.setHorizontalHeaderLabels(["Tag Name", "Count"])
        self.tag_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tag_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tag_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tag_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tag_table.setSortingEnabled(True) # Enable sorting by clicking headers
        self.tag_table.verticalHeader().setVisible(False)
        self.tag_table.setShowGrid(False)
        self.tag_table.setAlternatingRowColors(True)

        list_layout.addWidget(self.filter_input)
        list_layout.addWidget(self.tag_table)
        list_group.setLayout(list_layout)
        main_layout.addWidget(list_group)

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        self.merge_button = QPushButton("Merge Selected")
        self.rename_button = QPushButton("Rename")
        self.delete_button = QPushButton("Delete")
        
        button_layout.addWidget(self.merge_button)
        button_layout.addWidget(self.rename_button)
        button_layout.addWidget(self.delete_button)
        main_layout.addLayout(button_layout)

        # --- OK Button ---
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Close)
        main_layout.addWidget(dialog_buttons)

        # --- Connections ---
        self.filter_input.textChanged.connect(self._filter_list)
        self.merge_button.clicked.connect(self._merge_tags)
        self.rename_button.clicked.connect(self._rename_tag)
        self.delete_button.clicked.connect(self._delete_tag)
        dialog_buttons.rejected.connect(self.accept) # Close button

        self._load_tags()

    def _load_tags(self):
        """Fetches all tags with counts from the DB and populates the table."""
        self.tag_table.setSortingEnabled(False) # Disable during load to prevent jumps
        self.tag_table.clearContents()
        
        # Fetch data: [(id, name, count), ...]
        all_tags = get_all_tags_with_counts(self.db_file)
        self.tag_table.setRowCount(len(all_tags))

        for row, (tag_id, tag_name, count) in enumerate(all_tags):
            # Column 0: Name
            name_item = QTableWidgetItem(tag_name)
            name_item.setData(Qt.UserRole, tag_id) # Store ID hidden
            self.tag_table.setItem(row, 0, name_item)

            # Column 1: Count
            # Use setData(Qt.DisplayRole, value) for proper numerical sorting
            count_item = QTableWidgetItem()
            count_item.setData(Qt.DisplayRole, count) 
            count_item.setTextAlignment(Qt.AlignCenter)
            self.tag_table.setItem(row, 1, count_item)

        self.tag_table.setSortingEnabled(True)
        self._filter_list() # Re-apply filter if exists

    def _filter_list(self):
        """Hides rows based on filter text."""
        filter_text = self.filter_input.text().lower()
        for row in range(self.tag_table.rowCount()):
            item = self.tag_table.item(row, 0) # Check name column
            show = filter_text in item.text().lower()
            self.tag_table.setRowHidden(row, not show)

    def _merge_tags(self):
        """Merges multiple selected tags into one."""
        selected_rows = sorted(set(index.row() for index in self.tag_table.selectedIndexes()))
        
        if len(selected_rows) < 2:
            QMessageBox.warning(self, "Selection Error", "Please select at least two tags to merge.")
            return

        # Gather data
        tags_to_merge = [] # List of (id, name)
        names_display = []
        for row in selected_rows:
            tag_id = self.tag_table.item(row, 0).data(Qt.UserRole)
            tag_name = self.tag_table.item(row, 0).text()
            tags_to_merge.append(tag_id)
            names_display.append(tag_name)

        # Prompt for target name
        # Default to the first selected name as a suggestion
        default_name = names_display[0]
        new_name, ok = QInputDialog.getText(
            self, 
            "Merge Tags", 
            f"Merge {len(tags_to_merge)} tags ({', '.join(names_display[:3])}...) into:", 
            text=default_name
        )

        if ok and new_name.strip():
            target_name = new_name.strip()
            reply = QMessageBox.question(
                self, "Confirm Merge",
                f"Are you sure you want to merge {len(tags_to_merge)} tags into '{target_name}'?\n\n"
                "All associated entries will be updated. This cannot be undone.",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                success, msg = merge_tags(self.db_file, tags_to_merge, target_name)
                if success:
                    self._load_tags()
                    QMessageBox.information(self, "Success", f"Tags merged into '{target_name}'.")
                else:
                    QMessageBox.critical(self, "Error", f"Merge failed: {msg}")

    def _rename_tag(self):
        """Renames the selected tag."""
        selected_rows = list(set(index.row() for index in self.tag_table.selectedIndexes()))
        if len(selected_rows) != 1:
            QMessageBox.warning(self, "Selection Error", "Please select a single tag to rename.")
            return

        row = selected_rows[0]
        tag_id = self.tag_table.item(row, 0).data(Qt.UserRole)
        current_name = self.tag_table.item(row, 0).text()

        new_name, ok = QInputDialog.getText(self, "Rename Tag", "Enter new name:", text=current_name)
        
        if ok and new_name.strip() and new_name.strip() != current_name:
            success, error_message = rename_tag(self.db_file, tag_id, new_name.strip())
            if success:
                self._load_tags()
            else:
                QMessageBox.critical(self, "Error", f"Could not rename tag: {error_message}")
    
    def _delete_tag(self):
        """Deletes selected tags."""
        selected_rows = list(set(index.row() for index in self.tag_table.selectedIndexes()))
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select one or more tags to delete.")
            return

        count = len(selected_rows)
        msg = f"Are you sure you want to delete {count} tag{'s' if count > 1 else ''}?"
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            msg + "\n\nEntries will remain but will no longer have these tags.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for row in selected_rows:
                tag_id = self.tag_table.item(row, 0).data(Qt.UserRole)
                delete_tag(self.db_file, tag_id)
            
            self._load_tags()

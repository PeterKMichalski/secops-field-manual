import sqlite3
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, 
    QMessageBox, QDialogButtonBox, QLabel
)
from ..data.database import delete_entry

class UndoDialog(QDialog):
    def __init__(self, db_file, new_ids, operation_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Operation Summary")
        self.db_file = db_file
        self.new_ids = new_ids
        
        main_layout = QVBoxLayout(self)
        
        count = len(self.new_ids)
        entry_text = f"entr{'y' if count == 1 else 'ies'}"
        
        main_layout.addWidget(QLabel(f"The {operation_name} operation successfully added {count} new {entry_text}."))
        
        self.entry_list = QListWidget()
        main_layout.addWidget(self.entry_list)
        
        button_layout = QHBoxLayout()
        
        self.undo_button = QPushButton(f"Undo this {operation_name}")
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)

        button_layout.addWidget(self.undo_button)
        button_layout.addStretch() # This spacer pushes the OK button to the right
        button_layout.addWidget(ok_button)
        
        main_layout.addLayout(button_layout)
        
        # Connect signals
        self.undo_button.clicked.connect(self._perform_undo)
        ok_button.clicked.connect(self.reject)

        self._populate_list()

    def _populate_list(self):
        """Fetches the titles of the newly added entries."""
        if not self.new_ids: return
        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()
        try:
            # Create a string of placeholders for the query
            placeholders = ','.join('?' for _ in self.new_ids)
            cur.execute(f"SELECT title FROM entries WHERE id IN ({placeholders})", self.new_ids)
            titles = [row[0] for row in cur.fetchall()]
            self.entry_list.addItems(titles)
        finally:
            conn.close()

    def _perform_undo(self):
        """Deletes the newly added entries and accepts the dialog."""
        for entry_id in self.new_ids:
            delete_entry(self.db_file, entry_id)
        # self.accept() will be called automatically by the AcceptRole button
        self.accept()


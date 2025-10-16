from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QDialogButtonBox, QTextEdit, QHBoxLayout, QGroupBox
)
from PySide6.QtCore import Qt

class DiffDialog(QDialog):
    def __init__(self, entry_title, current_data, external_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Differences for '{entry_title}'")
        self.setMinimumSize(800, 600)

        main_layout = QVBoxLayout(self)
        
        comparison_group = QGroupBox("Field Comparison")
        group_layout = QVBoxLayout()
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<b>Field</b>"), 1)
        header_layout.addWidget(QLabel("<b>Current Version</b>"), 2)
        header_layout.addWidget(QLabel("<b>External Version</b>"), 2)
        group_layout.addLayout(header_layout)

        # --- Updated field list and indices ---
        fields_to_compare = {
            "Description": "description",
            "Artifact Type": "artifact_type",
            "Artifact Value": "artifact_value",
            "OS": "os", 
            "MITRE": "mitre", 
            "Notes": "notes", 
            "Tags": "tags", 
            "Resources": "resources"
        }

        for field_name, key in fields_to_compare.items():
            current_value = str(current_data.get(key) or "")
            external_value = str(external_data.get(key) or "")

            current_text_edit = QTextEdit(current_value)
            current_text_edit.setReadOnly(True)
            external_text_edit = QTextEdit(external_value)
            external_text_edit.setReadOnly(True)
            
            field_label = QLabel(f"<b>{field_name}</b>")

            if current_value != external_value:
                current_text_edit.setStyleSheet("background-color: #4d94ff; color: black;")
                external_text_edit.setStyleSheet("background-color: #ffb84d; color: black;")

            row_layout = QHBoxLayout()
            row_layout.addWidget(field_label, 1)
            row_layout.addWidget(current_text_edit, 2)
            row_layout.addWidget(external_text_edit, 2)
            group_layout.addLayout(row_layout)

        # --- Image Indicator ---
        current_has_image = bool(current_data.get("image_path"))
        external_has_image = bool(external_data.get("image_path"))
        current_image_label = QLabel("Yes" if current_has_image else "No")
        external_image_label = QLabel("Yes" if external_has_image else "No")
        field_label = QLabel("<b>Image Present</b>")

        if current_has_image != external_has_image:
             current_image_label.setStyleSheet("background-color: #dbeaff; color: black; padding: 5px;")
             external_image_label.setStyleSheet("background-color: #ffb84d; color: black; padding: 5px;")

        row_layout = QHBoxLayout()
        row_layout.addWidget(field_label, 1)
        row_layout.addWidget(current_image_label, 2)
        row_layout.addWidget(external_image_label, 2)
        group_layout.addLayout(row_layout)
        
        comparison_group.setLayout(group_layout)
        main_layout.addWidget(comparison_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        main_layout.addStretch()
        main_layout.addWidget(buttons)

import os
import re
import shutil
import html
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QTextEdit, QTextBrowser, QComboBox,
    QLabel, QPushButton, QDialogButtonBox, QFileDialog,
    QInputDialog, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QSizePolicy,
    QCompleter, QAbstractItemView, QGroupBox, QStyle
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QSize, QStringListModel
from .constants import OPERATING_SYSTEMS, MITRE_ATTACK_TACTICS, ARTIFACT_TYPES
from .compare_dialog import CompareDBDialog
from ..data.database import get_mitre_order, get_all_tags, get_tags_for_entry
from .utilities import resource_path


class TagLineEdit(QLineEdit):
    """A QLineEdit that processes tags on Enter but does not close the parent dialog."""
    def keyPressEvent(self, event):
        # Check if the key pressed is Enter or Return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # If it is, emit the returnPressed signal that we're using
            self.returnPressed.emit()
            # Crucially, accept the event to stop it from bubbling up to the dialog
            event.accept()
        else:
            # For all other keys, perform the default action
            super().keyPressEvent(event)

# --- Custom List Widget for Single-Click Toggle ---
class ToggleListWidget(QListWidget):
    """A QListWidget customized for single-click item selection/deselection."""
    
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.addItems(items)

    def mousePressEvent(self, event):
        """Override to handle single-click toggle."""
        item = self.itemAt(event.pos())
        if item:
            # Check if Ctrl/Cmd/Shift is NOT pressed (i.e., this is a simple click)
            if not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                # If the item is already selected, deselect it. Otherwise, select it.
                if item.isSelected():
                    item.setSelected(False)
                else:
                    item.setSelected(True)
            else:
                # If modifier keys are pressed, use default Qt selection behavior
                super().mousePressEvent(event)
        else:
            # If clicking in empty space, clear selection
            self.clearSelection()
            super().mousePressEvent(event)
            
    def get_selected_tags(self):
        """Returns selected items as a comma-separated string, preserving MITRE order."""
        selected_titles = {item.text() for item in self.selectedItems()}
        
        # Use the utility function to order the tags correctly
        ordered_tags = get_mitre_order(", ".join(selected_titles))
        return ordered_tags

# --- Entry Editor Dialog ---
class EntryEditor(QDialog):
    def __init__(self, db_file, parent=None, existing_entry=None):
        super().__init__(parent)
        self.setWindowTitle("Add / Edit Entry")
        self.setMinimumSize(800, 700)
        
        self.db_file = db_file
        self.image_path = ""
        self.entry_id = None

        main_layout = QVBoxLayout(self)
        
        # --- Title Group ---
        title_group = QGroupBox("Title")
        title_layout = QVBoxLayout()
        self.title_input = QLineEdit()
        title_layout.addWidget(self.title_input)
        title_group.setLayout(title_layout)
        main_layout.addWidget(title_group)

        # --- Two-Column Layout ---
        columns_layout = QHBoxLayout()
        left_column_layout = QVBoxLayout()
        right_column_layout = QVBoxLayout()
        columns_layout.addLayout(left_column_layout, 1) # Metadata column
        columns_layout.addLayout(right_column_layout, 2) # Content column
        main_layout.addLayout(columns_layout)

        # --- Create all widgets ---
        self.os_input = QComboBox()
        self.os_input.insertItem(0, "")
        self.os_input.addItems(OPERATING_SYSTEMS[1:])
        self.os_input.setCurrentIndex(0)

        self.mitre_list_widget = ToggleListWidget(MITRE_ATTACK_TACTICS)
        
        self.artifact_type_input = QComboBox()
        # Add a blank item to the beginning of the list
        self.artifact_type_input.insertItem(0, "")
        self.artifact_type_input.addItems(ARTIFACT_TYPES)
        self.artifact_type_input.setCurrentIndex(0) # Default to blank
        self.artifact_value_input = QTextEdit()
        self.artifact_value_input.setMinimumHeight(26)
        self.artifact_value_input.setPlaceholderText("Enter the value for the selected artifact type...")
        
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Add notes here. You can use [[Internal Links]].")
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Add a description. You can also use [[Internal Links]].")
        self.resources_input = QTextEdit()
        self.resources_input.setPlaceholderText("e.g., [Markdown Link](example.com)")

        # Tag UI Widgets
        all_tag_names = [tag[1] for tag in get_all_tags(self.db_file)]
        self.tag_input = TagLineEdit()
        self.tag_input.setPlaceholderText("Type tags and press Enter...")
        completer = QCompleter(all_tag_names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.tag_input.setCompleter(completer)
        self.tag_input.returnPressed.connect(self._process_tags)
        self.tag_list_widget = QListWidget()
        self.tag_list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.remove_tag_button = QPushButton("Remove Selected Tag(s)")
        self.remove_tag_button.clicked.connect(self._remove_selected_tags)
        
        # --- Populate LEFT Column (Metadata) ---
        metadata_group = QGroupBox("Metadata")
        metadata_layout = QVBoxLayout()
        metadata_layout.addWidget(QLabel("Operating System:"))
        metadata_layout.addWidget(self.os_input)
        metadata_layout.addWidget(QLabel("MITRE Tactic (Multi-Select):"))
        metadata_layout.addWidget(self.mitre_list_widget)
        metadata_group.setLayout(metadata_layout)
        left_column_layout.addWidget(metadata_group)
        
        tags_group = QGroupBox("Tags")
        tags_layout = QVBoxLayout()
        tags_layout.addWidget(self.tag_input)
        tags_layout.addWidget(self.tag_list_widget)
        tags_layout.addWidget(self.remove_tag_button)
        tags_group.setLayout(tags_layout)
        left_column_layout.addWidget(tags_group)
        left_column_layout.addStretch()

        # --- Populate RIGHT Column (Content) ---
        artifact_group = QGroupBox("Artifact")
        artifact_layout = QVBoxLayout()
        artifact_layout.addWidget(QLabel("Type:"))
        artifact_layout.addWidget(self.artifact_type_input)
        artifact_layout.addWidget(QLabel("Value:"))
        artifact_layout.addWidget(self.artifact_value_input)
        artifact_group.setLayout(artifact_layout)
        right_column_layout.addWidget(artifact_group)

        desc_group = QGroupBox("Description")
        desc_layout = QVBoxLayout()
        desc_layout.addWidget(self.desc_input)
        desc_group.setLayout(desc_layout)
        right_column_layout.addWidget(desc_group)

        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout()
        notes_layout.addWidget(self.notes_input)
        notes_group.setLayout(notes_layout)
        right_column_layout.addWidget(notes_group)
        
        resources_group = QGroupBox("Resources")
        resources_layout = QVBoxLayout()
        resources_layout.addWidget(self.resources_input)
        resources_group.setLayout(resources_layout)
        right_column_layout.addWidget(resources_group)
        
        # --- Bottom section for Image and Buttons ---
        self.image_label = QLabel("No image selected")
        self.image_button = QPushButton("Attach Image")
        self.image_button.clicked.connect(self.select_image)
        self.remove_image_button = QPushButton("Remove Image")
        self.remove_image_button.clicked.connect(self._remove_image)
        
        image_button_layout = QHBoxLayout()
        image_button_layout.addWidget(self.image_button)
        image_button_layout.addWidget(self.remove_image_button)
        button_container = QWidget()
        button_container.setLayout(image_button_layout)
    
        # Assemble the bottom layout
        bottom_section_layout = QHBoxLayout()
        bottom_section_layout.addWidget(button_container)
        bottom_section_layout.addWidget(self.image_label)
        
        main_layout.addLayout(bottom_section_layout)

        # OK/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        if existing_entry:
            self._load_existing_data(existing_entry)

    def _add_tag_from_input(self):
        """Adds the tag from the input line to the list widget."""
        tag_text = self.tag_input.text().strip()
        if tag_text:
            # Prevent adding duplicate tags to the list
            items = self.tag_list_widget.findItems(tag_text, Qt.MatchFixedString)
            if not items:
                self.tag_list_widget.addItem(tag_text)
            self.tag_input.clear()

    def _remove_selected_tags(self):
        """Removes all selected tags from the list widget."""
        for item in self.tag_list_widget.selectedItems():
            self.tag_list_widget.takeItem(self.tag_list_widget.row(item))

    def _load_existing_data(self, existing_entry):
        """Loads data from an existing entry into the form fields."""
        # Use dictionary-style access (e.g., existing_entry['key']) instead of .get()
        self.entry_id = existing_entry['id']
        self.title_input.setText(existing_entry['title'] or '')
        self.desc_input.setPlainText(existing_entry['description'] or '')
        
        # Set the artifact type
        artifact_type = existing_entry['artifact_type']
        if artifact_type:
            index = self.artifact_type_input.findText(artifact_type)
            if index >= 0:
                self.artifact_type_input.setCurrentIndex(index)
        else:
            self.artifact_type_input.setCurrentIndex(0)
        
        self.artifact_value_input.setText(existing_entry['artifact_value'] or '')
        self.image_path = existing_entry['image_path'] or ''
        self.notes_input.setPlainText(existing_entry['notes'] or '')
        self.resources_input.setText(existing_entry['resources'] or '')

        # Set the OS
        os_val = existing_entry['os']
        if os_val:
            index = self.os_input.findText(os_val)
            if index >= 0:
                self.os_input.setCurrentIndex(index)
        else:
            self.os_input.setCurrentIndex(0)

        # Set the selected items for the MITRE QListWidget
        mitre_val = existing_entry['mitre'] or ''
        if mitre_val:
            selected_mitre_tactics = {t.strip() for t in mitre_val.split(',') if t.strip()}
            for i in range(self.mitre_list_widget.count()):
                item = self.mitre_list_widget.item(i)
                if item.text() in selected_mitre_tactics:
                    item.setSelected(True)

        entry_tags = get_tags_for_entry(self.db_file, self.entry_id)
        self.tag_list_widget.addItems(entry_tags)

        self.image_label.setText(os.path.basename(self.image_path) if self.image_path else "No image selected")

    def get_data(self):
        tags = [self.tag_list_widget.item(i).text() for i in range(self.tag_list_widget.count())]
        return (
            self.title_input.text().strip(),
            self.desc_input.toPlainText(),
            self.artifact_type_input.currentText(),
            self.artifact_value_input.toPlainText(),
            self.image_path,
            self.os_input.currentText(),
            self.mitre_list_widget.get_selected_tags(),
            self.notes_input.toPlainText(),
            self.resources_input.toPlainText().strip(),
            tags
        )

    def select_image(self):
        default_dir = os.path.join(os.path.expanduser("~"), 'Documents')
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", default_dir, "Images (*.png *.jpg *.jpeg *.bmp)")

        if file_path:
            # --- IMAGE HANDLING LOGIC ---

            # First, perform the size check
            MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
            if os.path.getsize(file_path) > MAX_IMAGE_SIZE_BYTES:
                QMessageBox.warning(self, "Image Too Large", f"Image is larger than {MAX_IMAGE_SIZE_BYTES / 1024 / 1024:.0f} MB.")
                return

            # 1. Define the assets folder path, named after the database
            db_dir = os.path.dirname(self.db_file)
            db_name = os.path.basename(self.db_file)
            assets_folder_name = os.path.splitext(db_name)[0] + "_assets"
            assets_path = os.path.join(db_dir, assets_folder_name)

            # 2. Create the assets folder if it doesn't exist
            os.makedirs(assets_path, exist_ok=True)

            # 3. Create a unique filename for the copy to avoid overwriting
            original_filename = os.path.basename(file_path)
            base, ext = os.path.splitext(original_filename)
            counter = 1
            new_filename = original_filename
            destination_path = os.path.join(assets_path, new_filename)

            while os.path.exists(destination_path):
                new_filename = f"{base}_{counter}{ext}"
                destination_path = os.path.join(assets_path, new_filename)
                counter += 1
            
            # 4. Copy the file to the assets folder
            try:
                shutil.copy2(file_path, destination_path)
            except Exception as e:
                QMessageBox.critical(self, "Copy Error", f"Could not copy image to assets folder.\n\nError: {e}")
                return

            # 5. Store the NEW, RELATIVE filename (not the full path)
            self.image_path = new_filename 
            self.image_label.setText(new_filename)

    def _remove_image(self):
        """Clears the currently attached image path."""
        self.image_path = ""
        self.image_label.setText("No image selected")

    def accept(self):
        """Override the default accept behavior to add validation."""
        title = self.title_input.text().strip()
        description = self.desc_input.toPlainText().strip()
        notes = self.notes_input.toPlainText().strip()
        artifact_value = self.artifact_value_input.toPlainText()

        # --- Validation Block ---
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please provide a title.")
            return

        if self.os_input.currentIndex() == 0:
            QMessageBox.warning(self, "Missing Field", "Please select an Operating System.")
            return

        if self.artifact_type_input.currentIndex() == 0:
            QMessageBox.warning(self, "Missing Field", "Please select an Artifact Type.")
            return

        if len(title) > 255:
            QMessageBox.warning(self, "Title Too Long", "The title cannot exceed 255 characters.")
            return

        LARGE_TEXT_THRESHOLD = 100_000
        if len(description) > LARGE_TEXT_THRESHOLD or len(notes) > LARGE_TEXT_THRESHOLD or len(artifact_value) > LARGE_TEXT_THRESHOLD:
            reply = QMessageBox.question(
                self, "Large Text Detected",
                "The text in one of the fields is very long. This may affect UI performance.\n\nAre you sure you want to continue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        super().accept()

    def _process_tags(self):
        """
        Processes the text in the tag input field, splitting by comma only,
        and adds each tag to the list widget.
        """
        # Split the string by comma or space, and filter out any empty strings
        tags_to_add = [tag.strip() for tag in self.tag_input.text().split(',') if tag.strip()]
        
        if not tags_to_add:
            return

        for tag_text in tags_to_add:
            items = self.tag_list_widget.findItems(tag_text, Qt.MatchFixedString)
            if not items:
                self.tag_list_widget.addItem(tag_text)
        
        self.tag_input.clear()

# --- Generic Help / Info Dialog ---
class HelpDialog(QDialog):
    def __init__(self, title, html_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(560, 500)

        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setHtml(html_content)
        browser.setOpenLinks(False)
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)


# --- About Dialog ---
class AboutDialog(QDialog):
    # Update the __init__ method to accept the new arguments
    def __init__(self, author, version, release_date, thanks, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About SecOps Field Manual")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout(self)
        
        header_label = QLabel("<h2>SecOps Field Manual</h2>")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        
        # Use the arguments passed to the method
        info_text = f"""
        <p><b>Author:</b> {author}</p>
        <p><b>Version:</b> {version}</p>
        <p><b>Release Date:</b> {release_date}</p>
        <p><b>Thanks:</b> {thanks}</p>
        <p>A portable, personal knowledge base for security operations — quickly store, search, and reference forensic artifacts, technical procedures, and investigation notes.</p>
        """
        info_label = QLabel(info_text)
        info_label.setTextFormat(Qt.RichText)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
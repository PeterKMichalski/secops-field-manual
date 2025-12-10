import sys
import os
import re
import sqlite3
import urllib.parse
import traceback
import csv
import markdown
from pygments.formatters import HtmlFormatter
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QListWidget, QTextEdit, QLabel, QLineEdit,
    QComboBox, QMessageBox, QDialog, QFormLayout, QSplitter, QMenuBar, QMenu,
    QSpacerItem, QFileDialog, QSizePolicy, QScrollArea, QToolBar, QGroupBox,
    QApplication, QStyle, QInputDialog
)
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QPixmap, QDesktopServices, QAction, QIcon, QFontMetrics, QFont, QPalette
from PySide6.QtCore import Qt, QUrl, QSize, QTimer

from ..data.database import (
    init_db, search_entries, insert_entry, update_entry, delete_entry,
    is_valid_sqlite_file, check_db_schema, get_tags_for_entry, get_database_summary,
    get_all_entries_for_export
)
from .dialogs import EntryEditor, AboutDialog, CompareDBDialog # Assuming CompareDBDialog is moved to dialogs.py
from .constants import OPERATING_SYSTEMS, MITRE_ATTACK_TACTICS, DEFAULT_DB_FILENAME, DEFAULT_FOLDER_NAME, APP_AUTHOR, APP_VERSION, APP_RELEASE_DATE, APP_THANKS, ARTIFACT_TYPES
from .utilities import resource_path, parse_search_query, save_last_db_path, load_saved_searches, save_searches, load_search_history, record_search_in_history, save_zoom_level, load_zoom_level
from .custom_widgets import ClickableImage, SearchLineEdit, FieldCompleter
from .tag_management_dialog import TagManagementDialog
from .summary_dialog import SummaryDialog
from .import_dialog import ImportDialog
from .manage_searches_dialog import ManageSearchesDialog



# --- Custom TextEdit for placeholders ---
# (Keep this class definition here as it is tightly coupled with FieldManualApp methods)
class PlaceholderTextEdit(QTextEdit):
    def __init__(self, parent_app=None):
        super().__init__()
        self.parent_app = parent_app
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setLineWrapMode(QTextEdit.NoWrap) 
        self.setReadOnly(True) 
        
        self.copy_button = QPushButton(self)
        style = QApplication.style()
        copy_icon = style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        self.copy_button.setIcon(copy_icon)
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.setFixedSize(12, 15)
        self.copy_button.setToolTip("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_text_to_clipboard)

    def copy_text_to_clipboard(self):
        QApplication.clipboard().setText(self.toPlainText())
        if self.parent_app and self.parent_app.statusBar():
            self.parent_app.statusBar().showMessage("Artifact value copied to clipboard.", 3000)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        button_size = self.copy_button.size()
        frame_width = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        self.copy_button.move(
            self.rect().right() - frame_width - button_size.width() - 2,
            self.rect().top() + frame_width + 2
        )

    def highlight_placeholders(self, text):
        self.clear()
        self.setPlainText(text)
        cursor = self.textCursor()
        fmt_clear = QTextCharFormat()
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(fmt_clear)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#000000"))
        fmt.setBackground(QColor("#ffb84d"))
        document_text = self.toPlainText()
        for match in re.finditer(r"\{\{.*?\}\}", document_text):
            start, end = match.start(), match.end()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(fmt)

    def mouseDoubleClickEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        click_pos = cursor.position()
        document_text = self.toPlainText()
        start_match = document_text.rfind("{{", 0, click_pos + 1)
        if start_match != -1:
            end_match = document_text.find("}}", start_match)
            if end_match != -1:
                end_match += 2
                if start_match <= click_pos <= end_match:
                    new_cursor = self.textCursor()
                    new_cursor.setPosition(start_match)
                    new_cursor.setPosition(end_match, QTextCursor.KeepAnchor)
                    self.setTextCursor(new_cursor)
                    word = new_cursor.selectedText()
                    if re.match(r"\{\{.*?\}\}", word):
                        self.setReadOnly(False)
                        self.replace_placeholder(word)
                        self.setReadOnly(True)
                        event.accept()
                        return
        super().mouseDoubleClickEvent(event)
        event.ignore()

    def replace_placeholder(self, word):
        from PySide6.QtWidgets import QInputDialog, QLineEdit
        new_value, ok = QInputDialog.getText(
            self, "Replace Placeholder", f"Replace {word} with:", QLineEdit.Normal, ""
        )
        if ok and self.parent_app:
            self.parent_app.current_text = self.parent_app.current_text.replace(word, new_value, 1)
            self.parent_app.display_placeholders(self.parent_app.current_text)
            updated_text = self.parent_app.current_text
            QApplication.clipboard().setText(updated_text)
            if self.parent_app.statusBar():
                self.parent_app.statusBar().showMessage("Artifact value updated and copied to clipboard.", 3000)

# --- Main Application ---
class FieldManualApp(QMainWindow):
    def __init__(self, db_file):
        super().__init__()
        self.statusBar().showMessage("Ready", 0)
        self.resize(1200, 800)
        
        self.db_file = db_file
        self._initialize_database(db_file)
        
        self.current_entry_id = None
        self.current_text = ""

        self.setWindowTitle(f"SecOps Field Manual - [{os.path.basename(self.db_file)}]")
        self.setAcceptDrops(True)
        self._setup_menubar()
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Search Toolbar
        self.search_toolbar = QToolBar("Search Toolbar")
        self.search_toolbar.setMovable(False)
        
        # 1. Use our new custom SearchLineEdit
        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("Search... (type and press Right Arrow to complete fields)")
        
        # 2. Define the list of fields for completion
        positive_fields = [
            "title:", "os:", "mitre:", "tags:", "artifact_type:", "artifact_value:", "description:", "notes:", "resources:"
            "added_after:", "added_before:", "modified_after:", "modified_before:", "source:"
        ]
        negative_fields = [f"-{field}" for field in positive_fields]
        all_search_fields = positive_fields + negative_fields
        
        # 3. Create and set our custom completer
        completer = FieldCompleter(all_search_fields, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        
        self.search_input.setCompleter(completer)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self.search)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_toolbar.addWidget(self.search_input)

        # 1. "Save Search" Button
        self.save_search_button = QPushButton()
        save_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        self.save_search_button.setIcon(save_icon)
        self.save_search_button.setToolTip("Save Current Search")
        self.save_search_button.setEnabled(False) # Disabled until user types
        
        # 2. "Favorite Searches" Dropdown Menu
        self.favorites_button = QPushButton("Favorites")
        self.favorites_menu = QMenu(self)
        self.favorites_button.setMenu(self.favorites_menu)
        
        # Add the new buttons to the toolbar
        self.search_toolbar.addWidget(self.save_search_button)
        self.search_toolbar.addWidget(self.favorites_button)

        # Enable "Save" button only when there's text
        self.search_input.textChanged.connect(
            lambda text: self.save_search_button.setEnabled(bool(text.strip()))
        )
        self.save_search_button.clicked.connect(self._save_new_search)

        main_layout.addWidget(self.search_toolbar)
        
        horizontal_splitter = QSplitter(Qt.Horizontal)
        self._setup_left_panel()
        horizontal_splitter.addWidget(self.left_widget)
        self._setup_right_panel()
        horizontal_splitter.addWidget(self.right_panel_container)
        horizontal_splitter.setSizes([250, 850])
        main_layout.addWidget(horizontal_splitter)

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._handle_resize_finished)

        self.zoom_level = load_zoom_level()
        self._apply_zoom()

        self._load_favorites_menu()
        self.search()

    def _initialize_database(self, db_file):
        if not os.path.exists(db_file):
            init_db(db_file)
        elif not is_valid_sqlite_file(db_file) or not check_db_schema(db_file):
            QMessageBox.critical(self, "Database Error", f"'{os.path.basename(db_file)}' is not a valid or compatible database.")
            sys.exit(1)
        init_db(db_file)

    # --- Database File Management ---

    def create_new_db(self):
        default_dir = os.path.join(os.path.expanduser("~"), 'Documents')
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Create New Field Notes Database",
            default_dir,
            "SQLite DB (*.db)"
        )
        
        if file_path:
            if os.path.exists(file_path):
                reply = QMessageBox.question(self, "Confirm Overwrite",
                                           f"The database '{os.path.basename(file_path)}' already exists. Do you want to overwrite it?",
                                           QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    return

            self.db_file = file_path
            init_db(self.db_file)
            save_last_db_path(self.db_file)

            # Proactively create the associated assets folder
            db_dir = os.path.dirname(file_path)
            db_name = os.path.basename(file_path)
            assets_folder_name = os.path.splitext(db_name)[0] + "_assets"
            assets_path = os.path.join(db_dir, assets_folder_name)
            os.makedirs(assets_path, exist_ok=True)

            self.setWindowTitle(f"SecOps Field Manual - [{os.path.basename(self.db_file)}]")
            self.statusBar().showMessage(f"New database created: {os.path.basename(self.db_file)}.", 5000)
            self.search()
            self.clear_entry_view()

    def load_db(self):
        default_dir = os.path.join(os.path.expanduser("~"), 'Documents', DEFAULT_FOLDER_NAME)

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Existing Field Notes Database",
            default_dir,
            "SQLite DB (*.db)"
        )
        
        if file_path and file_path != self.db_file:
            self._switch_to_new_db(file_path)

    def _switch_to_new_db(self, file_path):
        """Helper for D&D and Load menu actions."""
        
        # Centralized check for bad files before loading
        if not is_valid_sqlite_file(file_path):
            QMessageBox.Critical(self, "Load Error", 
                                  f"The file '{os.path.basename(file_path)}' is not a valid SQLite database.")
            return
            
        self.db_file = file_path
        self._initialize_database(file_path) # Uses the new initialization with schema check
        save_last_db_path(self.db_file) 

        # Also create assets folder when loading/switching, just in case it's missing
        db_dir = os.path.dirname(file_path)
        db_name = os.path.basename(file_path)
        assets_folder_name = os.path.splitext(db_name)[0] + "_assets"
        assets_path = os.path.join(db_dir, assets_folder_name)
        os.makedirs(assets_path, exist_ok=True)
        
        self.setWindowTitle(f"SecOps Field Manual - [{os.path.basename(self.db_file)}]")
        self.statusBar().showMessage(f"Database loaded: {os.path.basename(self.db_file)}.", 5000)
        self.search()
        self.clear_entry_view()

    # --- Drag and Drop Overrides ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1:
            file_path = event.mimeData().urls()[0].toLocalFile()
            if file_path.lower().endswith('.db'):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path and file_path != self.db_file:
                if os.path.exists(file_path):
                    self._switch_to_new_db(file_path)
                    event.acceptProposedAction()
                    return

        event.ignore()

    def _setup_menubar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        load_action = QAction("Load Field Notes...", self)
        load_action.triggered.connect(self.load_db)
        file_menu.addAction(load_action)
        
        create_action = QAction("Create New Field Notes...", self)
        create_action.triggered.connect(self.create_new_db)
        file_menu.addAction(create_action)
        
        file_menu.addSeparator()
        import_action = QAction("Import from CSV...", self)
        import_action.triggered.connect(self._open_import_dialog)
        file_menu.addAction(import_action)

        export_action = QAction("Export to CSV...", self)
        export_action.triggered.connect(self._export_to_csv)
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        
        merge_compare_action = QAction("Merge / Compare Field Notes...", self)
        merge_compare_action.triggered.connect(self.compare_db)
        file_menu.addAction(merge_compare_action)
        file_menu.addSeparator()

        summary_action = QAction("Field Notes Summary", self)
        summary_action.triggered.connect(self._open_summary_dialog)
        file_menu.addAction(summary_action)
        file_menu.addSeparator()

        manage_tags_action = QAction("Manage Tags...", self)
        manage_tags_action.triggered.connect(self._open_tag_manager)
        file_menu.addAction(manage_tags_action)

        view_menu = menubar.addMenu("View")
        
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self._zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self._zoom_out)
        view_menu.addAction(zoom_out_action)
        
        reset_zoom_action = QAction("Reset Zoom", self)
        reset_zoom_action.setShortcut("Ctrl+0")
        reset_zoom_action.triggered.connect(self._reset_zoom)
        view_menu.addAction(reset_zoom_action)

        help_menu = menubar.addMenu("Help")
        search_help_action = QAction("Search Syntax Help", self)
        search_help_action.triggered.connect(self._show_search_help)
        help_menu.addAction(search_help_action)

        formatting_help_action = QAction("Formatting Help", self)
        formatting_help_action.triggered.connect(self._show_entry_editor_help)
        help_menu.addAction(formatting_help_action)
        help_menu.addSeparator()

        about_action = QAction("About", self)
        about_action.triggered.connect(self.about_app)
        help_menu.addAction(about_action)

    def _setup_left_panel(self):
        self.left_widget = QWidget()
        left_layout = QVBoxLayout(self.left_widget)
        
        entries_group = QGroupBox("Entries")
        entries_layout = QVBoxLayout()
        self.results_list = QListWidget()
        self.results_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.results_list.currentItemChanged.connect(self.show_entry)
        entries_layout.addWidget(self.results_list)

        button_layout = QGridLayout()
        self.add_button = QPushButton("Add")
        self.edit_button = QPushButton("Edit")
        self.duplicate_entry_button = QPushButton("Duplicate")
        self.delete_button = QPushButton("Delete")
        button_layout.addWidget(self.add_button, 0, 0)
        button_layout.addWidget(self.edit_button, 0, 1)
        button_layout.addWidget(self.duplicate_entry_button, 1, 0)
        button_layout.addWidget(self.delete_button, 1, 1)
        entries_layout.addLayout(button_layout)
        
        entries_group.setLayout(entries_layout)
        left_layout.addWidget(entries_group)
        
        self.add_button.clicked.connect(self.add_entry)
        self.edit_button.clicked.connect(self.edit_entry)
        self.duplicate_entry_button.clicked.connect(self.duplicate_current_entry)
        self.delete_button.clicked.connect(self.delete_selected_entry)

    def _setup_right_panel(self):
        self.right_panel_container = QWidget()
        grid_layout = QGridLayout(self.right_panel_container)

        # --- Create All Widgets First ---
        self.artifact_group = QGroupBox("Artifact")
        artifact_layout = QVBoxLayout()
        self.entry_artifact_area = PlaceholderTextEdit(parent_app=self)
        self.entry_artifact_area.setMaximumHeight(40)
        artifact_layout.addWidget(self.entry_artifact_area)
        self.artifact_group.setLayout(artifact_layout)

        desc_group = QGroupBox("Description")
        desc_layout = QVBoxLayout()
        self.desc_area = QLabel()
        self.desc_area.setWordWrap(True)
        self.desc_area.setAlignment(Qt.AlignTop)
        self.desc_area.setTextInteractionFlags(Qt.TextBrowserInteraction | Qt.TextSelectableByMouse)
        self.desc_area.linkActivated.connect(self._handle_internal_link)
        desc_scroll_area = QScrollArea()
        desc_scroll_area.setWidget(self.desc_area)
        desc_scroll_area.setWidgetResizable(True)
        desc_layout.addWidget(desc_scroll_area)
        desc_group.setLayout(desc_layout)
        
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout()
        self.notes_area = QLabel()
        self.notes_area.setWordWrap(True)
        self.notes_area.setAlignment(Qt.AlignTop)
        self.notes_area.setTextInteractionFlags(Qt.TextBrowserInteraction | Qt.TextSelectableByMouse)
        self.notes_area.linkActivated.connect(self._handle_internal_link)
        notes_scroll_area = QScrollArea()
        notes_scroll_area.setWidget(self.notes_area)
        notes_scroll_area.setWidgetResizable(True)
        notes_layout.addWidget(notes_scroll_area)
        notes_group.setLayout(notes_layout)

        resources_group = QGroupBox("Resources")
        resources_layout = QVBoxLayout()
        self.resources_area = QLabel()
        self.resources_area.setWordWrap(True)
        self.resources_area.setOpenExternalLinks(True)
        self.resources_area.setAlignment(Qt.AlignTop)
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.resources_area)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(120)
        resources_layout.addWidget(scroll_area)
        resources_group.setLayout(resources_layout)

        top_info_group = QGroupBox("Metadata")
        metadata_v_layout = QVBoxLayout()
        top_info_form_layout = QFormLayout()
        top_info_form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        top_info_form_layout.setLabelAlignment(Qt.AlignLeft)
        
        self.title_label = QLabel()
        self.modified_label = QLabel()
        self.os_label = QLabel()
        self.mitre_label = QLabel()
        self.tags_label = QLabel()
        
        for label in [self.title_label, self.modified_label, self.os_label, self.mitre_label, self.tags_label]:
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        top_info_form_layout.addRow("Title:", self.title_label)
        top_info_form_layout.addRow("OS:", self.os_label)
        top_info_form_layout.addRow("MITRE:", self.mitre_label)
        top_info_form_layout.addRow("Tags:", self.tags_label)
        metadata_v_layout.addLayout(top_info_form_layout)

        self.details_container = QWidget()
        details_form_layout = QFormLayout()
        details_form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        details_form_layout.setLabelAlignment(Qt.AlignLeft)
        self.added_label = QLabel()
        self.source_label = QLabel()
        for label in [self.added_label, self.source_label]:
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details_form_layout.addRow("Last Modified:", self.modified_label)
        details_form_layout.addRow("Added On:", self.added_label)
        details_form_layout.addRow("Source:", self.source_label)
        self.details_container.setLayout(details_form_layout)
        self.details_container.setVisible(False)
        metadata_v_layout.addWidget(self.details_container)
        
        self.details_button = QPushButton("Show Details...")
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._toggle_details)
        metadata_v_layout.addWidget(self.details_button)
        top_info_group.setLayout(metadata_v_layout)

        image_group = QGroupBox("Image")
        image_layout = QVBoxLayout()
        self.image_display = ClickableImage()
        self.image_display.setAlignment(Qt.AlignCenter)
        self.image_display.clicked.connect(self.open_image)
        image_layout.addWidget(self.image_display)
        image_group.setLayout(image_layout)
        
        # --- Add Widgets to the Grid ---
        # Row 0: Metadata and Image
        grid_layout.addWidget(top_info_group, 0, 0, 1, 3)
        grid_layout.addWidget(image_group, 0, 3, 1, 1)

        # Row 1: Artifact
        grid_layout.addWidget(self.artifact_group, 1, 0, 1, 4)

        # Row 2: Description and Notes in a splitter
        desc_notes_splitter = QSplitter(Qt.Horizontal)
        desc_notes_splitter.addWidget(desc_group)
        desc_notes_splitter.addWidget(notes_group)
        desc_notes_splitter.setSizes([self.width() * 0.5, self.width() * 0.5])
        grid_layout.addWidget(desc_notes_splitter, 2, 0, 1, 4)

        # Row 3: Resources
        grid_layout.addWidget(resources_group, 3, 0, 1, 4)

        # --- Configure Grid Stretching ---
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        grid_layout.setColumnStretch(2, 1)
        grid_layout.setColumnStretch(3, 1)
        
        grid_layout.setRowStretch(2, 2) # Allow the splitter row to take up the most vertical space
        grid_layout.setRowStretch(3, 1)


    def _create_text_group(self, title, copy_func):
        """Helper to create Path and Notes header/body structure."""
        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(0) 

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0) 
        header.setSpacing(5) 

        label = QLabel(title)
        label.setStyleSheet("padding-top: 0px; padding-bottom: 0px; margin-top: 0px; margin-bottom: 0px;")

        header.addWidget(label)
        header.addStretch() 
        
        if copy_func:
            self.copy_button = QPushButton("Copy")
            self.copy_button.setFixedSize(60, 32) 
            self.copy_button.clicked.connect(copy_func)
            header.addWidget(self.copy_button)
        
        group_layout.addLayout(header)
        return group_layout
        

    def about_app(self):
        """Displays the About dialog with app info."""
        dialog = AboutDialog(
            APP_AUTHOR, 
            APP_VERSION, 
            APP_RELEASE_DATE, 
            APP_THANKS, 
            self
        )
        dialog.exec()


    def compare_db(self):
        default_dir = os.path.join(os.path.expanduser("~"), 'Documents', DEFAULT_FOLDER_NAME)
        external_db_path, _ = QFileDialog.getOpenFileName(self, "Select Database to Compare", default_dir, "SQLite DB (*.db)")
        if not external_db_path or external_db_path == self.db_file:
            return
        dialog = CompareDBDialog(self.db_file, external_db_path, self)
        if dialog.exec():
            self.search()


    def search(self):
        """Performs a search based on the content of the search bar."""
        query_text = self.search_input.text().strip()
        parsed_query = parse_search_query(query_text)
        
        results = search_entries(self.db_file, parsed_query)
        
        self.results_list.clear()
        if results:
            for r in results:
                self.results_list.addItem(f"{r[0]}: {r[1]}")

    def _toggle_details(self, checked):
        """Shows or hides the detailed metadata fields."""
        self.details_container.setVisible(checked)
        self.details_button.setText("Hide Details" if checked else "Show Details...")

    def show_entry(self, item):
        if not item:
            self.clear_entry_view()
            return

        entry_id = int(item.text().split(":")[0])
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM entries WHERE id=?", (entry_id,))
        entry = cur.fetchone()
        conn.close()

        if entry:
            self.current_entry_id = entry['id']
            # Use dictionary-style access with a fallback
            self.current_text = entry['artifact_value'] if 'artifact_value' in entry.keys() else ""

            tags_list = get_tags_for_entry(self.db_file, self.current_entry_id)
            full_tags_str = ", ".join(tags_list)

            self.artifact_group.setTitle(entry['artifact_type'] if 'artifact_type' in entry.keys() else "Artifact")

            metrics = QFontMetrics(self.title_label.font())

            # Use dictionary-style access for all fields
            title_text = entry['title']
            modified_text = entry['content_modified_at'] if 'content_modified_at' in entry.keys() else ""
            os_text = entry['os'] if 'os' in entry.keys() else "N/A"
            mitre_text = entry['mitre'] if 'mitre' in entry.keys() else "N/A"
            added_text = entry['added_at'] if 'added_at' in entry.keys() else ""
            source_text = entry['source'] if 'source' in entry.keys() else ""
            description_text = entry['description'] if 'description' in entry.keys() else ""
            notes_text = entry['notes'] if 'notes' in entry.keys() else ""
            resources_text = entry['resources'] if 'resources' in entry.keys() else ""
            image_path_text = entry['image_path'] if 'image_path' in entry.keys() else ""

            self.title_label.setToolTip(title_text)
            self.modified_label.setToolTip(modified_text)
            self.os_label.setToolTip(os_text)
            self.mitre_label.setToolTip(mitre_text)
            self.tags_label.setToolTip(full_tags_str)

            if self.title_label.width() > 10:
                self.title_label.setText(metrics.elidedText(title_text, Qt.ElideRight, self.title_label.width()))
                self.modified_label.setText(metrics.elidedText(modified_text, Qt.ElideRight, self.modified_label.width()))
                self.os_label.setText(metrics.elidedText(os_text, Qt.ElideRight, self.os_label.width()))
                self.mitre_label.setText(metrics.elidedText(mitre_text, Qt.ElideRight, self.mitre_label.width()))
                self.tags_label.setText(metrics.elidedText(full_tags_str, Qt.ElideRight, self.tags_label.width()))
            else:
                self.title_label.setText(title_text)
                self.modified_label.setText(modified_text)
                self.os_label.setText(os_text)
                self.mitre_label.setText(mitre_text)
                self.tags_label.setText(full_tags_str)

            self.added_label.setText(added_text)
            self.source_label.setText(source_text)
            
            self.display_placeholders(self.current_text)
            # 1. First, process for internal links on the raw text
            # self.desc_area.setText(self._format_internal_links(description_text))
            # self.notes_area.setText(self._format_internal_links(notes_text))
            desc_with_internal_links = self._format_internal_links(description_text)
            notes_with_internal_links = self._format_internal_links(notes_text)

            # 2. Then, convert the resulting Markdown/HTML mix to full HTML
            description_html = self._format_markdown_to_html(desc_with_internal_links)
            notes_html = self._format_markdown_to_html(notes_with_internal_links)

            # 3. Set the final HTML on the display widgets
            self.desc_area.setText(description_html)
            self.notes_area.setText(notes_html)


            self.resources_area.setText(self._format_links_to_html(resources_text))
            
            stored_image_path = entry['image_path']

            final_image_path = self._get_full_image_path(stored_image_path)
            
            if final_image_path:
                pixmap = QPixmap(final_image_path)
                scaled_pixmap = pixmap.scaled(self.image_display.height(), 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_display.setPixmap(scaled_pixmap)
            else:
                self.image_display.setText("No Image" if not stored_image_path else "Image Not Found")
                self.image_display.setPixmap(QPixmap()) # Important: Clear the old pixmap

            self.duplicate_entry_button.setEnabled(True)


    def display_placeholders(self, text):
        # self.entry_artifact_area.setPlainText(text)
        self.entry_artifact_area.highlight_placeholders(text)

    def add_entry(self):
        dialog = EntryEditor(self.db_file, self)
        if dialog.exec():
            title, desc, artifact_type, artifact_value, img_path, os_val, mitre_val, notes, resources, tag_list = dialog.get_data()
            success, new_id = insert_entry(
                self.db_file, title, desc, artifact_type, artifact_value, img_path, os_val, mitre_val, 
                notes, resources, tag_list, "Manual Entry"
            )
            if success:
                self.search()
                for i in range(self.results_list.count()):
                    item = self.results_list.item(i)
                    if item.text().startswith(f"{new_id}:"):
                        self.results_list.setCurrentItem(item)
                        self.show_entry(item)
                        break
            else:
                # Handle duplicate title error
                QMessageBox.warning(self, "Entry Already Exists", f"An entry with the title '{title}' already exists.")
                for i in range(self.results_list.count()):
                    item = self.results_list.item(i)
                    if item.text().startswith(f"{existing_id}:"):
                        self.results_list.setCurrentItem(item)
                        self.show_entry(item)
                        break

    def edit_entry(self):
        if not self.results_list.currentItem(): return
        
        entry_id = int(self.results_list.currentItem().text().split(":")[0])
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM entries WHERE id=?", (entry_id,))
        entry = cur.fetchone()
        conn.close()
        
        if entry:
            dialog = EntryEditor(self.db_file, self, existing_entry=entry)
            if dialog.exec():
                title, desc, artifact_type, artifact_value, img_path, os_val, mitre_val, notes, resources, tag_list = dialog.get_data()
                update_entry(
                    self.db_file, entry_id, title, desc, artifact_type, artifact_value, img_path, os_val, 
                    mitre_val, notes, resources, tag_list
                )
                self.search()

                for i in range(self.results_list.count()):
                    item = self.results_list.item(i)
                    if item.text().startswith(f"{entry_id}:"):
                        self.results_list.setCurrentItem(item)
                        self.show_entry(item)
                        break


    def duplicate_current_entry(self):
        if self.current_entry_id is None: return

        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()
        cur.execute("SELECT * FROM entries WHERE id=?", (self.current_entry_id,))
        original_entry = dict(zip([d[0] for d in cur.description], cur.fetchone()))
        tags_list = get_tags_for_entry(self.db_file, self.current_entry_id)
        if not original_entry:
            conn.close()
            return
        
        base_title = re.sub(r'_Copy_\d+$', '', original_entry['title'])
        copy_num = 1
        while True:
            new_title = f"{base_title}_Copy_{copy_num}"
            cur.execute("SELECT id FROM entries WHERE title = ?", (new_title,))
            if cur.fetchone() is None: break
            copy_num += 1
        conn.close() 

        success, new_id = insert_entry(
            self.db_file, new_title, original_entry['description'], original_entry['artifact_type'],
            original_entry['artifact_value'], original_entry['image_path'], original_entry['os'], 
            original_entry['mitre'], original_entry['notes'], original_entry['resources'], 
            tags_list, "Manual Duplicate"
        )
        if success:
            self.statusBar().showMessage(f"Entry duplicated as '{new_title}'.", 3000)
            self.search()
            for i in range(self.results_list.count()):
                item = self.results_list.item(i)
                if item.text().startswith(f"{new_id}:"):
                    self.results_list.setCurrentItem(item)
                    self.show_entry(item)
                    break
        else:
            QMessageBox.critical(self, "Error", f"Failed to create duplicate entry.")

    def clear_entry_view(self):
        """Clears all fields in the right-hand panel."""
        self.current_entry_id = None
        self.current_text = ""
        
        # Clear Metadata
        self.title_label.setText("")
        self.modified_label.setText("")
        self.os_label.setText("")
        self.mitre_label.setText("")
        self.tags_label.setText("")
        self.added_label.setText("")
        self.source_label.setText("")
        self.details_container.setVisible(False)
        self.details_button.setChecked(False)
        self.details_button.setText("Show Details...")
        
        # Clear Content
        self.artifact_group.setTitle("Artifact")
        self.entry_artifact_area.clear()
        self.notes_area.clear()
        self.desc_area.clear()
        self.resources_area.clear()
        self.image_display.setText("No Image")
        self.image_display.setPixmap(QPixmap())
        
        self.duplicate_entry_button.setEnabled(False)

    def delete_selected_entry(self):
        selected_items = self.results_list.selectedItems()
        if not selected_items: return
        
        count = len(selected_items)
        prompt = f"Are you sure you want to delete {count} entr{'y' if count == 1 else 'ies'}?"
        if QMessageBox.question(self, "Confirm Delete", prompt) == QMessageBox.Yes:
            for item in selected_items:
                delete_entry(self.db_file, int(item.text().split(":")[0]))
            self.statusBar().showMessage(f"Successfully deleted {count} entr{'y' if count == 1 else 'ies'}.", 3000)
            self.search()
            self.clear_entry_view()

    def copy_text(self):
        text = self.entry_artifact_area.toPlainText()
        
        # Ensure the main application pointer is available for the status bar
        app = self.parent() or self
        
        if text.strip():
            QApplication.clipboard().setText(text)
            
            # --- TEMPORARY MESSAGE (Status Bar) ---
            if app.statusBar():
                app.statusBar().showMessage(
                    "Artifact text copied to clipboard. (3s)",
                    3000  # Message disappears after 3 seconds
                )
            
        else:
            # For warnings, a non-blocking message is still less disruptive than a blocking QMessageBox
            if app.statusBar():
                app.statusBar().showMessage("Warning: This entry has no artifact text to copy.", 5000) # Show warning for 5 seconds
            else:
                # Fallback in case status bar isn't available (though it should be)
                QMessageBox.warning(self, "Empty", "This entry has no artifact text to copy.")

    def open_image(self):
        if self.current_entry_id is not None:
            conn = sqlite3.connect(self.db_file)
            cur = conn.cursor()
            cur.execute("SELECT image_path FROM entries WHERE id=?", (self.current_entry_id,))
            stored_path = cur.fetchone()[0]
            conn.close()

            # Use the helper to find the full path
            full_path = self._get_full_image_path(stored_path)

            if full_path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(full_path))

    def resizeEvent(self, event):
        """Overrides the resize event to trigger a delayed update."""
        super().resizeEvent(event)
        # Wait 50ms for the layout to settle before recalculating.
        self.resize_timer.start(50)

    def about_app(self):
        """Displays the About dialog with app info."""
        dialog = AboutDialog(
            APP_AUTHOR, 
            APP_VERSION, 
            APP_RELEASE_DATE, 
            APP_THANKS, 
            self
        )
        dialog.exec()

    def _handle_resize_finished(self):
        """Called after the resize has finished to re-truncate text."""
        if self.results_list.currentItem():
            self.show_entry(self.results_list.currentItem())

    def _get_full_image_path(self, stored_image_path):
        """Resolves a stored image path (either new relative or old absolute) into a full, usable path."""
        if not stored_image_path:
            return None

        # This is the logic we will now reuse
        db_dir = os.path.dirname(self.db_file)
        db_name = os.path.basename(self.db_file)
        assets_folder_name = os.path.splitext(db_name)[0] + "_assets"
        
        potential_path = os.path.join(db_dir, assets_folder_name, stored_image_path)
        if os.path.exists(potential_path):
            return potential_path
        
        return None # Return None if no valid path is found

    def _open_tag_manager(self):
        """Opens the tag management dialog."""
        dialog = TagManagementDialog(self.db_file, self)
        dialog.exec()

    def _format_links_to_html(self, text):
        """
        Converts text into clickable links, validating URLs within Markdown syntax.
        """
        if not text:
            return ""
        
        output_lines = []
        markdown_pattern = re.compile(r'\[(.*?)\]\((.*?)\)')
        plain_url_pattern = re.compile(r'^(https?://)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

        for line in text.strip().split('\n'):
            clean_line = line.strip()
            if not clean_line:
                continue
            
            match = markdown_pattern.match(clean_line)
            if match:
                display_text = match.group(1)
                url_part = match.group(2)
                
                # --- VALIDATION ---
                # Now, validate the URL part from the Markdown
                if plain_url_pattern.match(url_part):
                    # If it's a valid-looking URL, create the link
                    url = f"https://{url_part}" if not url_part.startswith(('http://', 'https://')) else url_part
                    output_lines.append(f'<a href="{url}">{display_text}</a>')
                else:
                    # If the URL part is invalid, treat the whole line as plain text
                    output_lines.append(clean_line)

            elif plain_url_pattern.match(clean_line):
                # Fallback for plain URLs remains the same
                url = f"https://{clean_line}" if not clean_line.startswith(('http://', 'https://')) else clean_line
                output_lines.append(f'<a href="{url}">{clean_line}</a>')
            else:
                output_lines.append(clean_line)
                
        return "<br>".join(output_lines)

    def _format_internal_links(self, text):
        """Finds [[Entry Title]] and converts it to a URL-encoded HTML link."""
        if not text:
            return ""

        # This function will be called for each match
        def create_link(match):
            title = match.group(1)
            # URL-encode the title to handle spaces and special characters
            encoded_title = urllib.parse.quote(title)
            return f'<a href="entry://{encoded_title}">{title}</a>'

        # Use a function with re.sub for safer replacement
        formatted_text = re.sub(r'\[\[(.*?)\]\]', create_link, text)
        return formatted_text

    def _handle_internal_link(self, link_str):
        """Handles clicks on internal entry:// links by manually parsing the string."""
        if link_str.startswith("entry://"):
            encoded_title = link_str[len("entry://"):]
            entry_title = urllib.parse.unquote(encoded_title)
            if not entry_title: return

            search_query_text = f'title:"{entry_title}"'
            
            # Set the search bar text and directly call the search function
            self.search_input.setText(search_query_text)
            self.search()
            
            # After the search, check if any results were found
            if self.results_list.count() == 0:
                QMessageBox.warning(self, "Not Found", f"The entry named '{entry_title}' could not be found.")
            else:
                # Auto-select the first result
                item = self.results_list.item(0)
                self.results_list.setCurrentItem(item)
                self.show_entry(item)

    def _on_search_text_changed(self, text):
        """
        This method is called whenever the search bar text changes.
        If the text is cleared, it automatically refreshes the search.
        """
        if not text:
            self.search()

    def _open_summary_dialog(self):
        """Gathers database stats and displays them in a dialog."""
        summary_data = get_database_summary(self.db_file)

        if summary_data.get('total_entries', 0) == 0:
            QMessageBox.information(self, "Database Empty", "There are no entries in the current database to summarize.")
            return

        dialog = SummaryDialog(summary_data, self)
        dialog.exec()

    def _show_search_help(self):
        """Displays a dialog with search syntax help."""
        help_title = "Advanced Search Syntax"
        help_text = """
        <p>Combine keywords and filters to create powerful queries.</p>
        
        <h3>Basic Keywords (AND):</h3>
        <p>Simply type words to find entries containing all of them.<br>
        <i>Example:</i> <code>windows persistence</code></p>
        
        <h3>Exclusion (NOT):</h3>
        <p>Use a minus sign (-) to exclude entries containing a word.<br>
        Can be prepended to Field-Specific Filters.<br>
        <i>Example:</i> <code>registry -autoruns</code></p>
        
        <h3>Exact Phrase:</h3>
        <p>Wrap words in double quotes to search for the exact phrase.<br>
        <i>Example:</i> <code>"initial access"</code></p>
        
        <h3>Field-Specific Filters:</h3>
        <p>Use <code>field:value</code>. Available fields: <code>title</code>, 
        <code>os</code>, <code>mitre</code>, <code>tags</code>, <code>artifact_type</code>, <code>artifact_value</code>, <code>description</code>, <code>notes</code>, <code>resources</code>, <code>source</code>.<br>
        <i>Example:</i> <code>os:windows tags:network,malware -tags:server</code><br>
        <i>Example (exact title):</i> <code>title:"My Entry"</code></p>

        <h3>Date Filters:</h3>
        <p>Use YYYY-MM-DD format.<br>
        <code>added_after:2025-10-01</code><br>
        <code>modified_before:2025-09-30</code></p>

        <h3>Empty Field Search:</h3>
        <p>Find entries where a field is empty.<br>
        <i>Example:</i> <code>artifact_value:blank</code></p>
        """
        QMessageBox.information(self, help_title, help_text)

    def _show_entry_editor_help(self):
        """Displays the HTML formatting help dialog."""
        # This is the same logic that was in the EntryEditor dialog
        title = "Formatting Help"
        text = """
        <p>The <b>Notes, Description,</b> and <b>Resources</b> fields support basic HTML and Mardown formating and special syntax.</p>
        <hr>
        <b>Bold:</b> <code>**your text**</code><br>
        <b>Italic:</b> <code>*your text*</code><br>
        <b>List:</b> <code>* Item 1</code><br>
        <b>Internal Link:</b> <code>[[Entry Title]]</code><br>
        <b>External Link:</b> <code>[Display Text](url.com)</code>
        """
        QMessageBox.information(self, title, text)

    def _open_import_dialog(self):
        """Opens the CSV import wizard dialog."""
        dialog = ImportDialog(self, self)
        dialog.exec()
        self.search() # Refresh the main view after the dialog closes

    def _export_to_csv(self):
        """Exports all entries in the current database to a CSV file."""
        if self.results_list.count() == 0:
            QMessageBox.information(self, "Database Empty", "There are no entries to export.")
            return

        default_dir = os.path.join(os.path.expanduser("~"), 'Documents', DEFAULT_FOLDER_NAME)
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV", default_dir, "CSV Files (*.csv)"
        )

        if not file_path:
            return # User cancelled

        try:
            all_entries = get_all_entries_for_export(self.db_file)
            
            if not all_entries:
                QMessageBox.information(self, "No Data", "No data found to export.")
                return

            # Define the headers, including the new timestamp, in the desired order
            headers = ["Title", "Description", "Artifact Type", "Artifact Value", "OS", "MITRE", "Tags", "Notes", "Resources", "Content Modified At"]
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(all_entries)
            
            self.statusBar().showMessage(f"Successfully exported {len(all_entries)} entries to {os.path.basename(file_path)}.", 5000)

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n\n{e}")


    def _load_favorites_menu(self):
        """Builds the hybrid favorites menu with recent items and a 'Manage' option."""
        self.favorites_menu.clear()
        
        all_searches = load_saved_searches()
        recent_searches = load_search_history()
        
        if not all_searches:
            self.favorites_menu.addAction("No saved searches").setEnabled(False)
            return

        # Add up to 5 most recent searches for quick access
        added_recent = False
        for i, search_name in enumerate(recent_searches):
            if i >= 5: break
            if search_name in all_searches:
                action = QAction(search_name, self)
                action.triggered.connect(lambda checked=False, name=search_name: self._run_favorite_search(name))
                self.favorites_menu.addAction(action)
                added_recent = True

        if added_recent:
            self.favorites_menu.addSeparator()

        # Add the 'Manage' option
        manage_action = QAction("Manage All Searches...", self)
        manage_action.triggered.connect(self._open_manage_searches_dialog)
        self.favorites_menu.addAction(manage_action)

    def _run_favorite_search(self, search_name):
        """Runs a selected favorite search."""
        all_searches = load_saved_searches()
        query = all_searches.get(search_name)
        if query:
            record_search_in_history(search_name)
            self.search_input.setText(query)
            self.search()
            self._load_favorites_menu() # Refresh menu to show new order

    def _save_new_search(self):
        """Saves the current search query as a new favorite."""
        current_query = self.search_input.text().strip()
        if not current_query:
            return

        name, ok = QInputDialog.getText(self, "Save Search", "Enter a name for this search:")
        if ok and name.strip():
            name = name.strip()
            all_searches = load_saved_searches()
            if name in all_searches:
                QMessageBox.warning(self, "Name Exists", "A search with that name already exists.")
                return
            
            all_searches[name] = current_query
            save_searches(all_searches)
            record_search_in_history(name)
            self._load_favorites_menu()
            self.statusBar().showMessage(f"Search '{name}' saved.", 3000)

    def _open_manage_searches_dialog(self):
        """Opens the dialog to manage searches and handles the result."""
        # 1. Load the current saved searches from the config file
        saved_searches = load_saved_searches()
        
        # 2. Open the dialog, which works on its own copy of the searches
        dialog = ManageSearchesDialog(saved_searches, self)
        
        # 3. The dialog's exec() method returns True only if the user clicks "OK"
        #    or a button that calls self.accept() (like our "Run" button).
        if dialog.exec():
            # 4. If the user accepted, save the potentially modified dictionary back to the config file.
            save_searches(dialog.searches)
            
            # 5. Refresh the "Favorites" dropdown to show any changes (renames/deletions).
            self._load_favorites_menu()
            
            # 6. Check if a search was selected to be run.
            if dialog.query_to_run:
                # If so, call the helper function to run it.
                self._run_favorite_search(dialog.query_to_run)

    def _format_markdown_to_html(self, text):
        """Converts Markdown to HTML with theme-aware styling."""
        if not text:
            return ""
        
        extensions = ['fenced_code', 'tables', 'admonition', 'toc', 'codehilite']
        
        # 1. Convert Markdown to HTML
        html_body = markdown.markdown(text, extensions=extensions)

        # 2. Detect Theme (Light vs Dark)
        # We check the generic Text color. If it's bright, we are in dark mode.
        text_color = self.palette().color(QPalette.Text)
        is_dark_mode = text_color.lightness() > 128

        # 3. Define Colors based on Theme
        if is_dark_mode:
            # Dark Mode Colors
            header_bg = "#2a2a2a"
            header_text = "#ffffff"
            row_bg_alt = "#2c2c2c" # Dark gray for alternating rows
            border_color = "#555"
            body_text = "#e0e0e0" # Explicit text color ensures readability
            pygments_style = 'monokai'
            code_bg = "#2a2a2a" # Background for code blocks
            code_border = "#555"
        else:
            # Light Mode Colors
            header_bg = "#e0e0e0" # Light gray header
            header_text = "#000000"
            row_bg_alt = "#f5f5f5" # Very light gray for alternating rows
            border_color = "#ccc"
            body_text = "#333333" # Explicit dark text for light mode
            pygments_style = 'default' # Use a light-friendly code theme
            code_bg = "#f8f8f8" # Light background for code blocks
            code_border = "#ccc"

        # 4. Generate CSS for Syntax Highlighting (Pygments)
        formatter = HtmlFormatter(style=pygments_style, nobackground=True)
        pygments_css = f"<style>{formatter.get_style_defs('.codehilite')}</style>"

        # 5. Define CSS for Tables using the variables
        # Note: We now explicitly set 'color' for 'th, td' to prevent contrast issues
        table_css = f"""
        <style>
        table {{ border-collapse: collapse; width: 95%; margin: 1em 0; }}
        th, td {{ border: 1px solid {border_color}; padding: 8px; text-align: left; color: {body_text}; }}
        th {{ background-color: {header_bg}; color: {header_text}; }}
        </style>
        """
        
        # 6. Define CSS for Code Blocks
        code_block_css = f"""
        <style>
        .codehilite {{ 
            background-color: {code_bg}; 
            border: 1px solid {code_border}; 
            border-radius: 4px; 
            padding: 10px; 
            overflow: auto;
        }}
        /* Ensure pre tag doesn't add extra margins that break the block look */
        pre {{ margin: 0; }}
        </style>
        """
        
        # 7. Manually add alternating row colors
        # We define the replacement logic here to capture the 'row_bg_alt' variable
        def add_row_styling(match):
            rows = match.group(1)
            styled_rows = []
            for i, row in enumerate(re.findall(r'<tr.*?>.*?</tr>', rows, re.DOTALL)):
                if (i + 1) % 2 == 0:
                    # Inject the theme-specific background color
                    styled_rows.append(row.replace('<tr>', f'<tr style="background-color: {row_bg_alt};">', 1))
                else:
                    styled_rows.append(row)
            return f"<tbody>{''.join(styled_rows)}</tbody>"

        # Apply the row styling regex
        html_with_styled_rows = re.sub(r'<tbody>(.*?)</tbody>', add_row_styling, html_body, flags=re.DOTALL)

        # 8. Combine everything
        return pygments_css + table_css + code_block_css + html_with_styled_rows

    def _apply_zoom(self):
        """Applies the current zoom level to the application's global font."""
        font = QApplication.font()
        # Start from a standard default size and apply the zoom level
        default_size = 13 # You can adjust this if your default font size is different
        new_size = default_size + self.zoom_level
        if new_size < 6: new_size = 6 # Set a minimum font size
        font.setPointSize(new_size)
        QApplication.setFont(font)
        # Refresh the current entry to re-calculate elided text
        if self.results_list.currentItem():
            self.show_entry(self.results_list.currentItem())

    def _zoom_in(self):
        """Increases the zoom level and saves it."""
        self.zoom_level += 1
        self._apply_zoom()
        save_zoom_level(self.zoom_level)

    def _zoom_out(self):
        """Decreases the zoom level and saves it."""
        self.zoom_level -= 1
        self._apply_zoom()
        save_zoom_level(self.zoom_level)

    def _reset_zoom(self):
        """Resets the zoom level to default and saves it."""
        self.zoom_level = 0
        self._apply_zoom()
        save_zoom_level(self.zoom_level)

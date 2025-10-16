from PySide6.QtWidgets import QLabel, QLineEdit, QCompleter
from PySide6.QtCore import Qt, Signal, QRect, QSize

class ClickableImage(QLabel):
    """
    A QLabel that can be clicked, emitting a 'clicked' signal.
    It only registers clicks if they occur within the visible pixmap area.
    """
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        # Proceed only if there is a pixmap to check against
        if self.pixmap() and not self.pixmap().isNull():
            
            # Get the size of the label and the original pixmap
            label_size = self.size()
            pixmap_original_size = self.pixmap().size()
            
            # Calculate the size of the pixmap as it is displayed (scaled)
            # This creates a virtual scaled size without creating a new pixmap object
            scaled_pixmap_size = pixmap_original_size.scaled(label_size, Qt.KeepAspectRatio)

            # Calculate the top-left corner of the centered pixmap
            x = (label_size.width() - scaled_pixmap_size.width()) / 2
            y = (label_size.height() - scaled_pixmap_size.height()) / 2
            
            # Create a rectangle representing the area of the visible pixmap
            pixmap_rect = QRect(x, y, scaled_pixmap_size.width(), scaled_pixmap_size.height())

            # Only emit the signal if the click was inside the pixmap's rectangle
            if pixmap_rect.contains(event.pos()):
                self.clicked.emit()


class FieldCompleter(QCompleter):
    """A custom QCompleter that is context-aware for search fields."""
    def splitPath(self, path):
        # This method controls what part of the text is used for completion
        cursor_pos = self.widget().cursorPosition()
        text_up_to_cursor = path[:cursor_pos]
        
        # Find the start of the current word
        start = text_up_to_cursor.rfind(' ') + 1
        
        # Return only the current word for completion
        return [text_up_to_cursor[start:]]

class SearchLineEdit(QLineEdit):
    """A custom QLineEdit that handles completion for smart autocompletion."""
    def __init__(self, parent=None):
        super().__init__(parent)
        # When a completion is activated (by click or Enter), call our smart replacer
        if self.completer():
            self.completer().activated.connect(self._insert_completion)

    def setCompleter(self, completer):
        """Override setCompleter to connect our custom signal handler."""
        super().setCompleter(completer)
        if self.completer():
            self.completer().activated.connect(self._insert_completion)

    def _insert_completion(self, completion):
        """Replaces only the current word with the selected completion."""
        full_text = self.text()
        cursor_pos = self.cursorPosition()
        
        # Find the start of the word being completed
        start = full_text.rfind(' ', 0, cursor_pos) + 1
        
        # --- Remove the extra space at the end ---
        # Build the new text string by replacing only the current part
        new_text = full_text[:start] + completion
        
        self.setText(new_text)
        self.setCursorPosition(len(new_text)) # Move cursor to the end

    def keyPressEvent(self, event):
        """Overrides key press events to handle Right Arrow key completion."""
        completer = self.completer()
        # Check if the completer popup is visible and the key is the Right Arrow key
        if completer and completer.popup().isVisible() and event.key() == Qt.Key_Right:
            # Manually call the insertion logic
            self._insert_completion(completer.currentCompletion())
            # Hide the popup
            completer.popup().hide()
            # Use return to definitively stop event propagation
            return
        
        # For all other keys, use the default behavior
        super().keyPressEvent(event)
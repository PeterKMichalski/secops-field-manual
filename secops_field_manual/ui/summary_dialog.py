from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QDialogButtonBox, QGroupBox
)
from PySide6.QtCore import Qt
from .constants import OPERATING_SYSTEMS, MITRE_ATTACK_TACTICS

class SummaryDialog(QDialog):
    def __init__(self, summary_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Summary")
        self.setMinimumWidth(400)

        main_layout = QVBoxLayout(self)

        # --- General Stats Group ---
        general_group = QGroupBox("General")
        form_layout_1 = QFormLayout()
        form_layout_1.addRow("Total Entries:", QLabel(str(summary_data.get('total_entries', 0))))
        form_layout_1.addRow("Last Modified:", QLabel(str(summary_data.get('last_update', 'N/A'))))
        form_layout_1.addRow("Entries with Images:", QLabel(str(summary_data.get('entries_with_images', 0))))
        general_group.setLayout(form_layout_1)
        main_layout.addWidget(general_group)

        # --- Data Quality Group ---
        quality_group = QGroupBox("Data Quality")
        form_layout_2 = QFormLayout()
        form_layout_2.addRow("Entries with Empty Artifact Value:", QLabel(str(summary_data.get('empty_artifact_values', 0))))
        form_layout_2.addRow("Entries with Empty Description:", QLabel(str(summary_data.get('empty_descriptions', 0))))
        quality_group.setLayout(form_layout_2)
        main_layout.addWidget(quality_group)

        # --- OS Counts Group ---
        os_counts = summary_data.get('os_counts', {})
        if os_counts:
            os_order = {os: i for i, os in enumerate(OPERATING_SYSTEMS)}
            os_group = QGroupBox("Entries by OS")
            form_layout_3 = QFormLayout()
            for os, count in sorted(os_counts.items(), key=lambda x: os_order.get(x[0], 999)):
                form_layout_3.addRow(f"{os or 'Unspecified'}:", QLabel(str(count)))
            os_group.setLayout(form_layout_3)
            main_layout.addWidget(os_group)

        # --- MITRE Counts Group ---
        mitre_counts = summary_data.get('mitre_counts', {})
        if mitre_counts:
            mitre_order = {tactic: i for i, tactic in enumerate(MITRE_ATTACK_TACTICS)}
            mitre_group = QGroupBox("Entries by MITRE Tactic")
            form_layout_4 = QFormLayout()
            for tactic, count in sorted(mitre_counts.items(), key=lambda x: mitre_order.get(x[0], 999)):
                form_layout_4.addRow(f"{tactic}:", QLabel(str(count)))
            mitre_group.setLayout(form_layout_4)
            main_layout.addWidget(mitre_group)
        
        # --- Top Tags Group ---
        top_tags = summary_data.get('top_tags', [])
        if top_tags:
            tags_group = QGroupBox("Top 5 Tags")
            form_layout_5 = QFormLayout()
            for tag, count in top_tags:
                form_layout_5.addRow(f"{tag}:", QLabel(str(count)))
            tags_group.setLayout(form_layout_5)
            main_layout.addWidget(tags_group)

        main_layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        main_layout.addWidget(buttons)

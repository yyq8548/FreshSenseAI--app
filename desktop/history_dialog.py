"""Qt dialog for viewing, exporting, and clearing local scan history."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.history import HistoryStorageError, ScanHistoryRecord, ScanHistoryStore


class HistoryDialog(QDialog):
    def __init__(self, store: ScanHistoryStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("FreshSense scan history")
        self.resize(860, 480)
        self.setMinimumSize(680, 360)

        layout = QVBoxLayout(self)
        heading = QLabel("Recent scans")
        heading.setStyleSheet("font-size: 22px; font-weight: 700; color: #183F29;")
        layout.addWidget(heading)

        privacy = QLabel(
            "Stored only on this computer. FreshSense saves result metadata and the file name; "
            "it does not copy or retain the photo."
        )
        privacy.setWordWrap(True)
        privacy.setStyleSheet("color: #587062;")
        layout.addWidget(privacy)

        self.empty_label = QLabel("No scans have been saved yet.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #587062; padding: 24px;")
        layout.addWidget(self.empty_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Photo", "Result", "Confidence", "Risk"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        button_row = QHBoxLayout()
        self.export_button = QPushButton("Export CSV")
        self.export_button.clicked.connect(self._export)
        self.clear_button = QPushButton("Clear history")
        self.clear_button.clicked.connect(self._clear)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(self.export_button)
        button_row.addWidget(self.clear_button)
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self._refresh()

    def _refresh(self) -> None:
        try:
            records = self.store.list_records()
        except HistoryStorageError as exc:
            QMessageBox.warning(self, "History unavailable", str(exc))
            records = []

        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = [
                _display_timestamp(record),
                record.image_name,
                record.result_title,
                "—" if record.confidence is None else f"{record.confidence:.1%}",
                record.risk,
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

        has_records = bool(records)
        self.empty_label.setVisible(not has_records)
        self.table.setVisible(has_records)
        self.export_button.setEnabled(has_records)
        self.clear_button.setEnabled(has_records)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export FreshSense scan history",
            "FreshSense-scan-history.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            count = self.store.export_csv(path)
        except HistoryStorageError as exc:
            QMessageBox.warning(self, "Could not export history", str(exc))
            return
        QMessageBox.information(self, "History exported", f"Exported {count} scan records.")

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear scan history?",
            "This permanently removes all locally stored scan records. Photos are not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.clear()
        except HistoryStorageError as exc:
            QMessageBox.warning(self, "Could not clear history", str(exc))
            return
        self._refresh()


def _display_timestamp(record: ScanHistoryRecord) -> str:
    try:
        value = datetime.fromisoformat(record.created_at.replace("Z", "+00:00"))
        return value.astimezone().strftime("%Y-%m-%d %I:%M %p")
    except ValueError:
        return record.created_at

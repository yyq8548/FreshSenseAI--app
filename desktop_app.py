"""Native Windows entry point for FreshSense AI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from PIL import Image
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from agent.fruit_agent import FruitScannerAgent
from agent.state import AgentState
from desktop.history import HistoryStorageError, ScanHistoryRecord, ScanHistoryStore
from desktop.history_dialog import HistoryDialog
from desktop.presenter import result_summary, supported_scope_text
from utils.config import FRUIT_CATALOG_PATH, KNOWLEDGE_BASE_PATH, MODEL_PATH, SAFETY_NOTICE
from utils.startup import StartupValidationError, validate_startup


IMAGE_FILTER = "Images (*.jpg *.jpeg *.png)"


class DropImageLabel(QLabel):
    image_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__("Drop a fruit photo here\nor choose a file")
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(440, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName("dropZone")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if urls and _is_supported_image(urls[0].toLocalFile()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        path = event.mimeData().urls()[0].toLocalFile()
        self.image_selected.emit(path)
        event.acceptProposedAction()


class ModelLoader(QObject):
    loaded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def run(self) -> None:
        try:
            validate_startup(MODEL_PATH, KNOWLEDGE_BASE_PATH, FRUIT_CATALOG_PATH)
            self.loaded.emit(
                FruitScannerAgent(
                    model_path=MODEL_PATH,
                    catalog_path=FRUIT_CATALOG_PATH,
                    knowledge_base_path=KNOWLEDGE_BASE_PATH,
                )
            )
        except (StartupValidationError, RuntimeError) as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class AnalysisWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, agent: FruitScannerAgent, image: Image.Image) -> None:
        super().__init__()
        self.agent = agent
        self.image = image

    def run(self) -> None:
        try:
            self.completed.emit(self.agent.run(self.image))
        except Exception:
            self.failed.emit(
                "The photo could not be analyzed. Try another image or restart FreshSense."
            )
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self, history_store: ScanHistoryStore | None = None) -> None:
        super().__init__()
        self.history_store = history_store or ScanHistoryStore()
        self.agent: FruitScannerAgent | None = None
        self.current_image: Image.Image | None = None
        self.current_path: str | None = None
        self._model_thread: QThread | None = None
        self._model_worker: ModelLoader | None = None
        self._analysis_thread: QThread | None = None
        self._analysis_worker: AnalysisWorker | None = None
        self._build_ui()
        self._load_model()

    def _build_ui(self) -> None:
        self.setWindowTitle("FreshSense AI")
        self.resize(1120, 760)
        self.setMinimumSize(920, 640)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(34, 26, 34, 26)
        root_layout.setSpacing(18)

        title = QLabel("FreshSense AI")
        title.setObjectName("title")
        subtitle = QLabel("Private, on-device fruit freshness guidance")
        subtitle.setObjectName("subtitle")
        scope = QLabel(supported_scope_text())
        scope.setObjectName("scope")
        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)
        root_layout.addWidget(scope)

        notice = QLabel(SAFETY_NOTICE)
        notice.setWordWrap(True)
        notice.setObjectName("safetyNotice")
        root_layout.addWidget(notice)

        content = QHBoxLayout()
        content.setSpacing(22)
        root_layout.addLayout(content, 1)

        left_card = QFrame()
        left_card.setObjectName("card")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(12)
        self.preview = DropImageLabel()
        self.preview.image_selected.connect(self.select_image)
        left_layout.addWidget(self.preview, 1)

        choose_button = QPushButton("Choose photo")
        choose_button.clicked.connect(self.choose_image)
        left_layout.addWidget(choose_button)

        history_button = QPushButton("View scan history")
        history_button.clicked.connect(self.show_history)
        left_layout.addWidget(history_button)

        self.analyze_button = QPushButton("Analyze freshness")
        self.analyze_button.setObjectName("primaryButton")
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self.analyze)
        left_layout.addWidget(self.analyze_button)
        content.addWidget(left_card, 5)

        right_card = QFrame()
        right_card.setObjectName("card")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(24, 22, 24, 22)
        right_layout.setSpacing(12)

        self.status = QLabel("Loading freshness model…")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        right_layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        right_layout.addWidget(self.progress)

        self.result_title = QLabel("Select a clear fruit photo to begin")
        self.result_title.setObjectName("resultTitle")
        self.result_title.setWordWrap(True)
        right_layout.addWidget(self.result_title)

        self.confidence = QLabel("")
        self.confidence.setObjectName("confidence")
        right_layout.addWidget(self.confidence)

        self.recommendation = QLabel("")
        self.recommendation.setWordWrap(True)
        self.recommendation.setObjectName("recommendation")
        right_layout.addWidget(self.recommendation)

        self.details = QLabel("")
        self.details.setWordWrap(True)
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.details)
        right_layout.addWidget(scroll, 1)
        content.addWidget(right_card, 4)

        self.setCentralWidget(root)
        self.setStyleSheet(_stylesheet())

    def _load_model(self) -> None:
        thread = QThread(self)
        worker = ModelLoader()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.loaded.connect(self._model_ready)
        worker.failed.connect(self._model_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._model_thread = thread
        self._model_worker = worker
        thread.start()

    def _model_ready(self, agent: FruitScannerAgent) -> None:
        self.agent = agent
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress.hide()
        self.status.setText("Model ready · Analysis stays on this computer")
        self._update_analyze_state()

    def _model_failed(self, message: str) -> None:
        self.progress.hide()
        self.status.setText("FreshSense cannot start")
        QMessageBox.critical(
            self,
            "FreshSense model unavailable",
            f"{message}\n\nReinstall FreshSense or contact the application provider.",
        )

    def choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a fruit photo", "", IMAGE_FILTER)
        if path:
            self.select_image(path)

    def select_image(self, path: str) -> None:
        if not _is_supported_image(path):
            QMessageBox.warning(self, "Unsupported image", "Choose a JPG, JPEG, or PNG image.")
            return
        try:
            image = Image.open(path)
            image.verify()
            self.current_image = Image.open(path).convert("RGB")
        except (OSError, ValueError):
            QMessageBox.warning(self, "Invalid image", "FreshSense could not read this image.")
            return

        self.current_path = path
        pixmap = QPixmap(path)
        self.preview.setPixmap(
            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.status.setText(f"Ready to analyze · {Path(path).name}")
        self.result_title.setText("Photo selected")
        self.confidence.clear()
        self.recommendation.clear()
        self.details.clear()
        self._update_analyze_state()

    def analyze(self) -> None:
        if self.agent is None or self.current_image is None:
            return
        self.analyze_button.setEnabled(False)
        self.progress.show()
        self.progress.setRange(0, 0)
        self.status.setText("Analyzing image quality and freshness…")

        thread = QThread(self)
        worker = AnalysisWorker(self.agent, self.current_image.copy())
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._show_result)
        worker.failed.connect(self._analysis_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._analysis_finished)
        self._analysis_thread = thread
        self._analysis_worker = worker
        thread.start()

    def _show_result(self, state: AgentState) -> None:
        summary = result_summary(
            state,
            catalog=self.agent.catalog if self.agent else None,
        )
        self.result_title.setText(summary["title"])
        self.confidence.setText(
            f"{summary['confidence']}  ·  Risk guidance: {summary['risk']}"
        )
        self.recommendation.setText(summary["recommendation"])
        self.details.setText(summary["details"])
        history_saved = self._record_history(state, summary)
        self.status.setText(
            "Analysis complete"
            if history_saved
            else "Analysis complete · History was not saved"
        )

    def _record_history(self, state: AgentState, summary: dict[str, str]) -> bool:
        if self.current_path is None:
            return True
        confidence = (
            state.prediction.confidence
            if state.decision == "accept_prediction" and state.prediction is not None
            else None
        )
        try:
            record = ScanHistoryRecord.create(
                image_name=Path(self.current_path).name,
                result_title=summary["title"],
                confidence=confidence,
                risk=summary["risk"],
                decision=state.decision,
                status=state.status,
            )
            self.history_store.add(record)
        except HistoryStorageError:
            state.add_trace("Desktop history could not be saved.")
            return False
        state.add_trace("Desktop history saved result metadata without the photo.")
        return True

    def show_history(self) -> None:
        HistoryDialog(self.history_store, self).exec()

    def _analysis_failed(self, message: str) -> None:
        self.status.setText("Analysis failed")
        QMessageBox.warning(self, "Could not analyze photo", message)

    def _analysis_finished(self) -> None:
        self.progress.hide()
        self._update_analyze_state()

    def _update_analyze_state(self) -> None:
        self.analyze_button.setEnabled(self.agent is not None and self.current_image is not None)


def _is_supported_image(path: str) -> bool:
    return Path(path).suffix.lower() in {".jpg", ".jpeg", ".png"}


def _stylesheet() -> str:
    return """
        QWidget { background: #F4F7F3; color: #17251C; font-family: "Segoe UI"; font-size: 14px; }
        QLabel#title { font-size: 30px; font-weight: 700; color: #163F27; }
        QLabel#subtitle { color: #587062; font-size: 15px; }
        QLabel#scope { color: #315B40; font-size: 14px; font-weight: 600; }
        QLabel#safetyNotice { background: #FFF4D8; border: 1px solid #E7C66D; border-radius: 9px; padding: 11px 14px; color: #604B16; }
        QFrame#card { background: white; border: 1px solid #D8E2DA; border-radius: 14px; }
        QLabel#dropZone { background: #F8FAF8; border: 2px dashed #8EB79A; border-radius: 12px; color: #4B6854; font-size: 17px; }
        QPushButton { min-height: 42px; border: 1px solid #9CB7A3; border-radius: 9px; background: white; font-weight: 600; padding: 0 18px; }
        QPushButton:hover { background: #EEF5F0; }
        QPushButton#primaryButton { background: #237A45; color: white; border-color: #237A45; }
        QPushButton#primaryButton:hover { background: #1A6638; }
        QPushButton:disabled { background: #D9E2DC; color: #829087; border-color: #D9E2DC; }
        QLabel#status { color: #4E6A57; font-weight: 600; }
        QLabel#resultTitle { font-size: 26px; font-weight: 700; color: #183F29; margin-top: 10px; }
        QLabel#confidence { color: #587062; font-weight: 600; }
        QLabel#recommendation { background: #E9F5EC; border-radius: 9px; padding: 14px; font-size: 15px; }
        QScrollArea { background: transparent; }
        QScrollArea > QWidget > QWidget { background: white; }
        QProgressBar { border: none; background: #E5ECE7; border-radius: 4px; min-height: 7px; max-height: 7px; }
        QProgressBar::chunk { background: #36A65D; border-radius: 4px; }
    """


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FreshSense AI")
    app.setOrganizationName("FreshSense")
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

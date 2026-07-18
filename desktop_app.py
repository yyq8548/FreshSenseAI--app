"""Native Windows entry point for FreshSense AI."""

from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from PIL import Image
from PySide6.QtCore import QObject, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QFont, QPixmap
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
from desktop.presenter import result_summary
from tools.explainability import render_gradcam_overlay
from utils.config import (
    FRUIT_CATALOG_PATH,
    KNOWLEDGE_BASE_PATH,
    MODEL_PATH,
    OPEN_SET_GATE_PATH,
    PROJECT_ROOT,
    REQUIRE_OPEN_SET_GATE,
    SAFETY_NOTICE,
)
from utils.feedback import build_feedback_url
from utils.startup import StartupValidationError, validate_startup
from utils.version import APP_VERSION


IMAGE_FILTER = "Images (*.jpg *.jpeg *.png)"


class DropImageLabel(QLabel):
    image_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__(
            "Choose a clear fruit photo\n"
            "Drop a JPG or PNG here, or use Choose photo"
        )
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(420, 300)
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
            validate_startup(
                MODEL_PATH,
                KNOWLEDGE_BASE_PATH,
                FRUIT_CATALOG_PATH,
                OPEN_SET_GATE_PATH,
                REQUIRE_OPEN_SET_GATE,
            )
            self.loaded.emit(
                FruitScannerAgent(
                    model_path=MODEL_PATH,
                    catalog_path=FRUIT_CATALOG_PATH,
                    knowledge_base_path=KNOWLEDGE_BASE_PATH,
                    open_set_gate_path=OPEN_SET_GATE_PATH,
                    require_open_set_gate=REQUIRE_OPEN_SET_GATE,
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
        self.last_state: AgentState | None = None
        self._model_thread: QThread | None = None
        self._model_worker: ModelLoader | None = None
        self._analysis_thread: QThread | None = None
        self._analysis_worker: AnalysisWorker | None = None
        self._build_ui()
        self._load_model()

    def _build_ui(self) -> None:
        self.setWindowTitle(f"FreshSense AI {APP_VERSION}")
        self.resize(1280, 900)
        self.setMinimumSize(1000, 700)

        page = QWidget()
        page.setObjectName("page")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(44, 0, 44, 40)
        page_layout.setSpacing(0)

        nav = QFrame()
        nav.setObjectName("nav")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        brand = QLabel("FreshSense AI")
        brand.setObjectName("brand")
        version = QLabel(f"WINDOWS PUBLIC BETA  ·  {APP_VERSION}")
        version.setObjectName("version")
        privacy_chip = QLabel("PRIVATE · ON DEVICE")
        privacy_chip.setObjectName("privacyChip")
        nav_layout.addWidget(brand)
        nav_layout.addWidget(version)
        nav_layout.addStretch(1)
        nav_layout.addWidget(privacy_chip)
        page_layout.addWidget(nav)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(0, 36, 0, 38)
        hero_layout.setSpacing(38)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(10)
        eyebrow = QLabel("VISION + RETRIEVAL + REASONING")
        eyebrow.setObjectName("eyebrow")
        headline = QLabel("Fruit freshness,\nexplained by AI.")
        headline.setObjectName("headline")
        headline.setWordWrap(True)
        intro = QLabel(
            "Photograph one apple, banana, or orange. FreshSense validates the "
            "input, classifies visible freshness patterns, retrieves reviewed "
            "food guidance, and explains what to do next."
        )
        intro.setObjectName("heroCopy")
        intro.setWordWrap(True)
        hero_copy.addWidget(eyebrow)
        hero_copy.addWidget(headline)
        hero_copy.addWidget(intro)
        hero_copy.addStretch(1)
        hero_layout.addLayout(hero_copy, 11)

        hero_image = QLabel()
        hero_image.setObjectName("heroImage")
        hero_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_image.setMinimumSize(360, 220)
        hero_image_path = PROJECT_ROOT / "assets" / "freshsense-hero-still-life.png"
        if hero_image_path.is_file():
            hero_image.setPixmap(
                QPixmap(str(hero_image_path)).scaled(
                    440,
                    250,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            hero_image.setText("APPLE  ·  BANANA  ·  ORANGE")
        hero_layout.addWidget(hero_image, 9)
        page_layout.addWidget(hero)

        section_title = QLabel("Try the scanner.")
        section_title.setObjectName("sectionTitle")
        section_intro = QLabel(
            "Choose one clear photo. FreshSense keeps the image in memory and "
            "does not upload or retain it by default."
        )
        section_intro.setObjectName("sectionIntro")
        section_intro.setWordWrap(True)
        page_layout.addWidget(section_title)
        page_layout.addWidget(section_intro)

        scope_row = QHBoxLayout()
        scope_row.setSpacing(8)
        for text in ("Apple", "Banana", "Orange", "One fruit type per photo"):
            chip = QLabel(text)
            chip.setObjectName("scopeChip")
            scope_row.addWidget(chip)
        scope_row.addStretch(1)
        page_layout.addSpacing(14)
        page_layout.addLayout(scope_row)

        notice = QLabel(SAFETY_NOTICE)
        notice.setWordWrap(True)
        notice.setObjectName("safetyNotice")
        page_layout.addSpacing(14)
        page_layout.addWidget(notice)

        self.scanner_section = QFrame()
        self.scanner_section.setObjectName("scannerSection")
        scanner_layout = QVBoxLayout(self.scanner_section)
        scanner_layout.setContentsMargins(0, 0, 0, 0)
        scanner_layout.setSpacing(16)
        content = QHBoxLayout()
        content.setSpacing(22)
        scanner_layout.addLayout(content)

        left_card = QFrame()
        left_card.setObjectName("inputPanel")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(14)
        input_label = QLabel("PHOTO INPUT")
        input_label.setObjectName("panelLabel")
        left_layout.addWidget(input_label)
        self.preview = DropImageLabel()
        self.preview.image_selected.connect(self.select_image)
        left_layout.addWidget(self.preview, 1)

        self.explanation_note = QLabel("")
        self.explanation_note.setObjectName("explanationNote")
        self.explanation_note.setWordWrap(True)
        self.explanation_note.hide()
        left_layout.addWidget(self.explanation_note)

        utility_row = QHBoxLayout()
        utility_row.setSpacing(10)
        choose_button = QPushButton("Choose photo")
        choose_button.setObjectName("secondaryButton")
        choose_button.clicked.connect(self.choose_image)
        utility_row.addWidget(choose_button, 1)

        history_button = QPushButton("Scan history")
        history_button.setObjectName("secondaryButton")
        history_button.clicked.connect(self.show_history)
        utility_row.addWidget(history_button, 1)
        left_layout.addLayout(utility_row)

        self.feedback_button = QPushButton("Report incorrect result")
        self.feedback_button.setObjectName("textButton")
        self.feedback_button.setEnabled(False)
        self.feedback_button.setToolTip(
            "Opens a prefilled GitHub issue without attaching your photo."
        )
        self.feedback_button.clicked.connect(self.report_incorrect_result)
        left_layout.addWidget(self.feedback_button)

        self.analyze_button = QPushButton("Analyze freshness")
        self.analyze_button.setObjectName("primaryButton")
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self.analyze)
        left_layout.addWidget(self.analyze_button)
        content.addWidget(left_card, 5)

        right_card = QFrame()
        right_card.setObjectName("resultPanel")
        right_card.setProperty("tone", "empty")
        self.result_panel = right_card
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(28, 26, 28, 24)
        right_layout.setSpacing(14)

        analysis_label = QLabel("ANALYSIS")
        analysis_label.setObjectName("panelLabel")
        right_layout.addWidget(analysis_label)

        self.status = QLabel("LOADING VALIDATED MODEL")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        right_layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        right_layout.addWidget(self.progress)

        self.result_title = QLabel("Your result will appear here.")
        self.result_title.setObjectName("resultTitle")
        self.result_title.setWordWrap(True)
        right_layout.addWidget(self.result_title)

        self.confidence = QLabel("")
        self.confidence.setObjectName("confidence")
        right_layout.addWidget(self.confidence)

        self.recommendation = QLabel(
            "FreshSense withholds a freshness label when the photo is unsupported, "
            "unclear, or below the configured confidence checks."
        )
        self.recommendation.setWordWrap(True)
        self.recommendation.setObjectName("recommendation")
        right_layout.addWidget(self.recommendation)

        self.details = QLabel("Knowledge mode: initializing local semantic embeddings")
        self.details.setWordWrap(True)
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.details)
        right_layout.addWidget(scroll, 1)

        route = QHBoxLayout()
        route.setSpacing(6)
        for index, text in enumerate(("See", "Validate", "Predict", "Retrieve", "Recommend")):
            step = QLabel(text)
            step.setObjectName("routeStep")
            step.setProperty("active", index == 0)
            step.setAlignment(Qt.AlignmentFlag.AlignCenter)
            route.addWidget(step, 1)
        right_layout.addLayout(route)
        content.addWidget(right_card, 4)

        page_layout.addSpacing(20)
        page_layout.addWidget(self.scanner_section)

        footer = QFrame()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 26, 0, 0)
        footer_copy = QLabel(
            "Local-first decision support · Photos are not uploaded or retained by default."
        )
        footer_copy.setObjectName("footerCopy")
        footer_layout.addWidget(footer_copy)
        footer_layout.addStretch(1)
        footer_version = QLabel(f"FreshSense AI {APP_VERSION}")
        footer_version.setObjectName("footerCopy")
        footer_layout.addWidget(footer_version)
        page_layout.addWidget(footer)

        self.page_scroll = QScrollArea()
        self.page_scroll.setObjectName("pageScroll")
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.page_scroll.setWidget(page)
        self.setCentralWidget(self.page_scroll)
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
        if agent.retriever_tool.semantic_ready:
            self.status.setText("READY FOR ONE CLEAR FRUIT PHOTO")
            self.details.setText("Knowledge mode: local semantic embeddings")
        else:
            self.status.setText("READY · KEYWORD RETRIEVAL FALLBACK")
            self.details.setText("Knowledge mode: local keyword fallback")
        self._update_analyze_state()
        smoke_marker = os.getenv("FRESHSENSE_STARTUP_SMOKE_FILE")
        if smoke_marker:
            Path(smoke_marker).write_text(
                "ready\n" if agent.retriever_tool.semantic_ready else "ready-keyword\n",
                encoding="utf-8",
            )
            QTimer.singleShot(0, QApplication.instance().quit)

    def _model_failed(self, message: str) -> None:
        self.progress.hide()
        self._set_result_tone("danger")
        self.status.setText("STARTUP VALIDATION FAILED")
        self.result_title.setText("Validated model unavailable")
        self.recommendation.setText(
            "FreshSense will not analyze a photo until its local model and safety assets pass validation."
        )
        self.details.setText("Reinstall FreshSense or contact the application provider.")
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
        self._set_result_tone("neutral")
        self.status.setText("PHOTO READY")
        self.result_title.setText("Ready to analyze")
        self.confidence.clear()
        self.recommendation.setText(
            "FreshSense will check image quality and supported input before running the freshness model."
        )
        self.details.setText(f"Selected locally: {Path(path).name}\nThe photo has not been uploaded or saved by FreshSense.")
        self.explanation_note.clear()
        self.explanation_note.hide()
        self._update_analyze_state()

    def analyze(self) -> None:
        if self.agent is None or self.current_image is None:
            return
        self.analyze_button.setEnabled(False)
        self.progress.show()
        self.progress.setRange(0, 0)
        self._set_result_tone("empty")
        self.status.setText("CHECKING QUALITY, SUPPORT, AND MODEL EVIDENCE")
        self.result_title.setText("Analyzing visible freshness patterns")
        self.confidence.clear()
        self.recommendation.setText(
            "The supported-input gate runs before the freshness classifier."
        )
        self.details.setText("See · Validate · Predict · Retrieve · Recommend")

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
        self.last_state = state
        self.feedback_button.setEnabled(True)
        summary = result_summary(
            state,
            catalog=self.agent.catalog if self.agent else None,
        )
        if state.decision == "accept_prediction":
            tone = "danger" if summary["risk"].lower() == "high" else "success"
            status = "ACCEPTED VISUAL RESULT"
        elif state.decision in {"unsupported_input", "uncertain_input"}:
            tone = "caution"
            status = "RESULT WITHHELD FOR SAFETY"
        else:
            tone = "neutral"
            status = "REVIEW THE RESULT"
        self._set_result_tone(tone)
        self.result_title.setText(summary["title"])
        self.confidence.setText(
            f"Confidence  {summary['confidence']}     ·     Visual risk  {summary['risk']}"
        )
        self.recommendation.setText(summary["recommendation"])
        self.details.setText(summary["details"])
        self._show_explanation(state)
        history_saved = self._record_history(state, summary)
        self.status.setText(status if history_saved else f"{status} · HISTORY NOT SAVED")

    def _show_explanation(self, state: AgentState) -> None:
        metadata = state.metadata.get("explainability", {})
        if state.decision != "accept_prediction" or metadata.get("method") != "grad_cam":
            self.explanation_note.clear()
            self.explanation_note.hide()
            return
        try:
            overlay = render_gradcam_overlay(state.image, metadata["heatmap"])
            buffer = BytesIO()
            overlay.save(buffer, format="PNG")
            pixmap = QPixmap()
            if not pixmap.loadFromData(buffer.getvalue(), "PNG"):
                raise ValueError("Qt could not load the explanation overlay.")
            self.preview.setPixmap(
                pixmap.scaled(
                    self.preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.explanation_note.setText(str(metadata["disclaimer"]))
            self.explanation_note.show()
        except Exception:
            self.explanation_note.clear()
            self.explanation_note.hide()

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

    def report_incorrect_result(self) -> None:
        if self.last_state is None:
            return
        QDesktopServices.openUrl(QUrl(build_feedback_url(self.last_state)))

    def _analysis_failed(self, message: str) -> None:
        self._set_result_tone("danger")
        self.status.setText("ANALYSIS FAILED")
        self.result_title.setText("The photo could not be analyzed")
        self.recommendation.setText("Try another clear photo or restart FreshSense.")
        self.details.setText(message)
        QMessageBox.warning(self, "Could not analyze photo", message)

    def _analysis_finished(self) -> None:
        self.progress.hide()
        self._update_analyze_state()

    def _set_result_tone(self, tone: str) -> None:
        self.result_panel.setProperty("tone", tone)
        widgets = [self.result_panel, *self.result_panel.findChildren(QWidget)]
        for widget in widgets:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.result_panel.update()

    def _update_analyze_state(self) -> None:
        self.analyze_button.setEnabled(self.agent is not None and self.current_image is not None)


def _is_supported_image(path: str) -> bool:
    return Path(path).suffix.lower() in {".jpg", ".jpeg", ".png"}


def _stylesheet() -> str:
    return """
        QWidget {
            background: #F6F7F2;
            color: #172019;
            font-family: "Aptos", "Segoe UI Variable", "Segoe UI";
            font-size: 14px;
        }
        QLabel { background: transparent; }
        QWidget#page { background: #F6F7F2; }
        QScrollArea#pageScroll { background: #F6F7F2; border: none; }
        QScrollArea#pageScroll > QWidget > QWidget { background: #F6F7F2; }

        QFrame#nav {
            min-height: 70px;
            max-height: 70px;
            border-bottom: 1px solid #D9DFD5;
            background: #F6F7F2;
        }
        QLabel#brand { font-size: 20px; font-weight: 700; letter-spacing: -1px; }
        QLabel#version { color: #667068; font-size: 11px; font-weight: 700; margin-left: 12px; }
        QLabel#privacyChip {
            color: #294D31;
            background: #EEF3E8;
            border: 1px solid #CAD9C6;
            border-radius: 13px;
            padding: 6px 10px;
            font-size: 11px;
            font-weight: 700;
            min-height: 18px;
            max-height: 26px;
        }

        QFrame#hero { background: #F6F7F2; }
        QLabel#eyebrow { color: #416B49; font-size: 12px; font-weight: 700; letter-spacing: 2px; }
        QLabel#headline {
            color: #172019;
            font-family: Georgia, "Times New Roman";
            font-size: 52px;
            font-weight: 600;
            letter-spacing: -2px;
            line-height: 0.95;
        }
        QLabel#heroCopy { color: #667068; font-size: 16px; line-height: 1.5; }
        QLabel#heroImage { background: #EEF3E8; border-radius: 22px; }

        QLabel#sectionTitle {
            color: #172019;
            font-family: Georgia, "Times New Roman";
            font-size: 36px;
            font-weight: 600;
            letter-spacing: -1px;
        }
        QLabel#sectionIntro { color: #667068; font-size: 15px; margin-top: 3px; }
        QLabel#scopeChip {
            color: #294D31;
            background: #FFFFFF;
            border: 1px solid #D9DFD5;
            border-radius: 14px;
            padding: 7px 11px;
            font-size: 12px;
            font-weight: 600;
        }
        QLabel#safetyNotice {
            background: #F7EFE5;
            border: 1px solid #EAD7BD;
            border-radius: 14px;
            padding: 13px 15px;
            color: #5E4B34;
            line-height: 1.45;
        }

        QFrame#scannerSection { background: transparent; }
        QFrame#inputPanel {
            background: #FFFFFF;
            border: 1px solid #D9DFD5;
            border-radius: 20px;
        }
        QFrame#resultPanel {
            background: #F0F1EE;
            border: 1px solid #D9DFD5;
            border-radius: 22px;
            min-height: 470px;
        }
        QFrame#resultPanel[tone="empty"] { background: #172019; border-color: #172019; }
        QFrame#resultPanel[tone="success"] { background: #EEF3E8; border-color: #CAD9C6; }
        QFrame#resultPanel[tone="caution"] { background: #F7EFE5; border-color: #EAD7BD; }
        QFrame#resultPanel[tone="danger"] { background: #F7E9E4; border-color: #E5C9C0; }
        QFrame#resultPanel[tone="neutral"] { background: #F0F1EE; border-color: #D9DFD5; }

        QLabel#panelLabel { color: #667068; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
        QFrame#resultPanel[tone="empty"] QLabel#panelLabel { color: #AEB9B0; }
        QLabel#dropZone {
            background: #EEF3E8;
            border: 2px dashed #A8B9A6;
            border-radius: 16px;
            color: #526157;
            font-size: 16px;
            font-weight: 500;
            padding: 18px;
        }
        QLabel#explanationNote {
            background: #EEF4FF;
            border: 1px solid #B8C9E8;
            border-radius: 10px;
            padding: 10px 12px;
            color: #314C73;
            font-size: 12px;
        }

        QPushButton {
            min-height: 44px;
            border: 1px solid #416B49;
            border-radius: 22px;
            background: #FFFFFF;
            color: #294D31;
            font-weight: 600;
            padding: 0 18px;
        }
        QPushButton:hover { background: #EEF3E8; }
        QPushButton:pressed { background: #DDE8D9; padding-top: 2px; }
        QPushButton:focus { border: 2px solid #6F8F72; }
        QPushButton#primaryButton { background: #294D31; color: #FFFFFF; border-color: #294D31; }
        QPushButton#primaryButton:hover { background: #1F3D27; }
        QPushButton#textButton { background: transparent; border-color: transparent; text-decoration: underline; }
        QPushButton#textButton:hover { color: #172019; background: #EEF3E8; }
        QPushButton:disabled { background: #E4E8E2; color: #8A948D; border-color: #E4E8E2; }

        QLabel#status { color: #294D31; font-size: 12px; font-weight: 700; letter-spacing: 1px; }
        QLabel#resultTitle {
            color: #172019;
            font-family: Georgia, "Times New Roman";
            font-size: 35px;
            font-weight: 600;
            letter-spacing: -1px;
            margin-top: 5px;
        }
        QLabel#confidence { color: #526157; font-weight: 600; padding: 9px 0; }
        QLabel#recommendation { color: #27322B; font-size: 15px; line-height: 1.5; }
        QFrame#resultPanel[tone="empty"] QLabel#status,
        QFrame#resultPanel[tone="empty"] QLabel#resultTitle { color: #F5F7F3; }
        QFrame#resultPanel[tone="empty"] QLabel#confidence,
        QFrame#resultPanel[tone="empty"] QLabel#recommendation,
        QFrame#resultPanel[tone="empty"] QScrollArea QLabel { color: #C5CDC6; }

        QLabel#routeStep {
            background: #D9DFD5;
            color: #526157;
            border-radius: 3px;
            padding: 6px 3px;
            font-size: 10px;
            font-weight: 600;
        }
        QLabel#routeStep[active="true"] { background: #A9C4A5; color: #172019; }
        QFrame#resultPanel[tone="empty"] QLabel#routeStep { background: #3B473D; color: #AEB9B0; }
        QFrame#resultPanel[tone="empty"] QLabel#routeStep[active="true"] { background: #A9C4A5; color: #172019; }

        QScrollArea { background: transparent; border: none; }
        QScrollArea > QWidget > QWidget { background: transparent; }
        QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
        QScrollBar::handle:vertical { background: #B9C3BA; border-radius: 4px; min-height: 28px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QProgressBar { border: none; background: #D9DFD5; border-radius: 3px; min-height: 6px; max-height: 6px; }
        QProgressBar::chunk { background: #6F8F72; border-radius: 3px; }

        QFrame#footer { border-top: 1px solid #D9DFD5; background: transparent; }
        QLabel#footerCopy { color: #667068; font-size: 12px; }
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

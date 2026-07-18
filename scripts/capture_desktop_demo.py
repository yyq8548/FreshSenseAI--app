"""Capture a cursor-free screenshot from the real FreshSense desktop UI."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from desktop.history import ScanHistoryStore
from desktop_app import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args()

    image_path = args.image.resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Demo image does not exist: {image_path}")

    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    history_path = PROJECT_ROOT / "work" / "demo_capture_history.json"

    app = QApplication(sys.argv)
    app.setApplicationName("FreshSense AI Demo Capture")
    app.setOrganizationName("FreshSense")
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow(history_store=ScanHistoryStore(history_path))
    window.show()

    elapsed = 0
    analysis_started = False

    def poll() -> None:
        nonlocal elapsed, analysis_started
        elapsed += 1
        if not analysis_started and window.agent is not None:
            window.select_image(str(image_path))
            window.analyze()
            analysis_started = True
        elif analysis_started and window.last_state is not None:
            app.processEvents()
            if not window.grab().save(str(output_path), "PNG"):
                raise RuntimeError(f"Could not save demo screenshot: {output_path}")
            print(f"Desktop screenshot: {output_path}")
            app.quit()
            return
        if elapsed >= args.timeout_seconds:
            raise TimeoutError("FreshSense demo capture timed out.")

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(1000)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

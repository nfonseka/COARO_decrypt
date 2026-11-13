"""PySide6 main window for COARO Decrypt (default Fusion style, no stylesheet)."""
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from coaro_decrypt import core
from coaro_decrypt.worker import DecryptWorker

GREEN = QColor("#2E7D32")
RED = QColor("#C62828")
GREY = QColor("#8C8C8C")
BLUE = QColor("#308CC6")

STATUS_TEXT = {
    core.OK: ("Decrypted", GREEN),
    core.NOT_COARO: ("Skipped", GREY),
    core.EXISTS: ("Skipped", GREY),
    core.BAD_PADDING: ("Failed", RED),
    core.ERROR: ("Failed", RED),
}


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / name


def dot_icon(color: QColor) -> QIcon:
    pix = QPixmap(10, 10)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawEllipse(1, 1, 8, 8)
    p.end()
    return QIcon(pix)


class FolderEdit(QLineEdit):
    """Line edit that accepts a folder dropped from the file manager."""

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).is_dir():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.setText(urls[0].toLocalFile())
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class HintLabel(QLabel):
    def __init__(self):
        super().__init__()
        font = self.font()
        font.setPointSizeF(font.pointSizeF() * 0.9)
        self.setFont(font)
        self.setWordWrap(True)

    def show_hint(self, text: str, color: QColor | None = None):
        pal = self.palette()
        if color is None:
            color = QApplication.palette().color(QPalette.PlaceholderText)
        pal.setColor(QPalette.WindowText, color)
        self.setPalette(pal)
        self.setText(text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("COARO Decrypt")
        icon = resource_path("assets/icon.png")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))

        self._thread: QThread | None = None
        self._worker: DecryptWorker | None = None
        self._dest_for_run: Path | None = None
        self._icons = {status: dot_icon(color) for status, (_, color) in STATUS_TEXT.items()}

        self._build_ui()
        self._load_settings()
        self._validate()
        self.statusBar().showMessage("Ready")

    # ---------- layout ----------

    def _build_ui(self):
        # Input
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_toggle = QToolButton()
        self.key_toggle.setText("Show")
        self.key_toggle.setCheckable(True)
        self.key_toggle.setToolTip("Show or hide the key")
        self.key_toggle.toggled.connect(self._toggle_key)
        self.key_hint = HintLabel()

        self.src_edit = FolderEdit()
        self.src_edit.setPlaceholderText("Folder with encrypted files")
        self.src_hint = HintLabel()
        self.dst_edit = FolderEdit()
        self.dst_edit.setPlaceholderText("Folder for decrypted files")
        self.dst_hint = HintLabel()

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.addRow("&Key:", self._row(self.key_edit, self.key_toggle))
        form.addRow("", self.key_hint)
        form.addRow("&Source:", self._row(self.src_edit, self._browse_button(self.src_edit, "Choose source folder")))
        form.addRow("", self.src_hint)
        form.addRow("&Destination:", self._row(self.dst_edit, self._browse_button(self.dst_edit, "Choose destination folder")))
        form.addRow("", self.dst_hint)
        self.input_box = QGroupBox("Input")
        self.input_box.setLayout(form)

        # Options
        self.overwrite_check = QCheckBox("Overwrite existing files")
        note = HintLabel()
        note.show_hint("Files that can’t be decrypted (wrong key or corrupt) are skipped and listed in the results.")
        opts = QVBoxLayout()
        opts.addWidget(self.overwrite_check)
        opts.addWidget(note)
        self.options_box = QGroupBox("Options")
        self.options_box.setLayout(opts)

        # Actions
        self.decrypt_button = QPushButton("Decrypt")
        self.decrypt_button.setDefault(True)
        self.decrypt_button.setMinimumWidth(120)
        self.decrypt_button.clicked.connect(self._on_decrypt_clicked)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setMinimumWidth(56)
        self.progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.decrypt_button)
        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.progress_label)

        left = QVBoxLayout()
        left.addWidget(self.input_box)
        left.addWidget(self.options_box)
        left.addStretch()
        left.addLayout(button_row)
        left.addLayout(progress_row)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMinimumWidth(340)
        left_widget.setMaximumWidth(420)

        # Results
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["File", "Status", "Detail"])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 240)

        self.summary_label = QLabel("")
        self.open_button = QPushButton("Open destination folder")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_destination)
        summary_row = QHBoxLayout()
        summary_row.addWidget(self.summary_label, 1)
        summary_row.addWidget(self.open_button)

        results = QVBoxLayout()
        results.addWidget(self.table, 1)
        results.addLayout(summary_row)
        results_box = QGroupBox("Results")
        results_box.setLayout(results)

        central = QWidget()
        main = QHBoxLayout(central)
        main.addWidget(left_widget)
        main.addWidget(results_box, 1)
        self.setCentralWidget(central)

        for edit in (self.key_edit, self.src_edit, self.dst_edit):
            edit.textChanged.connect(self._validate)

    def _row(self, *widgets) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        for i, widget in enumerate(widgets):
            layout.addWidget(widget, 1 if i == 0 else 0)
        return w

    def _browse_button(self, target: QLineEdit, title: str) -> QPushButton:
        button = QPushButton("Browse…")
        button.clicked.connect(lambda: self._browse(target, title))
        return button

    # ---------- input handling ----------

    def _toggle_key(self, shown: bool):
        self.key_edit.setEchoMode(QLineEdit.Normal if shown else QLineEdit.Password)
        self.key_toggle.setText("Hide" if shown else "Show")

    def _browse(self, target: QLineEdit, title: str):
        path = QFileDialog.getExistingDirectory(self, title, target.text() or str(Path.home()))
        if path:
            target.setText(path)

    def _validate(self) -> bool:
        key_ok = src_ok = dst_ok = False

        key = self.key_edit.text()
        if not key:
            self.key_hint.show_hint("16, 24 or 32 bytes")
        else:
            try:
                raw = core.validate_key(key)
                self.key_hint.show_hint(f"{len(raw)} bytes ({core.KEY_LENGTHS[len(raw)]})", GREEN)
                key_ok = True
            except ValueError as e:
                self.key_hint.show_hint(str(e), RED)

        src_text = self.src_edit.text().strip()
        src = Path(src_text) if src_text else None
        if src is None:
            self.src_hint.show_hint("Choose a folder, or drop one here")
        elif not src.is_dir():
            self.src_hint.show_hint("Folder does not exist", RED)
        else:
            try:
                files = core.list_files(src)
            except OSError as e:
                self.src_hint.show_hint(e.strerror or str(e), RED)
            else:
                n = sum(core.is_coaro(p) for p in files)
                self.src_hint.show_hint(
                    f"{n} COARO file{'s' if n != 1 else ''} found", None if n else RED
                )
                src_ok = n > 0

        dst_text = self.dst_edit.text().strip()
        dst = Path(dst_text) if dst_text else None
        if dst is None:
            self.dst_hint.show_hint("Choose a folder, or drop one here")
        elif src is not None and src.is_dir() and dst.exists() and dst.resolve() == src.resolve():
            self.dst_hint.show_hint("Must be different from the source folder", RED)
        elif dst.exists() and not dst.is_dir():
            self.dst_hint.show_hint("Not a folder", RED)
        else:
            self.dst_hint.show_hint("Folder exists" if dst.is_dir() else "Will be created if missing")
            dst_ok = True

        valid = key_ok and src_ok and dst_ok
        if self._thread is None:
            self.decrypt_button.setEnabled(valid)
        return valid

    # ---------- running ----------

    def _set_running(self, running: bool):
        self.input_box.setEnabled(not running)
        self.options_box.setEnabled(not running)
        self.decrypt_button.setText("Cancel" if running else "Decrypt")
        self.decrypt_button.setEnabled(True)
        if not running:
            self._validate()

    def _on_decrypt_clicked(self):
        if self._worker is not None:
            self._worker.cancel()
            self.decrypt_button.setEnabled(False)
            self.statusBar().showMessage("Cancelling…")
            return
        if not self._validate():
            return

        self._save_settings()
        self.table.setRowCount(0)
        self.summary_label.clear()
        self.open_button.setEnabled(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress_label.setText("0 / 0")

        self._dest_for_run = Path(self.dst_edit.text().strip())
        self._worker = DecryptWorker(
            Path(self.src_edit.text().strip()),
            self._dest_for_run,
            core.validate_key(self.key_edit.text()),
            self.overwrite_check.isChecked(),
        )
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.fileDone.connect(self._on_file_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_done)

        self._set_running(True)
        self.statusBar().showMessage("Decrypting…")
        self._thread.start()

    def _on_progress(self, done: int, total: int):
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        self.progress_label.setText(f"{done} / {total}")

    def _on_file_done(self, result: core.FileResult):
        text, _ = STATUS_TEXT[result.status]
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(result.path.name))
        status = QTableWidgetItem(self._icons[result.status], text)
        self.table.setItem(row, 1, status)
        self.table.setItem(row, 2, QTableWidgetItem(result.detail))
        self.table.scrollToBottom()
        self.statusBar().showMessage(f"Decrypting… {result.path.name}")

    def _on_finished(self, summary: dict):
        counts = summary["counts"]
        ok = counts.get(core.OK, 0)
        skipped = counts.get(core.NOT_COARO, 0) + counts.get(core.EXISTS, 0)
        failed = counts.get(core.BAD_PADDING, 0) + counts.get(core.ERROR, 0)
        self.summary_label.setText(f"{ok} decrypted, {skipped} skipped, {failed} failed")
        self.open_button.setEnabled(self._dest_for_run is not None and self._dest_for_run.is_dir())
        if summary["cancelled"]:
            self.statusBar().showMessage("Cancelled")
        elif failed:
            self.statusBar().showMessage(f"Finished — {failed} file{'s' if failed != 1 else ''} need{'s' if failed == 1 else ''} attention")
        else:
            self.statusBar().showMessage("Finished")

    def _on_failed(self, message: str):
        self.summary_label.setText("")
        self.statusBar().showMessage(f"Error: {message}")

    def _on_thread_done(self):
        self._thread = None
        self._worker = None
        self._set_running(False)

    def _open_destination(self):
        if self._dest_for_run is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._dest_for_run)))

    # ---------- settings ----------

    def _load_settings(self):
        s = QSettings("COARO", "Decrypt")
        self.src_edit.setText(s.value("source", "", str))
        self.dst_edit.setText(s.value("destination", "", str))
        self.overwrite_check.setChecked(s.value("overwrite", False, bool))
        geometry = s.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(1100, 680)

    def _save_settings(self):
        s = QSettings("COARO", "Decrypt")
        s.setValue("source", self.src_edit.text().strip())
        s.setValue("destination", self.dst_edit.text().strip())
        s.setValue("overwrite", self.overwrite_check.isChecked())
        s.setValue("geometry", self.saveGeometry())

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._save_settings()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("COARO Decrypt")
    window = MainWindow()
    window.show()
    return app.exec()

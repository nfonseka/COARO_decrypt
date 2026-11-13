"""Runs core.decrypt_dir off the GUI thread."""
import threading
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from coaro_decrypt import core


class DecryptWorker(QObject):
    progress = Signal(int, int)       # done, total
    fileDone = Signal(object)         # core.FileResult
    finished = Signal(dict)           # {"counts": {status: n}, "cancelled": bool}
    failed = Signal(str)

    def __init__(self, src: Path, dest: Path, key: bytes, overwrite: bool):
        super().__init__()
        self._src = src
        self._dest = dest
        self._key = key
        self._overwrite = overwrite
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    @Slot()
    def run(self):
        counts = Counter()
        try:
            for done, total, result in core.decrypt_dir(
                self._src, self._dest, self._key, self._overwrite, self._cancel.is_set
            ):
                counts[result.status] += 1
                self.fileDone.emit(result)
                self.progress.emit(done, total)
        except Exception as e:  # report anything unexpected instead of killing the thread
            self.failed.emit(str(e))
            return
        self.finished.emit({"counts": dict(counts), "cancelled": self._cancel.is_set()})

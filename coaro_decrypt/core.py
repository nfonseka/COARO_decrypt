"""Decryption logic for COARO_ files, shared by the GUI and the CLI.

File layout: b"COARO_" | 16-byte IV | AES-CBC ciphertext (PKCS7 padded).
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

MAGIC = b"COARO_"
IV_LEN = 16
KEY_LENGTHS = {16: "AES-128", 24: "AES-192", 32: "AES-256"}

OK = "ok"
NOT_COARO = "not_coaro"
EXISTS = "exists"
BAD_PADDING = "bad_padding"
ERROR = "error"


@dataclass
class FileResult:
    path: Path
    status: str
    detail: str = ""


def validate_key(key: str) -> bytes:
    raw = key.encode("utf-8")
    if len(raw) not in KEY_LENGTHS:
        raise ValueError(f"Key is {len(raw)} bytes; it must be 16, 24 or 32 bytes")
    return raw


def list_files(src: Path) -> list[Path]:
    return sorted(p for p in Path(src).iterdir() if p.is_file())


def is_coaro(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def format_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def decrypt_file(path: Path, key: bytes, dest_dir: Path, overwrite: bool = False) -> FileResult:
    path = Path(path)
    try:
        with open(path, "rb") as f:
            if f.read(len(MAGIC)) != MAGIC:
                return FileResult(path, NOT_COARO, "Not a COARO file")
            iv = f.read(IV_LEN)
            encrypted = f.read()

        out = Path(dest_dir) / path.name
        if out.exists() and not overwrite:
            return FileResult(path, EXISTS, "Already exists in destination")

        if len(iv) != IV_LEN or not encrypted or len(encrypted) % AES.block_size:
            return FileResult(path, BAD_PADDING, "Truncated or corrupt file")
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        try:
            decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
        except ValueError:
            return FileResult(path, BAD_PADDING, "Bad padding — wrong key or corrupt file")

        with open(out, "wb") as f:
            f.write(decrypted)
        return FileResult(path, OK, format_size(len(decrypted)))
    except OSError as e:
        return FileResult(path, ERROR, e.strerror or str(e))


def decrypt_dir(
    src: Path,
    dest: Path,
    key: bytes,
    overwrite: bool = False,
    cancel: Callable[[], bool] = lambda: False,
) -> Iterator[tuple[int, int, FileResult]]:
    """Yield (done, total, result) for each file in src. Raises ValueError for bad folders."""
    src, dest = Path(src), Path(dest)
    if not src.is_dir():
        raise ValueError(f"Source folder does not exist: {src}")
    dest.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dest.resolve():
        raise ValueError("Destination must be different from the source folder")

    files = list_files(src)
    total = len(files)
    for i, path in enumerate(files, start=1):
        if cancel():
            return
        yield i, total, decrypt_file(path, key, dest, overwrite)

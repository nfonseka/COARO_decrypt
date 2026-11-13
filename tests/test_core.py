import os

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from coaro_decrypt import core

KEY = b"0123456789abcdef0123456789abcdef"


def write_coaro(path, plaintext: bytes, key: bytes = KEY):
    iv = os.urandom(16)
    data = AES.new(key, AES.MODE_CBC, iv=iv).encrypt(pad(plaintext, AES.block_size))
    path.write_bytes(core.MAGIC + iv + data)


@pytest.fixture
def dirs(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    return src, dst


def run(src, dst, key=KEY, overwrite=False):
    return list(core.decrypt_dir(src, dst, key, overwrite))


def test_validate_key():
    assert core.validate_key("a" * 16) == b"a" * 16
    assert len(core.validate_key("b" * 32)) == 32
    with pytest.raises(ValueError):
        core.validate_key("short")


def test_validate_key_counts_bytes_not_chars():
    assert len(core.validate_key("é" * 8)) == 16
    with pytest.raises(ValueError):
        core.validate_key("é" * 15)


def test_decrypts_good_file(dirs):
    src, dst = dirs
    write_coaro(src / "a.txt", b"hello world")
    (index, total, result), = run(src, dst)
    assert (index, total, result.status) == (1, 1, core.OK)
    assert (dst / "a.txt").read_bytes() == b"hello world"


def test_skips_non_coaro_binary_file(dirs):
    src, dst = dirs
    (src / "junk.bin").write_bytes(b"\xff\xfe\x00\x01garbage")
    (result,) = [r for _, _, r in run(src, dst)]
    assert result.status == core.NOT_COARO
    assert not (dst / "junk.bin").exists()


def test_wrong_key_writes_nothing(dirs):
    src, dst = dirs
    write_coaro(src / "a.txt", b"secret data" * 10)
    (result,) = [r for _, _, r in run(src, dst, key=b"x" * 32)]
    assert result.status == core.BAD_PADDING
    assert not (dst / "a.txt").exists()


def test_ignores_subfolders(dirs):
    src, dst = dirs
    (src / "sub").mkdir()
    write_coaro(src / "a.txt", b"x")
    results = run(src, dst)
    assert [r.path.name for _, _, r in results] == ["a.txt"]


def test_existing_output_respects_overwrite(dirs):
    src, dst = dirs
    write_coaro(src / "a.txt", b"new")
    dst.mkdir()
    (dst / "a.txt").write_bytes(b"old")

    (result,) = [r for _, _, r in run(src, dst)]
    assert result.status == core.EXISTS
    assert (dst / "a.txt").read_bytes() == b"old"

    (result,) = [r for _, _, r in run(src, dst, overwrite=True)]
    assert result.status == core.OK
    assert (dst / "a.txt").read_bytes() == b"new"


def test_destination_same_as_source_refused(dirs):
    src, _ = dirs
    write_coaro(src / "a.txt", b"x")
    with pytest.raises(ValueError):
        run(src, src)


def test_missing_source_refused(tmp_path):
    with pytest.raises(ValueError):
        run(tmp_path / "nope", tmp_path / "dst")


def test_progress_counts_skipped_files(dirs):
    src, dst = dirs
    write_coaro(src / "a.txt", b"1")
    (src / "b.md").write_text("plain")
    write_coaro(src / "c.txt", b"3")
    progress = [(i, t) for i, t, _ in run(src, dst)]
    assert progress == [(1, 3), (2, 3), (3, 3)]


def test_cancel_stops_early(dirs):
    src, dst = dirs
    for name in "abc":
        write_coaro(src / name, b"x")
    seen = []
    for i, _, r in core.decrypt_dir(src, dst, KEY, cancel=lambda: len(seen) >= 1):
        seen.append(r)
    assert len(seen) == 1

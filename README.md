# COARO Decrypt

Decrypts `COARO_` files (a `COARO_` header, a 16-byte IV, then AES-CBC data with PKCS7 padding). It comes as a PySide6 desktop app and a small command-line tool.

## Run from source

```
pip install -r requirements-dev.txt
python -m coaro_decrypt      # GUI
python minimal.py           # CLI
```

In the GUI:

1. Enter the key. It must be 16, 24 or 32 bytes when encoded as UTF-8.
2. Choose the source and destination folders. You can also drop a folder onto either field.
3. Click **Decrypt**.

Each file's outcome is listed in the results table. These files are skipped and reported, and nothing is written for them:

- files that are not COARO files
- files that already exist in the destination, unless **Overwrite existing files** is ticked
- files that fail to decrypt, because of a wrong key or corrupt data

## Tests

```
python -m pytest tests
```

## Build

```
pyinstaller app.py --onefile --windowed --name coaro_decrypt --icon assets/icon.png --add-data "assets/icon.png:assets"
pyinstaller minimal.py --onefile --name coaro_decrypt-cli
```

On Windows, use `;` instead of `:` in `--add-data`.

Pushing a `v*` tag runs `.github/workflows/main.yml`. It builds both executables for Linux, Windows and macOS and attaches them to a GitHub release.

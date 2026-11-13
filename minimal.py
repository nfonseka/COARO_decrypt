from coaro_decrypt import core

LABELS = {
    core.OK: "decrypted",
    core.NOT_COARO: "skipped",
    core.EXISTS: "skipped",
    core.BAD_PADDING: "FAILED",
    core.ERROR: "FAILED",
}


def decrypt_files(key: str, source: str, destination: str) -> bool:
    try:
        raw_key = core.validate_key(key)
        failed = 0
        for done, total, result in core.decrypt_dir(source, destination, raw_key):
            print(f"[{done}/{total}] {result.path.name}: {LABELS[result.status]} {result.detail}")
            failed += result.status in (core.BAD_PADDING, core.ERROR)
    except ValueError as e:
        print(e)
        return False

    if failed:
        print(f"{failed} file(s) could not be decrypted")
    return True


if __name__ == "__main__":
    while True:
        key = input("Key: ")
        source = input("Source Directory: ")
        destination = input("Destination Directory: ")

        if decrypt_files(key, source, destination):
            print("Finished")
            break
        print("An error occurred")

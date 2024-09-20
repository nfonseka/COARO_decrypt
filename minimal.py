import glob
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import os


def decrypt_files(key, source, destination):
    try:
        key = bytes(key, 'utf-8')
        try:
            glob.glob(f"{source}/*")
        except Exception as e:
            print("Invalid source directory")
            return False

        try:
            glob.glob(f"{destination}/*")
        except Exception as e:
            print("Invalid destination directory")
            return False

        if not os.path.exists(destination):
            os.makedirs(destination)

        source_size = len(glob.glob(f"{source}/*"))
        i = 0

        for filename in glob.glob(f"{source}/*"):
            with open(filename, 'rb') as f:
                print(f"Decrypting {filename}")
                if f.read(6).decode() != 'COARO_':
                    continue
                iv = f.read(16)
                encrypted = f.read()

            cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            try:
                decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
            except Exception as e:
                print(f"Warning {filename} was incorrectly unpadded")
                decrypted = cipher.decrypt(encrypted)

            # filename from path
            name = filename.split("/")[-1]
            open(f"{destination}/{name}", 'wb').write(decrypted)
            i += 1
            # progress_bar.value = i / source_size
    except Exception as e:
        print(e)

    return True

repeat = True

while repeat:
    key: str = input("Key: ")
    source: str = input("Source Directory: ")
    destination: str = input("Destination Directory: ")

    done = decrypt_files(key, source, destination)

    if not done:
        print("An error occurred")
    else:
        print("Finished")
        repeat = False
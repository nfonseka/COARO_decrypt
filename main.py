import flet as ft
import glob
import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
# def decrypt(key: bytes, source: str, destination: str):
#     for filename in glob.glob(f"{source}/*"):
#         with open(filename, 'rb') as f:
#             if f.read(6).decode() != 'COARO_':
#                 continue
#             iv = f.read(16)
#             encrypted = f.read()
#
#         cipher = AES.new(key, AES.MODE_CBC, iv=iv)
#         decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
#         open(f"{destination}/{filename}", 'wb').write(decrypted)
import os
import shutil
def main(page: ft.Page):
    page.title = "Decrypt Files"
    # page.window_height = 600
    # page.window_width = 500

    key_field = ft.TextField(
        label="Key",
        icon="key",
        password=True,
        can_reveal_password=True
    )

    source_field = ft.TextField(
        label="Source Directory",
        icon=ft.icons.DRIVE_FOLDER_UPLOAD
    )

    destination_field = ft.TextField(
        label="Destination Directory",
        icon="folder"
    )

    progress_bar = ft.ProgressBar(value=0, height=10)
    status = ft.Text("")

    def decrypt_files(e):
        try:
            progress_bar.value = 0
            key = key_field.value
            key = bytes(key, 'utf-8')
            source = source_field.value
            destination = destination_field.value
            try:
                glob.glob(f"{source}/*")
            except Exception as e:
                status.value = "Invalid source directory"
                page.update()
                return

            try:
                glob.glob(f"{destination}/*")
            except Exception as e:
                status.value = "Invalid destination directory"
                page.update()
                return

            if not os.path.exists(destination):
                os.makedirs(destination)


            source_size = len(glob.glob(f"{source}/*"))
            i = 0

            for filename in glob.glob(f"{source}/*"):
                with open(filename, 'rb') as f:
                    status.value = f"Decrypting {filename}"
                    page.update()
                    if f.read(6).decode() != 'COARO_':
                        continue
                    iv = f.read(16)
                    encrypted = f.read()

                cipher = AES.new(key, AES.MODE_CBC, iv=iv)
                try:
                    decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
                except Exception as e:
                    status.value = f"Warning {filename} was incorrectly unpadded"
                    page.update()
                    decrypted = cipher.decrypt(encrypted)

                # filename from path
                name = filename.split("/")[-1]
                open(f"{destination}/{name}", 'wb').write(decrypted)
                i += 1
                progress_bar.value = i / source_size
                page.update()
        except Exception as e:
            status.value = e
            page.update()

        status.value = "Done"
        page.update()

    decrypt_button = ft.FilledButton("Decrypt", icon="lock_open", width=200, height=50, on_click=decrypt_files)

    page.add(key_field, source_field, destination_field,
             ft.Column([decrypt_button, progress_bar], alignment=ft.MainAxisAlignment.CENTER,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER), status)


ft.app(main)
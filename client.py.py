import base64
import io
import os
import json
import threading
import socket
from datetime import datetime

from customtkinter import *
from tkinter import filedialog
from PIL import Image

set_appearance_mode("dark")
set_default_color_theme("blue")


class ChatClient(CTk):
    def __init__(self):
        super().__init__()

        self.geometry("600x500")
        self.title("Chat Client")

        self.username = "User"
        self.sock = None
        self.images = []
        self.is_connected = False

        self.create_ui()
        self.connect()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- UI ----------------

    def create_ui(self):
        # Верхня панель зі статусом
        self.top_frame = CTkFrame(self, height=40)
        self.top_frame.pack(fill="x", pady=(0, 5))

        self.status_label = CTkLabel(
            self.top_frame,
            text="🔴 Підключення...",
            font=("Arial", 12)
        )
        self.status_label.pack(side="left", padx=10)

        # Кнопка зміни ніку
        self.name_btn = CTkButton(
            self.top_frame,
            text=f"👤 {self.username}",
            command=self.change_name,
            width=100
        )
        self.name_btn.pack(side="right", padx=10)

        # Поле чату
        self.chat = CTkScrollableFrame(self)
        self.chat.pack(fill="both", expand=True)

        # Нижня панель
        bottom = CTkFrame(self, height=50)
        bottom.pack(fill="x")

        self.entry = CTkEntry(bottom)
        self.entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        CTkButton(bottom, text="📂", width=40, command=self.send_image).pack(side="left", padx=5)
        CTkButton(bottom, text="➤", width=50, command=self.send_text).pack(side="left", padx=5)

        self.bind("<Return>", lambda e: self.send_text())

    def change_name(self):
        """Діалог зміни нікнейму"""
        dialog = CTkInputDialog(
            text="Введіть новий нікнейм:",
            title="Зміна ніку",
            initial_value=self.username
        )
        new_name = dialog.get_input()

        if new_name and new_name.strip():
            old_name = self.username
            self.username = new_name.strip()
            self.name_btn.configure(text=f"👤 {self.username}")
            self.add_message("Система", f"Ви змінили нік з '{old_name}' на '{self.username}'")

    # ---------------- NETWORK ----------------

    def connect(self):
        """Підключення до сервера"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)  # Таймаут на підключення
            self.sock.connect(("localhost", 8080))
            self.sock.settimeout(None)  # Прибираємо таймаут після підключення

            self.is_connected = True
            self.status_label.configure(text="🟢 Підключено до сервера")

            # Відправляємо повідомлення про вхід
            self.send_json({
                "type": "text",
                "author": "Система",
                "content": f"{self.username} приєднався до чату!"
            })

            # Запускаємо потік отримання
            threading.Thread(target=self.receive, daemon=True).start()

            self.add_message("Система", "✅ Підключено до сервера")

        except socket.timeout:
            self.status_label.configure(text="🔴 Таймаут підключення")
            self.add_message("Система", "❌ Таймаут підключення. Сервер не відповідає")
        except ConnectionRefusedError:
            self.status_label.configure(text="🔴 Сервер не запущено")
            self.add_message("Система", "❌ Сервер не запущено. Запустіть server.py")
        except Exception as e:
            self.status_label.configure(text="🔴 Помилка")
            self.add_message("Система", f"❌ Помилка підключення: {e}")

    def send_json(self, data):
        """Відправка JSON даних на сервер"""
        if not self.is_connected or not self.sock:
            self.add_message("Система", "❌ Немає підключення до сервера")
            return False

        try:
            msg = json.dumps(data, ensure_ascii=False) + "\n"
            self.sock.sendall(msg.encode("utf-8"))
            return True
        except Exception as e:
            self.is_connected = False
            self.status_label.configure(text="🔴 Відключено")
            self.add_message("Система", f"❌ Помилка відправки: {e}")
            return False

    def receive(self):
        """Цикл отримання повідомлень"""
        buffer = ""

        while self.is_connected:
            try:
                self.sock.settimeout(1)
                data = self.sock.recv(8192)

                if not data:
                    break

                buffer += data.decode("utf-8")

                # Обробка повідомлень
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)

                    if line.strip():
                        try:
                            data = json.loads(line)
                            self.after(0, self.handle_data, data)
                        except json.JSONDecodeError:
                            print(f"Помилка JSON: {line}")

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Помилка отримання: {e}")
                break

        # Вихід з циклу - втрата з'єднання
        self.is_connected = False
        self.after(0, lambda: self.status_label.configure(text="🔴 Відключено"))
        self.after(0, lambda: self.add_message("Система", "⚠️ З'єднання з сервером розірвано"))

    def handle_data(self, data):
        """Обробка вхідних даних"""
        msg_type = data.get("type")
        author = data.get("author")
        content = data.get("content")

        # Перевірка наявності обов'язкових полів
        if msg_type == "text" and (not author or not content):
            return

        if msg_type == "image" and not content:
            return

        if msg_type == "text":
            self.add_message(author, content)

        elif msg_type == "image":
            try:
                img_bytes = base64.b64decode(content)
                pil = Image.open(io.BytesIO(img_bytes)).copy()

                # Обмежуємо розмір зображення
                pil.thumbnail((250, 250), Image.Resampling.LANCZOS)
                img = CTkImage(pil, size=pil.size)

                # Обмежуємо кеш зображень
                self.images.append(img)
                if len(self.images) > 30:
                    self.images.pop(0)

                self.add_message(author, "📷 Зображення", img)

            except Exception as e:
                self.add_message("Помилка", f"Не вдалося завантажити зображення: {e}")

    # ---------------- CHAT ----------------

    def add_message(self, author, text, img=None):
        """Додавання повідомлення в чат"""
        try:
            frame = CTkFrame(self.chat, fg_color="transparent")
            frame.pack(anchor="w" if author != self.username else "e", pady=5, padx=5)

            time = datetime.now().strftime("%H:%M")

            # Стилізація повідомлень
            if author == "Система":
                msg = f"🔔 {text}"
                bg_color = "#444444"
            elif author == self.username:
                msg = f"{text}\n[{time}]"
                bg_color = "#1f538d"
            else:
                msg = f"{author} [{time}]\n{text}"
                bg_color = "#2d2d2d"

            # Бабл повідомлення
            bubble = CTkFrame(frame, fg_color=bg_color, corner_radius=10)
            bubble.pack()

            label = CTkLabel(
                bubble,
                text=msg,
                image=img,
                compound="top" if img else None,
                wraplength=350,
                justify="left",
                padx=12,
                pady=8
            )
            label.pack()

            # Безпечний скрол донизу
            self.after(50, self.scroll_to_bottom)

        except Exception as e:
            print(f"Помилка додавання повідомлення: {e}")

    def scroll_to_bottom(self):
        """Безпечний скрол донизу"""
        try:
            if hasattr(self.chat, '_parent_canvas'):
                self.chat._parent_canvas.yview_moveto(1.0)
            elif hasattr(self.chat, 'yview'):
                self.chat.yview_moveto(1.0)
        except:
            pass

    def send_text(self):
        """Відправка текстового повідомлення"""
        if not self.is_connected:
            self.add_message("Система", "❌ Немає підключення до сервера")
            return

        text = self.entry.get().strip()
        if not text:
            return

        if self.send_json({
            "type": "text",
            "author": self.username,
            "content": text
        }):
            self.entry.delete(0, END)

    def send_image(self):
        """Відправка зображення"""
        if not self.is_connected:
            self.add_message("Система", "❌ Немає підключення до сервера")
            return

        path = filedialog.askopenfilename(filetypes=[
            ("Images", "*.png *.jpg *.jpeg *.gif *.bmp")
        ])
        if not path:
            return

        try:
            # Перевірка розміру файлу
            if os.path.getsize(path) > 5 * 1024 * 1024:
                self.add_message("Система", "❌ Файл занадто великий (макс. 5MB)")
                return

            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()

            self.send_json({
                "type": "image",
                "author": self.username,
                "content": b64
            })

        except Exception as e:
            self.add_message("Помилка", str(e))

    # ---------------- CLOSE ----------------

    def on_close(self):
        """Коректне закриття програми"""
        try:
            if self.is_connected and self.sock:
                self.send_json({
                    "type": "text",
                    "author": "Система",
                    "content": f"{self.username} покинув чат!"
                })
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
        except:
            pass

        self.destroy()


if __name__ == "__main__":
    app = ChatClient()
    app.mainloop()

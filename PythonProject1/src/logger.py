from datetime import datetime

class ActionLogger:
    def __init__(self, qt_text_edit=None):
        self.qt_text_edit = qt_text_edit
        self.events = []

    def bind_widget(self, qt_text_edit):
        self.qt_text_edit = qt_text_edit

    def log(self, message: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {message}"
        self.events.append(line)
        if self.qt_text_edit is not None:
            self.qt_text_edit.append(line)

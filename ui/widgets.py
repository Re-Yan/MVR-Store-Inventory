from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel
class InputWidget(QWidget):
    def __init__(self, text, buttonText):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.resize(600, 400)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(text)

        self.input_button = QPushButton(buttonText)
        layout.addWidget(self.input_field)
        layout.addWidget(self.input_button)

class LogSection(QWidget):
    def __init__(self, lineText, buttonText, label):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel(label)
        log_section = InputWidget(lineText, buttonText)

        layout.addWidget(label)
        layout.addWidget(log_section)
    
class SearchSection(QWidget):
    def __init__(self, lineText, buttonText, label):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel(label)
        search_section = InputWidget(lineText, buttonText)

        layout.addWidget(label)
        layout.addWidget(search_section)
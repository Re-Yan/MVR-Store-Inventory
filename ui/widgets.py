from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QDateEdit
from PySide6.QtCore import QDate
from logic.transactions import search_transaction_date
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


class transaction_page(QWidget):
    def __init__(self, label):
        super().__init__()
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        label = QLabel(label)
        self.date_input = QDateEdit(self)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setCalendarPopup(True)

        transaction_button = QPushButton("Submit")
        transaction_button.clicked.connect(lambda: search_transaction_date(self.date_input.date()))

        layout.addWidget(label)
        layout.addWidget(self.date_input)
        layout.addWidget(transaction_button)

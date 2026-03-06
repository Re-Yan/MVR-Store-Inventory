import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel 

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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MVR Inventory")
        self.resize(800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        log_Section = LogSection("Enter SKU", "Submit", "Log Section")
        search_Section = SearchSection("Enter Part Number", "Search", "Search Section")        
        Main_layout = QHBoxLayout(central_widget)
        Main_layout.addWidget(log_Section)
        Main_layout.addWidget(search_Section)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
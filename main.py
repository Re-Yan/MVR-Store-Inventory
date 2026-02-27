import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton

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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MVR Inventory")
        self.resize(800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        logSection = InputWidget("Enter SKU", "Submit")
        searchSection = InputWidget("Enter Part Number", "Search")
        
        Main_layout = QHBoxLayout(central_widget)
        Main_layout.addWidget(logSection)
        Main_layout.addWidget(searchSection)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
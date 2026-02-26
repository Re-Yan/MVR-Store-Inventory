import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MVR Inventory")
        self.resize(800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Input Field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter SKU")

        # Input Button
        self.submit_button = QPushButton("Search")

        #Add to MainLayout
        layout.addWidget(self.input_field)
        layout.addWidget(self.submit_button)




if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
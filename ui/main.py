import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget,  QHBoxLayout
from widgets import  LogSection, SearchSection

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
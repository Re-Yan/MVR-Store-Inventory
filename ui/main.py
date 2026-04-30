import sys
import os

# Add the parent directory of 'ui' to the system path so Python can find 'logic'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout,  QHBoxLayout, QStackedWidget, QPushButton 
from widgets import  LogSection, SearchSection, transaction_page, restock_page, request_page

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MVR Inventory")
        self.resize(800, 600)

        central_widget = QWidget()
        Main_layout = QHBoxLayout(central_widget)
        
        transaction_section = transaction_page("Transaction Search")
        log_section = LogSection("Log Section")
        restock_section = restock_page("Restock Section")
        request_section = request_page("Request List")
        
        # Create a callback that fills the SKU field when a suggestion is selected
        def on_suggestion_selected(sku):
            log_section.sku_input.setText(sku)
        
        search_Section = SearchSection("Enter Part Number", "Search", "Search Section", on_selection=on_suggestion_selected) 
        Main_layout.addWidget(search_Section)
        
        navigation_sideBar = QWidget()
        nav_layout = QVBoxLayout()
        navigation_sideBar.setLayout(nav_layout)

        button1 = QPushButton("Search")
        button1.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        button2 = QPushButton("Log")
        button2.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        button3 = QPushButton("Transactions")
        button3.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        button4 = QPushButton("Restock")
        button4.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        button5 = QPushButton("Request Item")
        button5.clicked.connect(lambda: self.stack.setCurrentIndex(4))
    
        nav_layout.addWidget(button1)
        nav_layout.addWidget(button2)
        nav_layout.addWidget(button3)
        nav_layout.addWidget(button4)
        nav_layout.addWidget(button5)

        self.stack = QStackedWidget()
        self.stack.addWidget(central_widget)
        self.stack.addWidget(log_section)
        self.stack.addWidget(transaction_section)
        self.stack.addWidget(restock_section)
        self.stack.addWidget(request_section)

        container_widget = QWidget()
        container_layout = QHBoxLayout()
        container_widget.setLayout(container_layout)
        container_layout.addWidget(navigation_sideBar)
        container_layout.addWidget(self.stack)
        self.setCentralWidget(container_widget)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QDateEdit, QTableWidget, QTableWidgetItem, QMessageBox, QSpinBox, QDoubleSpinBox
from PySide6.QtCore import QDate
from logic.transactions import query_transaction_date

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
    def __init__(self, label):
        super().__init__()
        layout = QVBoxLayout(self)
        section_label = QLabel(label)
        
        # SKU Input 
        sku_input = QLineEdit()
        sku_label = QLabel("SKU:")
        sku_input.setPlaceholderText("Enter SKU")

        # Quantity Widget
        qty_input = QSpinBox()
        qty_input.setRange(0, 100)
        qty_input.setValue(1)
        qty_input.setMinimum(1)
        qty_input.setSingleStep(1)
        qty_label = QLabel("Quantity:")
        
        price_label = QLabel("Price:")
        price_input = QDoubleSpinBox()
        price_input.setRange(0.0, 1000000.0)
        price_input.setDecimals(1)
        price_input.setSingleStep(1)
        price_input.setPrefix("₱")
        price_input.setValue(0)

        button = QPushButton("Submit")

        input_layer = QWidget()
        input_layer_layout = QHBoxLayout(input_layer)
        input_layer_layout.addWidget(sku_label)
        input_layer_layout.addWidget(sku_input)
        input_layer_layout.addWidget(qty_label)
        input_layer_layout.addWidget(qty_input)

        layout.addWidget(section_label)
        layout.addWidget(input_layer)
        layout.addWidget(price_label)
        layout.addWidget(price_input)
        layout.addWidget(button)
    
class SearchSection(QWidget):
    def __init__(self, lineText, buttonText, label):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel(label)
        search_section = InputWidget(lineText, buttonText)

        layout.addWidget(label)
        layout.addWidget(search_section)

class transaction_table(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(["Date", "Part ID", "Part Name", "Quantity", "Amount Sold", "Type", "Revenue"])

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

        self.result_table = transaction_table()

        transaction_button = QPushButton("Submit")
        transaction_button.clicked.connect(self.handle_submit)

        layout.addWidget(label)
        layout.addWidget(self.date_input)
        layout.addWidget(transaction_button)
        layout.addWidget(self.result_table)

    def populate_table(self, results):
        self.result_table.setRowCount(0)
        self.result_table.setRowCount(len(results))

        for row_idx, row_data in enumerate(results):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                self.result_table.setItem(row_idx, col_idx, item)


    def handle_submit(self):
        date_string = self.date_input.date().toString("yyyy-MM-dd")

        try:
            results = query_transaction_date(date_string)
        except (RuntimeError, ValueError) as e:
            QMessageBox.critical(self, "Error Occured", str(e))
            return
        
        print(results)
        self.populate_table(results)


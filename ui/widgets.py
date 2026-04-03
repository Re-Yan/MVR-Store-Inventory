from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QDateEdit, QTableWidget, QTableWidgetItem, QMessageBox, QSpinBox, QDoubleSpinBox
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
        section_label = QLabel(label)
        form_layout = QFormLayout()

        # Input Widgets for QFormLayout
        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Enter SKU")
        self.qty_input = QSpinBox()
        self.price_input = QDoubleSpinBox()

        # Row Labels
        form_layout.addRow("SKU:", self.sku_input)
        form_layout.addRow("Quantity:", self.qty_input)
        form_layout.addRow("Price:", self.price_input)

        # Quantity Widget
        self.qty_input.setRange(0, 100)
        self.qty_input.setValue(1)
        self.qty_input.setMinimum(1)
        self.qty_input.setSingleStep(1)
        
        # Price Widget
        self.price_input.setRange(0.0, 1000000.0)
        self.price_input.setDecimals(1)
        self.price_input.setSingleStep(1)
        self.price_input.setPrefix("₱")
        self.price_input.setValue(0)

        # Submit Button
        self.button = QPushButton("Submit")
        form_layout.addRow(self.button)

        self.setLayout(form_layout)


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


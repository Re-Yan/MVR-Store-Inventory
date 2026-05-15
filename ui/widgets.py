from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QDateEdit, QTableWidget, QTableWidgetItem, QMessageBox, QSpinBox, QDoubleSpinBox, QListView
from PySide6.QtCore import QDate, QStringListModel, QTimer
from datetime import datetime
from logic.transactions import query_transaction_date, insert_transaction, search_suggestions
from logic.restock import get_current_batch, add_request_item, get_part_id_by_sku, query_request_item_table
import traceback

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
        form_layout = QFormLayout()
        section_label = QLabel(label)

        # Input Widgets for QFormLayout
        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Enter SKU")
        self.qty_input = QSpinBox()
        self.price_input = QDoubleSpinBox()

        # Row Labels
        form_layout.addRow(section_label)
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
        self.button.clicked.connect(self.handle_submit)
        form_layout.addRow(self.button)

        self.setLayout(form_layout)

    def handle_submit(self):
        sku = self.sku_input.text()
        quantity = self.qty_input.value()
        price = self.price_input.value()
        date = datetime.now()
        formatted_date = date.strftime("%Y-%m-%d")

        insert_transaction(formatted_date, quantity, sku, price)

class SearchSection(QWidget):
    def __init__(self, lineText, buttonText, label, on_selection=None):
        super().__init__()
        self.on_selection = on_selection
        layout = QVBoxLayout()
        self.setLayout(layout)
        label = QLabel(label)

        self.search_section = QLineEdit()
        self.search_section.setPlaceholderText(lineText)
        self.view = QListView()
        self.items = []
        self.model = QStringListModel()
        self.view.setModel(self.model)

        # Store the mapping from display text to SKU for selection
        self._display_to_sku = {}

        self.search_section.textChanged.connect(self.debounce_timer)
        self.view.clicked.connect(self.on_item_selected)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)

        self.timer.timeout.connect(self.on_text_changed)
 
        layout.addWidget(label)
        layout.addWidget(self.search_section)
        layout.addWidget(self.view)

    def on_text_changed(self):
        search_term = self.search_section.text()
        results = search_suggestions(search_term)
        
        # clear out previous results by emptying the list/dictionary
        self.items = []
        self._display_to_sku = {}
        
        for sku, part_name, alias_name in results:
            if alias_name:
                display_text = f"{sku} | {part_name} ({alias_name})"
            else:
                display_text = f"{sku} | {part_name}"
            self.items.append(display_text)
            self._display_to_sku[display_text] = sku

        print(self._display_to_sku)
        
        self.model.setStringList(self.items)

    def on_item_selected(self, index):
        selected_text = self.items[index.row()]
        sku = self._display_to_sku.get(selected_text)
        if sku and self.on_selection:
            self.on_selection(sku)

    def debounce_timer(self):
        self.timer.start(300)
        

class SectionTable(QTableWidget):
    def __init__(self, headers, parent=None):
        super().__init__()
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

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

        self.result_table = SectionTable(["Date", "Part ID", "Part Name", "Quantity", "Amount Sold", "Type", "Revenue"])

        transaction_button = QPushButton("Submit")
        transaction_button.clicked.connect(self.handle_submit)

        layout.addWidget(label)
        layout.addWidget(self.date_input)
        layout.addWidget(transaction_button)
        layout.addWidget(self.result_table)

    def populate_table(self, results):
        print(type(results))
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

class restock_page(QWidget):
    def __init__(self, label):
        super().__init__()
        form_layout = QFormLayout()
        # horizontal_layout = 
        section_label = QLabel(label)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Enter Item Code")
        self.qty_input = QSpinBox()
        self.submit_button = QPushButton("Submit")
        self.restock_table = SectionTable(["SKU", "Part Name", "Quantity", "Base Cost Price", "Total", "Restock Number"])
        self.finalize_button = QPushButton("Finalize Restock")

        form_layout.addRow(section_label)
        form_layout.addRow("SKU:", self.sku_input)
        form_layout.addRow("Quantity:", self.qty_input)
        form_layout.addRow(self.submit_button)
        form_layout.addRow(self.restock_table)
        form_layout.addRow(self.finalize_button)

        # Quantity Widget Settings
        self.qty_input.setRange(0, 100)
        self.qty_input.setValue(1)
        self.qty_input.setMinimum(1)
        self.qty_input.setSingleStep(1)

        self.setLayout(form_layout)

class request_page(QWidget):
    def __init__(self, label):
        super().__init__()

        form_layout = QFormLayout()
        section_label = QLabel(label)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Enter Item Code")
        self.qty_input = QSpinBox()
        self.input_button = QPushButton("Submit")
        self.input_button.clicked.connect(self.handle_submit)
        self.reset_table = QPushButton("Reset Table")
        self.request_table = SectionTable(["SKU", "Part Name", "Quantity", "Base Cost Price", "Total", "Restock Number", "Urgency"])

        button_container = QWidget()
        horizontal_layout = QHBoxLayout(button_container)
        horizontal_layout.addWidget(self.input_button)
        horizontal_layout.addWidget(self.reset_table)

        form_layout.addRow(section_label)
        form_layout.addRow("SKU:", self.sku_input)
        form_layout.addRow("Quantity:", self.qty_input)
        form_layout.addRow(button_container)
        form_layout.addRow(self.request_table)

        # Quantity Widget Settings
        self.qty_input.setRange(0, 100)
        self.qty_input.setValue(1)
        self.qty_input.setMinimum(1)
        self.qty_input.setSingleStep(1)

        self.setLayout(form_layout)

    def handle_submit(self):
        sku = self.sku_input.text().strip()
        quantity = self.qty_input.value()

        if not sku:
            QMessageBox.warning(self, "Input Error", "SKU cannot be empty.")
            return
        
        part_id = get_part_id_by_sku(sku)
        if part_id is None:
            QMessageBox.warning(self,"SKU Error", f"{sku} not found in the database.")
            return

        try:
            batch_id = get_current_batch()
        except (RuntimeError) as e:
            traceback.print_exc()
            QMessageBox.critical(self, "ERROR:", str(e))
            return

        try:
            add_request_item(batch_id, part_id, quantity, "PENDING", "")
            query_result = query_request_item_table()
        except (RuntimeError) as e:
            traceback.print_exc()
            QMessageBox.critical(self, "ERROR:", str(e))
        else:
            QMessageBox.information(self, "Item Submitted to DB", "Action Completed Successfully") 
        
        self.populate_request_item_table(query_result)
        
    def populate_request_item_table(self, query_result):
        print(type(query_result))
        self.request_table.setRowCount(0)
        self.request_table.setRowCount(len(query_result))

        for row_idx, row_data in enumerate(query_result):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                self.request_table.setItem(row_idx, col_idx, item)
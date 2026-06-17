from PySide6.QtWidgets import (
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout, 
    QFormLayout, 
    QLineEdit, 
    QPushButton, 
    QLabel, 
    QDateEdit, 
    QTableWidget, 
    QTableWidgetItem, 
    QMessageBox, 
    QSpinBox, 
    QDoubleSpinBox, 
    QListView, 
    QTreeWidget, 
    QTreeWidgetItem,
    QPlainTextEdit
)

from PySide6.QtCore import (
    Qt, 
    QDate, 
    QStringListModel, 
    QTimer 
)

from PySide6.QtGui import (
    QColor,
    QBrush
)

from datetime import datetime
from logic.transactions import ( 
    query_transaction_date, 
    insert_transaction, 
    search_suggestions 
)

from logic.restock import (
    fetch_most_recent_batch, 
    add_request_item, 
    get_part_id_by_sku, 
    query_request_item_table, 
    get_restock_batches 
)

import traceback

STATUS_COLORS = {
    "PENDING":      QColor("#b58900"),
    "PROCURED":     QColor("#2aa198"),
    "CARRIED OVER": QColor("#888888"),
}

# CLASSES

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

        self.setEditTriggers(self.EditTrigger.NoEditTriggers)

class restockTree(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(3)
        self.setHeaderLabels(["Batch/Item", "Created_On", "Status"])

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
    def __init__(self):
        super().__init__()

        main_layout = QHBoxLayout(self)

        self.left_panel = self.build_left_panel()
        self.right_panel = self.build_right_panel()

        main_layout.addWidget(self.left_panel, 1)
        main_layout.addWidget(self.right_panel, 2)
        self.refresh_item_table()

    def build_left_panel(self):
        panel = QWidget()
        left_layout = QFormLayout(panel)
        left_label = QLabel("ADD REQUEST")

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Enter Item Code")

        self.supplier_input = QLineEdit()
        self.supplier_input.setPlaceholderText("Enter Supplier Name")
        self.notes_input = QPlainTextEdit()
        self.notes_input.setPlaceholderText("Enter Notes (Optional)")
        # TO DO: Urgency Display
        add_button = QPushButton("Add +")
        # TO DO: error handling for blank supplier
        add_button.clicked.connect(self.handle_add_item)

        left_layout.addRow(left_label)
        left_layout.addRow("SKU", self.sku_input)
        left_layout.addRow("Supplier", self.supplier_input)
        left_layout.addRow("Notes", self.notes_input)
        left_layout.addRow(add_button)

        return panel


    def build_right_panel(self):
            panel = QWidget()
            right_layout = QVBoxLayout()
            self.batch_table = SectionTable(["Status", "Item Code", "Part Name", "Supplier", "Action"])
            
            right_layout.addWidget(self.build_header_batch())
            right_layout.addWidget(self.batch_table)
            panel.setLayout(right_layout)

            return panel
    
    def build_header_batch(self):
        header = QWidget()
        header_layout = QVBoxLayout(header)

        # ── meta line: which batch, created date, status ──
        self.batch_label   = QLabel("Batch —")
        self.batch_created = QLabel("created —")
        self.batch_status  = QLabel("status: —")

        meta_row = QHBoxLayout()
        meta_row.addWidget(self.batch_label)
        meta_row.addWidget(self.batch_created)
        meta_row.addWidget(self.batch_status)
        meta_row.addStretch()                       # keep labels left, soak up extra width

        # ── batch-level actions (inert in step 1) ──
        self.order_button    = QPushButton("Order Batch")
        self.complete_button = QPushButton("Complete Batch")
        self.order_button.setEnabled(False)
        self.complete_button.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self.order_button)
        button_row.addWidget(self.complete_button)
        button_row.addStretch()

        header_layout.addLayout(meta_row)
        header_layout.addLayout(button_row)

        return header
    
    def refresh_item_table(self):
        rows = query_request_item_table()       # (id, status, sku, part_name, supplier)
        self.populate_item_table(rows)

    def populate_item_table(self, rows):
        self.batch_table.setRowCount(0)
        self.batch_table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            item_id, status, sku, part_name, supplier = row[0], row[1], row[2], row[3], row[4]
            status_item = QTableWidgetItem(str(status))
            status_item.setForeground(QBrush(STATUS_COLORS.get(status, QColor("black"))))
            self.batch_table.setItem(r, 0, status_item)
            self.batch_table.setItem(r, 1, QTableWidgetItem(str(sku)))
            self.batch_table.setItem(r, 2, QTableWidgetItem(str(part_name)))
            self.batch_table.setItem(r, 3, QTableWidgetItem(str(supplier or "")))
            # Col 4 Action

    def add_item(self): 
        sku = self.sku_input.text().strip()            
        item_id = get_part_id_by_sku(sku)
        batch_id = fetch_most_recent_batch()
        supplier = self.supplier_input.text().strip()
        notes = self.notes_input.toPlainText().strip()

        add_request_item(batch_id, item_id, supplier, "PENDING", notes)

    def handle_add_item(self):

        self.add_item()
        self.refresh_item_table()
        

class request_page(QWidget):
    def __init__(self, label):
        super().__init__()

        form_layout = QFormLayout()
        section_label = QLabel(label)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Enter Item Code")
        self.tree = restockTree()
        self.input_button = QPushButton("Submit")
        self.input_button.clicked.connect(self.handle_submit)
        self.reset_table = QPushButton("Reset Table")
        

        button_container = QWidget()
        horizontal_layout = QHBoxLayout(button_container)
        horizontal_layout.addWidget(self.input_button)
        horizontal_layout.addWidget(self.reset_table)

        form_layout.addRow(section_label)
        form_layout.addRow("SKU:", self.sku_input)
        form_layout.addRow(button_container)
        form_layout.addRow(self.tree)

        self.refresh_restock_tree()
        self.setLayout(form_layout)



    def handle_submit(self):
        sku = self.sku_input.text().strip()

        if not sku:
            QMessageBox.warning(self, "Input Error", "SKU cannot be empty.")
            return
        
        part_id = get_part_id_by_sku(sku)
        if part_id is None:
            QMessageBox.warning(self,"SKU Error", f"{sku} not found in the database.")
            return

        try:
            batch_id = fetch_most_recent_batch()
        except (RuntimeError) as e:
            traceback.print_exc()
            QMessageBox.critical(self, "ERROR:", str(e))
            return

        try:
            add_request_item(batch_id, part_id, "PENDING", "")
            self.refresh_restock_tree()
            
        except (RuntimeError) as e:
            traceback.print_exc()
            QMessageBox.critical(self, "ERROR:", str(e))
        else:
            QMessageBox.information(self, "Item Submitted to DB", "Action Completed Successfully") 

    def refresh_restock_tree(self):
        batch_and_item_group = get_restock_batches()
        self.populate_tree(batch_and_item_group)

    def populate_tree(self, group):
        self.tree.clear()
        for batch_tuple, items in group:                 # outer loop: batches
    
            batch_id, created_on, status = batch_tuple
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, f"Batch #{batch_id}")
            parent.setText(1, created_on)
            parent.setText(2, status)
            parent.setData(0, Qt.UserRole, batch_id)

            for item in items:                             # inner loop: children
                item_id, sku, part_name, item_created = item
                child = QTreeWidgetItem(parent)
                child.setText(0, sku)
                child.setText(1, part_name)
                child.setData(0, Qt.UserRole, item_id)
        
        
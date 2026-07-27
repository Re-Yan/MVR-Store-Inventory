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
    QPlainTextEdit,
    QComboBox,
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QInputDialog
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
    add_request_item, 
    get_part_id_by_sku, 
    get_request_items,
    get_suppliers,
    get_or_create_supplier,
    delete_request_items,
    get_suppliers_with_counts,
    rename_supplier,
    delete_supplier
)

from logic.restock_transitions import (
    mark_items_ordered,
    mark_items_received,
    revert_items_to_pending
)

import sqlite3
import traceback

STATUS_COLORS = {
    "PENDING":     QColor("#b58900"),
    "ORDERED":     QColor("#2aa198"),
    "RECEIVED":    QColor("#888888"),
}

FILTER_MAP = {
    "Active":   ["PENDING", "ORDERED"],
    "All":      None,
    "PENDING":  ["PENDING"],
    "ORDERED":  ["ORDERED"],
    "RECEIVED": ["RECEIVED"],
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
        form_layout.addRow("Total Price:", self.price_input)

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
        sku = self.sku_input.text().strip()
        
        if not sku:
            QMessageBox.warning(self, "Missing Input", "Please Enter SKU")
            return
        quantity = self.qty_input.value()
        price = self.price_input.value()
        date = datetime.now().strftime("%Y-%m-%d")

        try:
            splits = insert_transaction(date, quantity, sku, price)
        except ValueError as e:
            QMessageBox.warning(self, "Sale Blocked", str(e))
            return
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", str(e))
            return

        detail = ", ".join(f"{qty} @ ₱{cost}" for qty, cost in splits)
        QMessageBox.information(self, "Sale Recorded", f"Sold {quantity} × {sku}\nCost basis: {detail}")
        self.sku_input.clear()
        self.qty_input.setValue(1)
        self.price_input.setValue(0)

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

class OrderDetailsDialog(QDialog):
    """Collects the supplier for the order plus quantity and unit cost per item."""
    def __init__(self, items, parent=None):
        # items: list of (item_id, part_name)
        super().__init__(parent)
        self.setWindowTitle("Order Details")
        layout = QFormLayout(self)
        self.inputs = {}   # item_id -> (qty_spin, cost_spin)

        # One supplier applies to the whole order.
        self.supplier_input = QComboBox()
        self.supplier_input.setEditable(True)
        self.supplier_input.setPlaceholderText("Select or Type Supplier")
        self.supplier_input.addItems([name for _id, name in get_suppliers()])
        self.supplier_input.setCurrentText("")
        layout.addRow("Supplier:", self.supplier_input)

        for item_id, part_name in items:
            qty_spin = QSpinBox()
            qty_spin.setRange(1, 100000)
            cost_spin = QSpinBox()
            cost_spin.setRange(1, 1000000)
            cost_spin.setPrefix("₱")
            layout.addRow(QLabel(part_name))
            layout.addRow("Quantity:", qty_spin)
            layout.addRow("Unit Cost:", cost_spin)
            self.inputs[item_id] = (qty_spin, cost_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_supplier_name(self):
        return self.supplier_input.currentText().strip()

    def get_order_data(self):
        return [
            (item_id, qty.value(), cost.value())
            for item_id, (qty, cost) in self.inputs.items()
        ]


class SupplierManagerDialog(QDialog):
    """Lists suppliers with usage counts; allows rename, and delete when unused."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Suppliers")
        layout = QVBoxLayout(self)

        self.table = SectionTable(["Supplier", "Used By"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.sync_buttons)

        button_bar = QHBoxLayout()
        self.rename_button = QPushButton("Rename")
        self.rename_button.clicked.connect(self.handle_rename)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.handle_delete)
        button_bar.addStretch()
        button_bar.addWidget(self.rename_button)
        button_bar.addWidget(self.delete_button)

        layout.addWidget(self.table)
        layout.addLayout(button_bar)
        self.reload()

    def reload(self):
        rows = get_suppliers_with_counts()
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        for r, (supplier_id, name, order_refs, batch_refs) in enumerate(rows):
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.UserRole, supplier_id)
            refs = order_refs + batch_refs
            usage = f"{order_refs} order(s), {batch_refs} batch(es)" if refs else "unused"
            usage_item = QTableWidgetItem(usage)
            usage_item.setData(Qt.UserRole, refs)
            self.table.setItem(r, 0, name_item)
            self.table.setItem(r, 1, usage_item)
        self.sync_buttons()

    def selected_supplier(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        return (self.table.item(row, 0).data(Qt.UserRole),   # id
                self.table.item(row, 0).text(),              # name
                self.table.item(row, 1).data(Qt.UserRole))   # ref count

    def sync_buttons(self):
        picked = self.selected_supplier()
        self.rename_button.setEnabled(picked is not None)
        self.delete_button.setEnabled(picked is not None and picked[2] == 0)

    def handle_rename(self):
        picked = self.selected_supplier()
        if not picked:
            return
        supplier_id, old_name, _refs = picked
        new_name, ok = QInputDialog.getText(
            self, "Rename Supplier", "New name:", text=old_name
        )
        if not ok or new_name.strip() == old_name:
            return
        try:
            rename_supplier(supplier_id, new_name)
        except ValueError as e:
            QMessageBox.warning(self, "Cannot Rename", str(e))
            return
        self.reload()

    def handle_delete(self):
        picked = self.selected_supplier()
        if not picked:
            return
        supplier_id, name, _refs = picked
        if QMessageBox.question(
            self, "Confirm Delete", f"Delete supplier '{name}'?"
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_supplier(supplier_id)
        except ValueError as e:
            QMessageBox.warning(self, "Cannot Delete", str(e))
            return
        self.reload()


class restock_page(QWidget):
    def __init__(self):
        super().__init__()

        main_layout = QHBoxLayout(self)

        self.left_panel = self.build_left_panel()
        self.right_panel = self.build_right_panel()

        main_layout.addWidget(self.left_panel, 1)
        main_layout.addWidget(self.right_panel, 2)
        self.reload()

    def build_left_panel(self):
        panel = QWidget()
        left_layout = QFormLayout(panel)
        left_label = QLabel("ADD REQUEST")

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Enter Item Code")

        self.notes_input = QPlainTextEdit()
        self.notes_input.setPlaceholderText("Enter Notes (Optional)")
        self.add_button = QPushButton("Add +")
        self.add_button.clicked.connect(self.handle_add_item)

        left_layout.addRow(left_label)
        left_layout.addRow("SKU", self.sku_input)
        left_layout.addRow("Notes", self.notes_input)
        left_layout.addRow(self.add_button)

        return panel


    def build_right_panel(self):
            panel = QWidget()
            layout = QVBoxLayout(panel)
            
            control_bar = QHBoxLayout()

            self.filter_combo = QComboBox()
            self.filter_combo.addItems(["Active", "All", "PENDING", "ORDERED", "RECEIVED"])
            self.filter_combo.currentTextChanged.connect(self.reload) # create self.refresh function
            
            self.order_button = QPushButton("Mark Ordered")
            self.order_button.clicked.connect(self.handle_mark_ordered)
            self.receive_button = QPushButton("Mark Received")
            self.receive_button.clicked.connect(self.handle_mark_received)
            self.revert_button = QPushButton("Revert to Pending")
            self.revert_button.clicked.connect(self.handle_revert)
            self.delete_button = QPushButton("Delete")
            self.delete_button.clicked.connect(self.handle_delete)

            self.suppliers_button = QPushButton("Suppliers…")
            self.suppliers_button.clicked.connect(self.handle_manage_suppliers)

            control_bar.addWidget(QLabel("Filter:"))
            control_bar.addWidget(self.filter_combo)
            control_bar.addWidget(self.suppliers_button)
            control_bar.addStretch()
            control_bar.addWidget(self.order_button)
            control_bar.addWidget(self.receive_button)
            control_bar.addWidget(self.revert_button)
            control_bar.addWidget(self.delete_button)

            self.item_table = SectionTable(["Status", "Item Code", "Part Name", "Supplier", "Qty", "Unit Cost", "Requested", "Ordered", "Received"])
            self.item_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.item_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) # question about selection methods
            self.item_table.itemSelectionChanged.connect(self.sync_action_buttons)

            self.sync_action_buttons() # Disables the wrong button on startup

            layout.addLayout(control_bar)
            layout.addWidget(self.item_table)
            return panel
    
    def reload(self, _text=None):
            statuses = FILTER_MAP[self.filter_combo.currentText()]
            rows = get_request_items(statuses)
            self.populate_item_table(rows)

    def populate_item_table(self, rows):
        self.item_table.setRowCount(0)
        self.item_table.setRowCount(len(rows))
        
        for r, row in enumerate(rows):
            item_id, status, sku, part_name, supplier, quantity, unit_cost, requested, ordered, received = row
            status_item = QTableWidgetItem(str(status))
            status_item.setForeground(QBrush(STATUS_COLORS.get(status, QColor("black"))))
            status_item.setData(Qt.UserRole, item_id)        # id lives on the row for Step 5
            self.item_table.setItem(r, 0, status_item)
            self.item_table.setItem(r, 1, QTableWidgetItem(str(sku)))
            self.item_table.setItem(r, 2, QTableWidgetItem(str(part_name)))
            self.item_table.setItem(r, 3, QTableWidgetItem(str(supplier or "")))
            self.item_table.setItem(r, 4, QTableWidgetItem(str(quantity if quantity is not None else "")))
            self.item_table.setItem(r, 5, QTableWidgetItem(f"₱{unit_cost}" if  unit_cost is not None else ""))
            self.item_table.setItem(r, 6, QTableWidgetItem(str(requested or "")))
            self.item_table.setItem(r, 7, QTableWidgetItem(str(ordered or "")))
            self.item_table.setItem(r, 8, QTableWidgetItem(str(received or "")))

    def sync_action_buttons(self):
        selected = self.item_table.selectionModel().selectedRows()
        if not selected:
            self.order_button.setEnabled(False)
            self.receive_button.setEnabled(False)
            self.revert_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            return
        statuses = {self.item_table.item(idx.row(), 0).text() for idx in selected}
        self.order_button.setEnabled(statuses == {"PENDING"})
        self.receive_button.setEnabled(statuses == {"ORDERED"})
        self.revert_button.setEnabled(statuses == {"ORDERED"})
        self.delete_button.setEnabled(statuses == {"PENDING"})

    def add_item(self, item_id):
        notes = self.notes_input.toPlainText().strip()
        add_request_item(item_id, notes)

    def handle_add_item(self):
        sku = self.sku_input.text().strip()            

        # Error Handling for null sku
        if not sku:
            QMessageBox.warning(self, "Missing Input", "Please Enter Item Code")
            return

        item_id = get_part_id_by_sku(sku)

        # Error Handling For Wrong Item Code
        if not item_id:
            QMessageBox.warning(self, "UNKNOWN SKU", "NON-EXISTENT ITEM CODE")
            return
        
        self.add_item(item_id)
        self.reload()

    def selected_item_ids(self):
        ids = []
        for index in self.item_table.selectionModel().selectedRows():
            cell = self.item_table.item(index.row(), 0)   # col 0 holds the id
            ids.append(cell.data(Qt.ItemDataRole.UserRole))
        return ids

    def handle_mark_ordered(self):
        selected = self.item_table.selectionModel().selectedRows()
        if not selected:
            return
        items = [
            (self.item_table.item(idx.row(), 0).data(Qt.ItemDataRole.UserRole),
            self.item_table.item(idx.row(), 2).text())
            for idx in selected
        ]
        dialog = OrderDetailsDialog(items, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        supplier_name = dialog.get_supplier_name()
        if not supplier_name:
            QMessageBox.warning(self, "Missing Input", "Please Provide Supplier Name")
            return
        supplier_id = get_or_create_supplier(supplier_name)

        try:
            mark_items_ordered(dialog.get_order_data(), supplier_id)
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Order", str(e))
            return
        self.reload()

    def handle_mark_received(self):
        selected = self.item_table.selectionModel().selectedRows()
        if not selected:
            return
        lines = [
            f"{self.item_table.item(idx.row(), 2).text()}: "
            f"{self.item_table.item(idx.row(), 4).text()} @ {self.item_table.item(idx.row(), 5).text()}"
            for idx in selected
        ]
        if QMessageBox.question(
            self, "Confirm Receipt",
            "Add to inventory?\n\n" + "\n".join(lines)
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            mark_items_received(self.selected_item_ids())
        except ValueError as e:
            QMessageBox.warning(self, "Cannot Receive", str(e))
            return
        self.reload()

    def handle_revert(self):
        selected = self.item_table.selectionModel().selectedRows()
        if not selected:
            return
        lines = [self.item_table.item(idx.row(), 2).text() for idx in selected]
        if QMessageBox.question(
            self, "Confirm Revert",
            "Revert these items to PENDING? Supplier, quantity and unit_cost "
            "will be cleared: \n\n" + "\n".join(lines)
        ) != QMessageBox.StandardButton.Yes:
            return
        revert_items_to_pending(self.selected_item_ids())
        self.reload()

    def handle_delete(self):
        selected = self.item_table.selectionModel().selectedRows()
        if not selected:
            return
        lines = [self.item_table.item(idx.row(), 2).text() for idx in selected]
        if QMessageBox.question(
            self, "Confirm Delete",
            "Delete these requests?\n\n" + "\n".join(lines)
        ) != QMessageBox.StandardButton.Yes:
            return
        delete_request_items(self.selected_item_ids())
        self.reload()

    def handle_manage_suppliers(self):
        SupplierManagerDialog(self).exec()
        self.reload()   # renames may have changed names shown in the item table
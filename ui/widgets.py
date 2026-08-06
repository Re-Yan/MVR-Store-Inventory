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
    QListView,
    QPlainTextEdit,
    QComboBox,
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QCompleter
)

from PySide6.QtCore import (
    Qt,
    QDate, 
    QStringListModel, 
    QTimer 
)

from PySide6.QtGui import (
    QColor,
    QBrush,
    QShortcut,
    QKeySequence
)

from logic.transactions import (
    get_sales_for_date,
    get_part_snapshot,
    record_sale,
    search_suggestions,
    void_sale
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

STATUS_COLORS = {
    "PENDING":     QColor("#b58900"),
    "ORDERED":     QColor("#2aa198"),
    "RECEIVED":    QColor("#888888"),
    "ACTIVE":      QColor("#2aa198"),
    "VOIDED":      QColor("#888888"),
}
NOTE_TEXT_COLOR = QColor("#e67e22")

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
        self.snapshot = None
        self.snapshot_sku = None    # which SKU self.snapshot describes
        self._display_to_sku = {}

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.build_entry_panel(label), 1)
        main_layout.addWidget(self.build_sales_panel(), 2)

        self.date_input.dateChanged.connect(self.reload)
        self.reload()

    def build_entry_panel(self, label):
        panel = QWidget()
        layout = QFormLayout(panel)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("SKU, part name, or alias")

        # Inline suggestions, fed by the same search the Search page uses.
        self.completer_model = QStringListModel(self)
        self.completer = QCompleter(self)
        self.completer.setModel(self.completer_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer.activated.connect(self.on_suggestion_picked)
        self.sku_input.setCompleter(self.completer)

        self.lookup_timer = QTimer(self)
        self.lookup_timer.setSingleShot(True)
        self.lookup_timer.timeout.connect(self.refresh_part_context)
        self.sku_input.textChanged.connect(lambda: self.lookup_timer.start(250))

        self.part_label = QLabel("—")
        self.part_label.setWordWrap(True)

        self.qty_input = QSpinBox()
        self.qty_input.setRange(1, 100000)
        self.qty_input.valueChanged.connect(self.autofill_price)

        self.price_input = QSpinBox()          # pesos are integers in the schema
        self.price_input.setRange(0, 10000000)
        self.price_input.setPrefix("₱")
        self.price_input.setGroupSeparatorShown(True)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Optional")

        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setCalendarPopup(True)

        self.submit_button = QPushButton("Log Sale")
        self.submit_button.clicked.connect(self.handle_submit)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        layout.addRow(QLabel(label))
        layout.addRow("SKU:", self.sku_input)
        layout.addRow(self.part_label)
        layout.addRow("Quantity:", self.qty_input)
        layout.addRow("Total:", self.price_input)
        layout.addRow("Notes:", self.notes_input)
        layout.addRow("Sale date:", self.date_input)
        layout.addRow(self.submit_button)
        layout.addRow(self.status_label)

        # Keyboard flow: SKU -> qty -> price -> submit
        self.sku_input.returnPressed.connect(self.focus_qty)
        self.qty_input.lineEdit().returnPressed.connect(self.focus_price)
        self.price_input.lineEdit().returnPressed.connect(self.handle_submit)
        submit_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        submit_shortcut.activated.connect(self.handle_submit)

        return panel

    def build_sales_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        bar = QHBoxLayout()
        self.day_total_label = QLabel("")
        self.void_button = QPushButton("Void Sale")
        self.void_button.clicked.connect(self.handle_void)
        bar.addWidget(self.day_total_label)
        bar.addStretch()
        bar.addWidget(self.void_button)

        self.sales_table = SalesTable()
        self.sales_table.itemSelectionChanged.connect(self.sync_void_button)

        layout.addLayout(bar)
        layout.addWidget(self.sales_table)
        self.sync_void_button()
        return panel

    def reload(self):
        sale_date = self.date_input.date().toString("yyyy-MM-dd")
        try:
            rows = get_sales_for_date(sale_date)
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", str(e))
            return

        self.sales_table.populate(rows)
        self.sync_void_button()

        active = [r for r in rows if r[7] == "ACTIVE"]
        voided = len(rows) - len(active)
        self.day_total_label.setText(
            f"{sale_date}:  {len(active)} sale(s),  ₱{sum(r[5] for r in active)}"
            + (f"   ({voided} voided)" if voided else "")
        )

    def sync_void_button(self):
        picked = self.sales_table.selected_sale()
        self.void_button.setEnabled(picked is not None and picked[1] == "ACTIVE")

    def handle_void(self):
        picked = self.sales_table.selected_sale()
        if not picked:
            return
        sale_id, _status = picked
        # Same row source as selected_sale(), so the two can never disagree.
        row = self.sales_table.selectionModel().selectedRows()[0].row()
        detail = (f"{self.sales_table.item(row, 3).text()} × "
                  f"{self.sales_table.item(row, 1).text()} "
                  f"({self.sales_table.item(row, 2).text()}) "
                  f"for {self.sales_table.item(row, 4).text()}")

        if QMessageBox.question(
            self, "Confirm Void",
            f"Void this sale?\n\n{detail}\n\n"
            "Stock returns to the batches it came from. "
            "The record is kept and marked VOIDED."
        ) != QMessageBox.StandardButton.Yes:
            return

        try:
            void_sale(sale_id)
        except ValueError as e:
            QMessageBox.warning(self, "Cannot Void", str(e))
            return
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", str(e))
            return

        self.status_label.setText(f"Voided sale #{sale_id} — stock returned")
        self.status_label.setStyleSheet("color: #888888;")
        self.reload()

    def refresh_part_context(self):
        """Debounced: refill the suggestion list and the part context card."""
        text = self.sku_input.text().strip()
        if not text:
            self.snapshot = None
            self.snapshot_sku = None
            self.part_label.setText("—")
            self.completer_model.setStringList([])
            return

        self._display_to_sku = {}
        labels = []
        for sku, part_name, alias in search_suggestions(text):
            label = f"{sku} | {part_name}" + (f" ({alias})" if alias else "")
            labels.append(label)
            self._display_to_sku[label] = sku
        self.completer_model.setStringList(labels)

        # The context card only fills once the text is an exact SKU.
        self.snapshot = get_part_snapshot(text)
        self.snapshot_sku = text if self.snapshot else None
        if self.snapshot is None:
            self.part_label.setText("no exact SKU match yet")
            self.part_label.setStyleSheet("color: #888888;")
            return

        warn = self.snapshot["stock_warning"]
        low = warn is not None and self.snapshot["available"] <= warn
        self.part_label.setText(
            f"{self.snapshot['part_name']}\n"
            f"{self.snapshot['available']} available   |   SRP ₱{self.snapshot['srp_price']}"
        )
        self.part_label.setStyleSheet(f"color: {'#b58900' if low else '#2aa198'};")
        self.autofill_price()

    def on_suggestion_picked(self, display_text):
        sku = self._display_to_sku.get(display_text)
        if sku:
            # Deferred so the completer finishes writing its own text first.
            QTimer.singleShot(0, lambda: self.apply_sku(sku))

    def apply_sku(self, sku):
        self.sku_input.setText(sku)     # collapse the label to the bare SKU
        self.refresh_part_context()
        self.focus_qty()

    def autofill_price(self):
        """Total defaults to qty x SRP; typing over it always wins."""
        if self.snapshot and self.snapshot["srp_price"]:
            self.price_input.setValue(self.qty_input.value() * self.snapshot["srp_price"])

    def focus_qty(self):
        self.qty_input.setFocus()
        self.qty_input.selectAll()

    def focus_price(self):
        self.price_input.setFocus()
        self.price_input.selectAll()

    def handle_submit(self):
        sku = self.sku_input.text().strip()
        if not sku:
            QMessageBox.warning(self, "Missing Input", "Please enter a SKU")
            return

        quantity = self.qty_input.value()
        price = self.price_input.value()
        notes = self.notes_input.text().strip()
        sale_date = self.date_input.date().toString("yyyy-MM-dd")

        try:
            result = record_sale(sale_date, sku, quantity, price, notes)
        except ValueError as e:
            QMessageBox.warning(self, "Sale Blocked", str(e))
            return
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", str(e))
            return

        self.show_success(sku, quantity, price, result)
        self.reset_form()
        self.reload()

    def show_success(self, sku, quantity, price, result):
        parts = [f"✓ {quantity} × {sku} — ₱{price}"]
        if len(result["splits"]) > 1:
            basis = ", ".join(f"{q} @ ₱{c}" for q, c in result["splits"])
            parts.append(f"{len(result['splits'])} batches ({basis})")

        remaining = result["remaining_stock"]
        # Only trust the threshold if the snapshot describes the SKU just sold --
        # a fast typist can submit before the debounced lookup catches up.
        fresh = self.snapshot if self.snapshot_sku == sku else None
        warn = fresh["stock_warning"] if fresh else None
        low = warn is not None and remaining <= warn
        parts.append(f"{remaining} left" + (" ⚠ LOW" if low else ""))

        self.status_label.setText("   |   ".join(parts))
        self.status_label.setStyleSheet(f"color: {'#b58900' if low else '#2aa198'};")

    def reset_form(self):
        self.sku_input.clear()
        self.qty_input.setValue(1)
        self.price_input.setValue(0)
        self.notes_input.clear()
        self.snapshot = None
        self.snapshot_sku = None
        self.part_label.setText("—")
        self.sku_input.setFocus()   # ready for the next entry

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

class SalesTable(SectionTable):
    """One row per sale. Column 6 carries the sale_id for row actions."""
    HEADERS = ["Time", "Item Code", "Part Name", "Qty", "Total", "Revenue", "Status"]

    def __init__(self, parent=None):
        super().__init__(self.HEADERS, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)

    def populate(self, rows):
        self.setRowCount(0)
        self.setRowCount(len(rows))

        for r, row in enumerate(rows):
            (sale_id, logged_on, sku, part_name, quantity, total_price,
             revenue, status, line_count, notes) = row

            sku_item = QTableWidgetItem(str(sku))
            if notes:
                sku_item.setToolTip(notes)
                sku_item.setForeground(NOTE_TEXT_COLOR)

            status_item = QTableWidgetItem(str(status))
            status_item.setForeground(QBrush(STATUS_COLORS.get(status, QColor("black"))))
            status_item.setData(Qt.ItemDataRole.UserRole, sale_id)

            qty_text = f"{quantity} ({line_count} batches)" if line_count > 1 else str(quantity)
            time_text = logged_on.split(" ")[1] if " " in logged_on else logged_on

            self.setItem(r, 0, QTableWidgetItem(time_text))
            self.setItem(r, 1, sku_item)
            self.setItem(r, 2, QTableWidgetItem(str(part_name)))            
            self.setItem(r, 3, QTableWidgetItem(qty_text))
            self.setItem(r, 4, QTableWidgetItem(f"₱{total_price}"))
            self.setItem(r, 5, QTableWidgetItem(f"₱{revenue}"))
            self.setItem(r, 6, status_item)

    def selected_sale(self):
        """(sale_id, status) for the selected row, or None."""
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        cell = self.item(selected[0].row(), 6)
        return (cell.data(Qt.ItemDataRole.UserRole), cell.text())


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

        self.result_table = SalesTable()

        transaction_button = QPushButton("Submit")
        transaction_button.clicked.connect(self.handle_submit)

        layout.addWidget(label)
        layout.addWidget(self.date_input)
        layout.addWidget(transaction_button)
        layout.addWidget(self.result_table)

    def handle_submit(self):
        date_string = self.date_input.date().toString("yyyy-MM-dd")

        try:
            results = get_sales_for_date(date_string)
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", str(e))
            return

        self.result_table.populate(results)

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
        self.sku_input.returnPressed.connect(self.handle_add_item)

        self.notes_input = QPlainTextEdit()
        self.notes_input.setPlaceholderText("Enter Notes (Optional)")
        notes_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.notes_input)
        notes_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        notes_shortcut.activated.connect(self.handle_add_item)

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
            item_id, status, sku, part_name, supplier, quantity, unit_cost, requested, ordered, received, notes = row
            status_item = QTableWidgetItem(str(status))
            status_item.setForeground(QBrush(STATUS_COLORS.get(status, QColor("black"))))
            status_item.setData(Qt.UserRole, item_id)        # id lives on the row for Step 5
            self.item_table.setItem(r, 0, status_item)

            sku_item = QTableWidgetItem(str(sku))
            if notes:
                sku_item.setToolTip(notes)
                sku_item.setForeground(NOTE_TEXT_COLOR)
            self.item_table.setItem(r, 1, sku_item)

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
        self.sku_input.clear()
        self.sku_input.setFocus() # sets the focus back to SKU input for rapid entries
        self.notes_input.clear()
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
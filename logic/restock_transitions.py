from datetime import datetime
from logic.db_connection import get_connection

def mark_items_ordered(items, supplier_id):
    if not items:
        return
    if not supplier_id:
        raise ValueError("Supplier ID is currently empty")
    for item_id, quantity, unit_cost in items:
        if not quantity or quantity < 1:
            raise ValueError(f"Item {item_id}: quantity must be at least 1")
        if not unit_cost or unit_cost <= 0:
            raise ValueError(f"Item {item_id}: unit cost must be greater than 0")
    
    date = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        conn.executemany("""
            UPDATE request_items
            SET supplier_id = ?, status = 'ORDERED', ordered_on = ?, quantity = ?, unit_cost = ?
            WHERE id = ? AND status = 'PENDING'
        """, [(supplier_id, date, qty, cost, item_id) for item_id, qty, cost in items])

def mark_items_received(item_ids):
    if not item_ids:
        return
    date = datetime.now().strftime("%Y-%m-%d")
    placeholders = ",".join("?" for _ in item_ids)

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT id, part_id, supplier_id, quantity, unit_cost
            FROM request_items
            WHERE id IN ({placeholders}) AND status = 'ORDERED'
        """, item_ids)
        rows = cursor.fetchall()

        for item_id, part_id, supplier_id, quantity, unit_cost in rows:
            if quantity is None or unit_cost is None or supplier_id is None:
                raise ValueError(f"Request item {item_id} has no quantity/cost/supplier recorded")

            cursor.execute("""
                INSERT INTO stock_batches
                    (part_id, supplier_id, request_item_id, qty_received, qty_remaining, unit_cost, received_on)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (part_id, supplier_id, item_id, quantity, quantity, unit_cost, date))

            cursor.execute("""
                UPDATE parts SET current_stock = current_stock + ?
                WHERE id = ?
            """, (quantity, part_id))

            cursor.execute("""
                UPDATE request_items SET status = 'RECEIVED', received_on = ?
                WHERE id = ?
            """, (date, item_id))
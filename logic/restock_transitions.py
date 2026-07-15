import os
import sqlite3
from datetime import datetime

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def mark_items_ordered(items):
    if not items:
        return
    for item_id, quantity, unit_cost in items:
        if not quantity or quantity < 1:
            raise ValueError(f"Item {item_id}: quantity must be at least 1")
        if not unit_cost or unit_cost <= 0:
            raise ValueError(f"Item {item_id}: unit cost must be greater than 0")
    
    date = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DB) as conn:
        conn.executemany("""
            UPDATE request_items
            SET status = 'ORDERED', ordered_on = ?, quantity = ?, unit_cost = ?
            WHERE id = ? AND status = 'PENDING'
        """, [(date, qty, cost, item_id) for item_id, qty, cost in items])

def mark_items_received(item_ids):
    if not item_ids:
        return
    placeholders = ",".join("?" for _ in item_ids)
    query = f"""
        UPDATE request_items
        SET 
            status = 'RECEIVED', 
            received_on = ?
        WHERE id IN ({placeholders}) AND status = 'ORDERED'
    """
    date = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DB) as conn:
        conn.execute(query, (date, *item_ids))
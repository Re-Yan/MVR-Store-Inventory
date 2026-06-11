import os
import sqlite3
from restock import fetch_most_recent_batch

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def mark_batch_ordered(id, date):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        batch_order_update = """
        UPDATE restock_batches
        SET status = 'ORDERED', ordered_on = ?
        WHERE id = ? AND status = 'OPEN'
        """

        cursor.execute(batch_order_update, (date, id,))

def mark_batch_completed():
    pass

def mark_item_procured(part_id):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        item_procured_update = """
        UPDATE request_items
        SET status = 'PROCURED'
        WHERE part_id = ? AND status = 'PENDING'
        """

        cursor.execute(item_procured_update, (part_id,))

def mark_item_carried_over():
    pass
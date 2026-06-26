import os
import sqlite3
from datetime import datetime

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def mark_items_ordered(item_ids):
    if not item_ids:
        return
    placeholders = ",".join("?" for _ in item_ids)
    query = f"""
        UPDATE request_items
        SET 
            status = 'ORDERED', 
            ordered_on = ?
        WHERE id IN ({placeholders}) AND status = 'PENDING'
    """
    date = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DB) as conn:
        conn.execute(query, (date, *item_ids))

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
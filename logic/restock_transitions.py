import os
import sqlite3
from restock import fetch_most_recent_batch

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def mark_batch_ordered(id, date):
    pass

def mark_batch_completed():
    pass

def mark_item_procured():
    pass

def mark_item_carried_over():
    pass
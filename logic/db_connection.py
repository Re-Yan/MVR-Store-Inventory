import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def get_connection():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

from PySide6.QtWidgets import QMessageBox
import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def search_transaction_date(date):
    date_string = date.toString("yyyy-MM-dd")
    print(f"Date Output: {date_string}")

    return date_string

def query_transaction_date(date_string, parent=None):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    # results = []
    try:
        cursor.execute("""
            SELECT
                t.timestamp,
                p.part_name,
                t.quantity,
                t.transaction_type,
                t.part_id,
                t.sale_at_time
            FROM transactions t
            INNER JOIN parts p ON t.part_id = p.sku
            WHERE t.timestamp LIKE ?
                    """, 
            (f"{date_string}%",),
        )
        results = cursor.fetchall()
    except sqlite3.Error as e:
        QMessageBox.critical(parent, "Database Error", f"An Error Has Occured: {e}")
    finally:
        conn.close()
        print(results)
        return results
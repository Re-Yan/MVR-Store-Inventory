import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def query_transaction_date(date_string, parent=None):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    
    query = """
            SELECT
                t.timestamp,
                t.part_id,
                p.part_name,
                t.quantity,
                t.sale_at_time,
                t.transaction_type
            FROM transactions t
            INNER JOIN parts p ON t.part_id = p.sku
            WHERE t.timestamp LIKE ?
        """

    try:
        with sqlite3.connect(DB) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (f"{date_string}%",))
            results = cursor.fetchall()

            if not results:
                raise ValueError(f"No transactions found for date: {date_string}")
        
        return results
    except sqlite3.Error as e:
        raise RuntimeError(f"Database Query failed: {e}") from e
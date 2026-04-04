import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def query_transaction_date(date_string, parent=None):
    
    query = """
            SELECT
                t.timestamp,
                t.part_id,
                p.part_name,
                t.quantity,
                t.sale_at_time,
                t.transaction_type,
                t.revenue
            FROM v_transactions_with_revenue t
            INNER JOIN parts p ON t.part_id = p.sku
            WHERE t.timestamp LIKE ?
            ORDER BY t.id DESC
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

def insert_transaction(date, quantity, sku, price):
    select_query = """
        SELECT
            p.part_name,
            p.base_cost_price
        FROM parts p
        WHERE sku = ?
        """

    insert_query = """
        INSERT INTO transactions (id, timestamp, quantity, part_id, transaction_type, cost_at_time, sale_at_time, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        
        # try and except clause for the select query
        try:
            cursor.execute(select_query, (sku,))
            select_result = cursor.fetchone()
            
            if select_result  is None:
                raise ValueError(f"ERROR: {sku} Not Found in Parts Table")
            
            part_name, cost_price = select_result

        except sqlite3.Error as e:
            print(f"Part ID Lookup Failed: - {e}")
            return

        # try and except clause for the insert query
        try:
            cursor.execute(insert_query, (
                None,   # id should be NONE as this column is AUTOINCREMENT
                date,
                quantity,
                sku,
                "SALE",  # any transaction logged is of type SALE
                cost_price,
                price,
                "",  # Notes will remain empty for now
            ))
            conn.commit()
            print(f"Transaction Recorded")

        except sqlite3.Error as e:
            print(f"ERROR: Failed to Insert Transaction - {e}")
            return
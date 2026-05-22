import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def search_suggestions(search_term):
    """
    Search for parts by SKU, part name, or alias name.
    Returns a list of tuples: (sku, part_name, alias_name or None)
    Prioritizes exact/prefix matches over substring matches.
    """
    if not search_term or not search_term.strip():
        return []
    
    search_term = search_term.strip()
    try:
        with sqlite3.connect(DB) as conn:
            cursor = conn.cursor()
            
            # Query 1: Exact or prefix match on SKU (highest priority)
            cursor.execute("""
                SELECT DISTINCT p.sku, p.part_name, NULL as alias_name, 1 as priority
                FROM parts p
                WHERE p.sku LIKE ? OR p.sku LIKE ?
                ORDER BY 
                    CASE WHEN p.sku = ? THEN 1 ELSE 2 END,
                    p.sku
                LIMIT 10
            """, (f"{search_term}%", f"%{search_term}%", search_term))
            results = cursor.fetchall()
            
            if results:
                return [(r[0], r[1], r[2]) for r in results]
            
            # Query 2: Match by part name (medium priority)
            cursor.execute("""
                SELECT DISTINCT p.sku, p.part_name, NULL as alias_name, 2 as priority
                FROM parts p
                WHERE p.part_name LIKE ?
                ORDER BY p.part_name
                LIMIT 10
            """, (f"%{search_term}%",))
            results = cursor.fetchall()
            
            if results:
                return [(r[0], r[1], r[2]) for r in results]
            
            # Query 3: Match by alias name (low priority)
            cursor.execute("""
                SELECT DISTINCT p.sku, p.part_name, a.alternative_name
                FROM parts p
                INNER JOIN aliases a ON p.sku = a.part_id
                WHERE a.alternative_name LIKE ?
                ORDER BY a.alternative_name
                LIMIT 10
            """, (f"%{search_term}%",))
            results = cursor.fetchall()
            
            return [(r[0], r[1], r[2]) for r in results]
    
    except sqlite3.Error as e:
        print(f"Search Error: {e}")
        return []

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
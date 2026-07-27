import sqlite3
from logic.db_connection import get_connection

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
        with get_connection() as conn:
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
                p.sku,
                p.part_name,
                t.quantity,
                t.sale_at_time,
                t.transaction_type,
                t.revenue
            FROM v_transactions_with_revenue t
            INNER JOIN parts p ON t.part_id = p.id
            WHERE t.timestamp LIKE ?
            ORDER BY t.id DESC
        """

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (f"{date_string}%",))
            results = cursor.fetchall()

            if not results:
                raise ValueError(f"No transactions found for date: {date_string}")
        return results

    except sqlite3.Error as e:
        raise RuntimeError(f"Database Query failed: {e}") from e

def insert_transaction(date, quantity, sku, total_price):
    if quantity < 1:
        raise ValueError("Quantity must be at least 1")
    total_price = int(round(total_price))
    if total_price < 0:
        raise ValueError("Price cannot be negative")

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Resolve part
        cursor.execute("SELECT id FROM parts WHERE sku = ?", (sku,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"{sku} not found in parts table")
        part_id = row[0]

        # 2. Oversell gate
        cursor.execute("""
            SELECT COALESCE(SUM(qty_remaining), 0)
            FROM stock_batches WHERE part_id = ?
        """, (part_id,))
        available = cursor.fetchone()[0]
        if available < quantity:
            raise ValueError(
                f"Insufficient stock for {sku}: {available} available, {quantity} requested"
            )

        # 3. FIFO walk — decide which batches supply the sale
        cursor.execute("""
            SELECT id, qty_remaining, unit_cost
            FROM stock_batches
            WHERE part_id = ? AND qty_remaining > 0
            ORDER BY received_on ASC, id ASC
        """, (part_id,))

        splits = []          # (batch_id, qty_taken, unit_cost)
        remaining = quantity
        for batch_id, qty_rem, unit_cost in cursor.fetchall():
            if remaining == 0:
                break
            take = min(qty_rem, remaining)
            splits.append((batch_id, take, unit_cost))
            remaining -= take

        # 4. Allocate the total price across splits (remainder on last row)
        allocated = 0
        rows_to_insert = []
        for i, (batch_id, take, unit_cost) in enumerate(splits):
            if i == len(splits) - 1:
                row_total = total_price - allocated
            else:
                row_total = round(total_price * take / quantity)
                allocated += row_total
            rows_to_insert.append((batch_id, take, unit_cost, row_total))

        # 5. Write everything
        for batch_id, take, unit_cost, row_total in rows_to_insert:
            cursor.execute("""
                INSERT INTO transactions
                    (timestamp, quantity, part_id, batch_id,
                     transaction_type, cost_at_time, sale_at_time, notes)
                VALUES (?, ?, ?, ?, 'SALE', ?, ?, '')
            """, (date, take, part_id, batch_id, unit_cost, row_total))

            cursor.execute("""
                UPDATE stock_batches SET qty_remaining = qty_remaining - ?
                WHERE id = ?
            """, (take, batch_id))

        cursor.execute("""
            UPDATE parts SET current_stock = current_stock - ?
            WHERE id = ?
        """, (quantity, part_id))

    return [(take, unit_cost) for _, take, unit_cost, _ in rows_to_insert]

def check_stock_consistency():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.sku, p.current_stock, COALESCE(SUM(b.qty_remaining), 0) AS batch_total
            FROM parts p
            LEFT JOIN stock_batches b ON b.part_id = p.id
            GROUP BY p.id
            HAVING p.current_stock != COALESCE(SUM(b.qty_remaining), 0)
        """)
        return cursor.fetchall()
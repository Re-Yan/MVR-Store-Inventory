import sqlite3
from datetime import datetime
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

def get_sales_for_date(sale_date):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sale_id, logged_on, sku, part_name, quantity,
                    total_price, revenue, status, line_count, notes
            FROM v_sales_summary
            WHERE sale_date = ?
            ORDER BY logged_on DESC, sale_id DESC
        """, (sale_date,))
        return cursor.fetchall()

def get_part_snapshot(sku):
    """Everything the log form needs about a part in one round trip.
    Returns None for an unknown SKU — the form calls this as the user types."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.part_name, p.srp_price, p.stock_warning,
                   COALESCE((SELECT SUM(qty_remaining)
                             FROM stock_batches WHERE part_id = p.id), 0)
            FROM parts p
            WHERE p.sku = ?
        """, (sku,))
        row = cursor.fetchone()
        if row is None:
            return None
        part_id, part_name, srp_price, stock_warning, available = row
        return {
            "part_id": part_id,
            "part_name": part_name,
            "srp_price": srp_price,
            "stock_warning": stock_warning,
            "available": available,
        }

def record_sale(sale_date, sku, quantity, total_price, notes=""):
    try:
        parsed_date = datetime.strptime(sale_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"Sale date must be YYYY-MM-DD, got {sale_date!r}")
    if parsed_date > datetime.now().date():
        raise ValueError(f"Cannot log a sale dated in the future: {sale_date}")

    if quantity < 1:
        raise ValueError("Quantity must be at least 1")
    total_price = int(round(total_price))
    if total_price < 0:
        raise ValueError("Price cannot be negative")

    logged_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        available = cursor.fetchone()[0] # the total available amount of a specific item
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

        # 4. Header first — its id stitches the lines together
        cursor.execute("""
            INSERT INTO sales (sale_date, logged_on, total_price, status, notes)
            VALUES (?, ?, ?, 'ACTIVE', ?)
        """, (sale_date, logged_on, total_price, notes))
        sale_id = cursor.lastrowid

        # 5. Lines + batch drawdown, allocating price across splits
        allocated = 0
        for i, (batch_id, take, unit_cost) in enumerate(splits):
            if i == len(splits) - 1:
                line_total = total_price - allocated      # remainder lands here
            else:
                line_total = round(total_price * take / quantity)
                allocated += line_total

            cursor.execute("""
                INSERT INTO transactions
                    (sale_id, part_id, batch_id, quantity, cost_at_time, sale_at_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sale_id, part_id, batch_id, take, unit_cost, line_total))

            cursor.execute("""
                UPDATE stock_batches SET qty_remaining = qty_remaining - ?
                WHERE id = ?
            """, (take, batch_id))

        # 6. Denormalized mirror
        cursor.execute("""
            UPDATE parts SET current_stock = current_stock - ?
            WHERE id = ?
        """, (quantity, part_id))

    return {
        "sale_id": sale_id,
        "splits": [(take, unit_cost) for _batch, take, unit_cost in splits],
        "remaining_stock": available - quantity,
    }

def void_sale(sale_id):
    voided_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Guard — only ACTIVE sales can be voided
        cursor.execute("SELECT status FROM sales WHERE id = ?", (sale_id,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Sale {sale_id} not found")
        if row[0] != 'ACTIVE':
            raise ValueError(f"Sale {sale_id} is already {row[0]}")

        # 2. The lines tell us exactly what to give back
        cursor.execute("""
            SELECT batch_id, part_id, quantity
            FROM transactions WHERE sale_id = ?
        """, (sale_id,))
        lines = cursor.fetchall()
        if not lines:
            raise ValueError(f"Sale {sale_id} has no line items")

        # 3. Restore each batch it drew from
        for batch_id, _part_id, qty in lines:
            cursor.execute("""
                UPDATE stock_batches SET qty_remaining = qty_remaining + ?
                WHERE id = ?
            """, (qty, batch_id))

        # 4. Restore the denormalized stock, grouped by part
        totals = {}
        for _batch_id, part_id, qty in lines:
            totals[part_id] = totals.get(part_id, 0) + qty
        for part_id, qty in totals.items():
            cursor.execute("""
                UPDATE parts SET current_stock = current_stock + ?
                WHERE id = ?
            """, (qty, part_id))

        # 5. Flip the header — lines stay untouched, that's the audit trail
        cursor.execute("""
            UPDATE sales SET status = 'VOIDED', voided_on = ?
            WHERE id = ?
        """, (voided_on, sale_id))

    return {"sale_id": sale_id, "restored": sum(qty for _b, _p, qty in lines)}

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
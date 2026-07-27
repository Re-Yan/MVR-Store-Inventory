import sqlite3
from datetime import datetime
from logic.db_connection import get_connection

def get_curr_date():
        date = datetime.now()
        curr_formatted_date = date.strftime("%Y-%m-%d")
        return curr_formatted_date

def get_suppliers():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM suppliers ORDER BY name")
        return cursor.fetchall()

def get_or_create_supplier(name):
    if not name or not name.strip():
        raise ValueError("Supplier name cannot be empty")
    name = name.strip()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO suppliers (name) VALUES (?)", (name,))
        cursor.execute("SELECT id FROM suppliers WHERE name = ?", (name,))
        return cursor.fetchone()[0]

def get_part_id_by_sku(sku):
    # TODO: add error handling for this function: wrap in try/except block
    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT id 
            FROM parts
            WHERE sku = ?
        """

        cursor.execute(query, (sku,))
        part_id = cursor.fetchone()
        return part_id[0] if part_id else None

def get_request_items(statuses=None):
    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT ri.id, ri.status, p.sku, p.part_name, s.name, 
            ri.quantity, ri.unit_cost, ri.created_on, ri.ordered_on, ri.received_on
            FROM request_items ri
            INNER JOIN parts p ON ri.part_id = p.id
            LEFT JOIN suppliers s ON ri.supplier_id = s.id
        """
        params = ()
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            query += f" WHERE ri.status IN ({placeholders})"
            params = tuple(statuses)
        query += " ORDER BY ri.created_on ASC, ri.id ASC"

        cursor.execute(query, params)
        return cursor.fetchall()

def add_request_item(part_id, notes):
    with get_connection() as conn:
        cursor = conn.cursor()

        curr_date = get_curr_date()

        insert_request_item = """
            INSERT INTO request_items (part_id, supplier_id, urgency_score, status, created_on, ordered_on, received_on, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            cursor.execute(insert_request_item, (
                part_id,
                None,
                1,
                'PENDING',
                curr_date,
                None,
                None,
                notes
        ))

        except sqlite3.Error as e:
            raise RuntimeError(f"Cannot Insert into DB: {e}") from e           

def delete_request_items(item_ids):
    if not item_ids:
        return 0
    placeholders = ",".join("?" for _ in item_ids)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            DELETE FROM request_items
            WHERE id IN ({placeholders}) AND status = 'PENDING'
        """, item_ids)
        return cursor.rowcount

def get_suppliers_with_counts():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.name,
                (SELECT COUNT(*) FROM request_items ri WHERE ri.supplier_id = s.id) AS order_refs,
                (SELECT COUNT(*) FROM stock_batches b WHERE b.supplier_id = s.id) AS batch_refs
            FROM suppliers s
            ORDER BY s.name
        """)
        return cursor.fetchall()

def rename_supplier(supplier_id, new_name):
    if not new_name or not new_name.strip():
        raise ValueError("Supplier name cannot be empty")
    with get_connection() as conn:
        try:
            conn.execute("UPDATE suppliers SET name = ? WHERE id = ?",
                         (new_name.strip(), supplier_id))
        except sqlite3.IntegrityError:
            raise ValueError(f"A supplier named '{new_name.strip()}' already exists")

def delete_supplier(supplier_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT (SELECT COUNT(*) FROM request_items WHERE supplier_id = ?)
                 + (SELECT COUNT(*) FROM stock_batches WHERE supplier_id = ?)
        """, (supplier_id, supplier_id))
        if cursor.fetchone()[0]:
            raise ValueError("Cannot delete: supplier is referenced by orders or stock batches")
        conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
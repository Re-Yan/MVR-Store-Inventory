import sqlite3
import os
from datetime import datetime

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def get_curr_date():
        date = datetime.now()
        curr_formatted_date = date.strftime("%y-%m-%d")
        return curr_formatted_date

def get_part_id_by_sku(sku):
    # TODO: add error handling for this function: wrap in try/except block
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        query = """
            SELECT id 
            FROM parts
            WHERE sku = ?
        """

        cursor.execute(query, (sku,))
        part_id = cursor.fetchone()
        return part_id[0] if part_id else None

def get_request_items(status=None):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        query = """
            SELECT ri.id, ri.status, p.sku, p.part_name,
                ri.supplier, ri.created_on, ri.ordered_on, ri.received_on
            FROM request_items ri
            INNER JOIN parts p ON ri.part_id = p.id
        """
        params = ()
        if status is not None:
            query += " WHERE ri.status = ?"
            params = (status,)

        cursor.execute(query, params)
        return cursor.fetchall()

def add_request_item(part_id, supplier, notes):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        curr_date = get_curr_date()

        insert_request_item = """
            INSERT INTO request_items (part_id, supplier, urgency_score, status, created_on, ordered_on, received_on, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            cursor.execute(insert_request_item, (
                part_id,
                supplier,
                1,
                'PENDING',
                curr_date,
                None,
                None,
                notes
        ))

        except sqlite3.Error as e:
            raise RuntimeError(f"Cannot Insert into DB: {e}") from e           


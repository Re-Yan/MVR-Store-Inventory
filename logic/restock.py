import sqlite3
import os
from datetime import datetime
from itertools import groupby

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def get_curr_date():
        date = datetime.now()
        curr_formatted_date = date.strftime("%Y-%m-%d")
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

def create_batch(conn):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        curr_date = get_curr_date()

        insert_batch = """
            INSERT INTO restock_batches (created_on, status, ordered_on, completed_on)
            VALUES (?, ?, ?, ?)
        """
        
        # Create a Fresh New Request Batch
        cursor.execute(insert_batch, (
            curr_date, # date the request batch is created on
            "OPEN",
            None,
            None
        ))
        batch_id = cursor.lastrowid # retrieves the id of the INSERT query
        print(f"New Request Batch Created: Batch #{batch_id}")
        return batch_id

# fetches ONE batch along with its additional info 
def get_batch(batch_id):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        query = """
        SELECT
            rb.id,
            rb.created_on,
            rb.status
        FROM restock_batches rb
        WHERE id = ?
        """

        cursor.execute(query, (batch_id,))
        return cursor.fetchone()

def get_request_items_from_batch(batch_id):
    with sqlite3.connect(DB) as conn: 
        cursor = conn.cursor()

        query = """
        SELECT
            ri.id
        FROM request_items ri
        WHERE batch_id = ?
        """

        cursor.execute(query, (batch_id,))
        # returns all request items from the given batch ID
        return cursor.fetchall()

def fetch_most_recent_batch():
    # fetches the most recent OPEN batch. If none exists, create one
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        search_batch = """
            SELECT id
            FROM restock_batches
            WHERE status = 'OPEN'
            ORDER BY created_on DESC, id DESC
            LIMIT 1
        """

        try:
            cursor.execute(search_batch)
            result = cursor.fetchone()

            if not result:
                return create_batch(conn)

            return result[0]

        except sqlite3.Error as e:
            raise RuntimeError(f"cannot get batch data: {e}") from e

def add_request_item(batch_id, part_id, supplier, status, notes):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        curr_date = get_curr_date()

        insert_request_item = """
            INSERT INTO request_items (batch_id, part_id, supplier, urgency_score, status, created_on, date_carried_over, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            cursor.execute(insert_request_item, (
                batch_id,
                part_id,
                supplier,
                1,
                status,
                curr_date,
                None,
                notes
        ))

        except sqlite3.Error as e:
            raise RuntimeError(f"Cannot Insert into DB: {e}") from e           

def query_request_item_table():

        select_query = """
        SELECT
            ri.id,
            ri.status,
            p.sku,
            p.part_name,
            ri.supplier
        FROM request_items ri
        INNER JOIN parts p ON ri.part_id = p.id
            """

        try:
            with sqlite3.connect(DB) as conn:
                cursor = conn.cursor()
                cursor.execute(select_query)
                query_result = cursor.fetchall()
                return query_result

        except sqlite3.Error as e:
             raise RuntimeError(f"Select Query Failed: {e}")
        
def get_restock_batches():
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        select_query = """
            SELECT b.id, b.created_on, b.status,
            i.id, p.sku, p.part_name, i.created_on
            FROM restock_batches b
            LEFT JOIN request_items i ON i.batch_id = b.id
            LEFT JOIN parts p ON i.part_id = p.id
            ORDER BY b.id DESC, i.id ASC;
        """

        cursor.execute(select_query)
        # the result set from the query will become the row to be grouped
        rows = cursor.fetchall()

        grouped = []
        for batch_id, group in groupby(rows, key=lambda r: r[0]):
            rows_for_batch = list(group)
            batch_tuple = rows_for_batch[0][:3]              # b.id, created_on, status
            items = [r[3:] for r in rows_for_batch if r[3]]  # drop NULL placeholder
            grouped.append((batch_tuple, items))
        # returns batch info in proper hierarchical tuple format
        return grouped
import sqlite3
import os
from datetime import datetime

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

def add_request_item(batch_id, part_id, quantity, status, notes):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        curr_date = get_curr_date()

        insert_request_item = """
            INSERT INTO request_items (batch_id, part_id, quantity_requested, urgency_score, status, created_on, date_carried_over, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            cursor.execute(insert_request_item, (
                batch_id,
                part_id,
                quantity,
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
                p.sku,
                p.part_name,
                ri.quantity_requested,
                p.base_cost_price,
                (ri.quantity_requested * p.base_cost_price) AS total,
                ri.batch_id,
                ri.urgency_score
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
        

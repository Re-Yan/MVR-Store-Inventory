import sqlite3
import os
from datetime import datetime

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def create_batch(self):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        date = datetime.now()
        curr_formatted_date = date.strftime("%Y-%m-%d")
        
        insert_query = """
            INSERT INTO restock_batches (id, created_on, status, ordered_on, completed_on)
            VALUES (?, ?, ?, ?, ?)
            """
        
        # Create a Fresh New Request Batch
        cursor.execute(insert_query, (
            None, # id is AUTOINCREMENT no need to give a value
            curr_formatted_date, # date the request batch is created on
            "OPEN",
            None,
            None
        ))
        batch_id = cursor.lastrowid() # retrieves the id of the INSERT query
        conn.commit()
        print(f"New Request Batch Created: Batch #{batch_id}")

def get_current_batch(self):
    # fetches the most recent open OPEN batch. If none exists, create one
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        search_query = """
            SELECT *
            FROM restock_batches rb
            WHERE status = 'OPEN'
            """

        try:
            cursor.execute(search_query)
            result = cursor.fetchall()

            if not result:
                create_batch()

        except sqlite3.error as e:
            raise RuntimeError("cannot get batch data: {e}") from e

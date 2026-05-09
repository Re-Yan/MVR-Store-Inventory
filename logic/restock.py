import sqlite3
import os
from datetime import datetime

DB = os.path.join(os.path.dirname(__file__), "..", "mvr_inventory.db")

def get_curr_date(self):
        date = datetime.now()
        curr_formatted_date = date.strftime("%Y-%m-%d")

def create_batch(self):
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
        batch_id = cursor.lastrowid() # retrieves the id of the INSERT query
        conn.commit()
        print(f"New Request Batch Created: Batch #{batch_id}")
        return batch_id

def get_current_batch(self):
    # fetches the most recent open OPEN batch. If none exists, create one
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
                return self.create_batch()

        except sqlite3.Error as e:
            raise RuntimeError("cannot get batch data: {e}") from e

def add_request_item(batch_id, part_id, quantity, status, date_carried_over, notes):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()

        curr_date = get_curr_date()

        insert_request_item = """
            INSERT INTO request_items (batch_id, part_id, quantity_requested, urgency_score, status, created_on, date_carried_over, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor.execute(insert_request_item, (
            batch_id,
            part_id,
            quantity,
            "1",
            status,
            curr_date,
            date_carried_over,
            notes
        ))

import sqlite3
import csv
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "mvr_inventory.db")
CSV_FOLDER = os.path.join(BASE_DIR, "data", "csv_files")

def ensure_transactions_use_sku_fk(cursor):
    cursor.execute("PRAGMA table_info(transactions)")
    columns = cursor.fetchall()
    if not columns:
        return

    part_id_column = next((col for col in columns if col[1] == 'part_id'), None)
    part_id_type = (part_id_column[2] if part_id_column else "").upper()

    cursor.execute("PRAGMA foreign_key_list(transactions)")
    fks = cursor.fetchall()
    has_sku_fk = any(
        fk[2] == 'parts' and fk[3] == 'part_id' and fk[4] == 'sku'
        for fk in fks
    )

    if part_id_type == 'TEXT' and has_sku_fk:
        return

    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute("DROP VIEW IF EXISTS v_transactions_with_revenue")

    cursor.execute("""
        CREATE TABLE transactions_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            part_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            cost_at_time INTEGER NOT NULL,
            sale_at_time INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (part_id) REFERENCES parts(sku)
            )
        """)

    cursor.execute("""
        INSERT INTO transactions_new
        (id, timestamp, quantity, part_id, transaction_type, cost_at_time, sale_at_time, notes)
        SELECT
            t.id,
            t.timestamp,
            t.quantity,
            COALESCE(
                (
                    SELECT p.sku
                    FROM parts p
                    WHERE p.sku = CAST(t.part_id AS TEXT)
                       OR ltrim(p.sku, '0') = ltrim(CAST(t.part_id AS TEXT), '0')
                    LIMIT 1
                ),
                CAST(t.part_id AS TEXT)
            ),
            t.transaction_type,
            t.cost_at_time,
            t.sale_at_time,
            t.notes
        FROM transactions t
        """)

    cursor.execute("DROP TABLE transactions")
    cursor.execute("ALTER TABLE transactions_new RENAME TO transactions")
    cursor.execute("PRAGMA foreign_keys = ON")


def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # to enable foreign relationships 
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT UNIQUE NOT NULL
            )
        """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shelves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_code TEXT UNIQUE NOT NULL
            )
        """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_type TEXT UNIQUE NOT NULL
            )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            part_name TEXT NOT NULL,
            base_cost_price INTEGER NOT NULL, 
            srp_price INTEGER NOT NULL,
            current_stock INTEGER NOT NULL, 
            shelf_id INTEGER,
            stock_warning INTEGER,
            is_active INTEGER,
            FOREIGN KEY (shelf_id) REFERENCES shelves(id)
            )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, -- Date Format: YYYY-MM-DD
            quantity INTEGER NOT NULL,
            part_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL, 
            cost_at_time INTEGER NOT NULL, 
            sale_at_time INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (part_id) REFERENCES parts(id)
            )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id TEXT NOT NULL,
            original_name TEXT,
            alternative_name TEXT NOT NULL,
            location TEXT,
            model TEXT,
            notes TEXT,
            FOREIGN KEY (part_id) REFERENCES parts(sku),
            UNIQUE (part_id, alternative_name, location, model, notes)
            )
        """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_aliases_part_id
        ON aliases(part_id)
    """)

    ensure_transactions_use_sku_fk(cursor)

    conn.commit()
    return conn

def create_revenue_view():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name='transactions'
    """)
    if cursor.fetchone() is None:
        conn.close()
        raise RuntimeError("transactions table not found. Run initialize_database() and migrate_csv_to_sql() first.")

    cursor.execute("DROP VIEW IF EXISTS v_transactions_with_revenue")

    cursor.execute("""
        CREATE VIEW v_transactions_with_revenue AS
            SELECT 
                *,
                (sale_at_time - (quantity * cost_at_time)) AS revenue
            FROM transactions;                  
                   """)

    conn.commit()
    conn.close()

def create_restock_tables():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_id INTEGER NOT NULL,
                supplier TEXT, 
                urgency_score INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK(status IN ('PENDING', 'ORDERED', 'RECEIVED')),
                created_on TEXT NOT NULL DEFAULT CURRENT_DATE,
                ordered_on TEXT,
                received_on TEXT,
                notes TEXT,
                
                FOREIGN KEY (part_id) REFERENCES parts(id)
                )
                    """)

def migrate_csv_to_sql():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Normalize ID text from CSV before matching against SKU values.
    def normalize_id(value):
        if value is None:
            return ""
        return str(value).strip()

    def resolve_part_sku(raw_part_id):
        part_id_text = normalize_id(raw_part_id)
        if not part_id_text:
            return None

        cursor.execute(
            """
            SELECT sku
            FROM parts
            WHERE sku = ?
               OR ltrim(sku, '0') = ltrim(?, '0')
            LIMIT 1
            """,
            (part_id_text, part_id_text),
        )
        found = cursor.fetchone()
        return found[0] if found else None

    # 1. Migrate Categories
    category_file = os.path.join(CSV_FOLDER, 'categories.csv')
    if os.path.exists(category_file):
        with open(category_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # handle cases where the header might be 'categories' or 'category'
            headers = reader.fieldnames
            cat_col = 'categories' if 'categories' in headers else 'category'
            for row in reader:
                cursor.execute("INSERT OR IGNORE INTO categories (category) VALUES (?)", (row[cat_col],))

    # 2. Migrate Models
    model_file = os.path.join(CSV_FOLDER, 'models.csv')
    if os.path.exists(model_file):
        with open(model_file, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader) # Skip header row
            for row in reader:
                if len(row) > 1 and row[1].strip():
                    cursor.execute("INSERT OR IGNORE INTO models (model_type) VALUES (?)", (row[1].strip(),))

    # 3. Migrate Shelves
    shelf_file = os.path.join(CSV_FOLDER, 'shelves.csv')
    if os.path.exists(shelf_file):
        with open(shelf_file, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader) # Skip header row
            for row in reader:
                if len(row) > 1 and row[1].strip():
                    cursor.execute("INSERT OR IGNORE INTO shelves (location_code) VALUES (?)", (row[1].strip(),))

    # 4. Migrate Parts
    parts_file = os.path.join(CSV_FOLDER, 'parts.csv')
    if os.path.exists(parts_file):
        with open(parts_file, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = [h.strip() for h in next(reader)]
            for row in reader:
                if not row: continue
                row_dict = dict(zip(headers, row))
                shelf_id = row_dict.get('shelf_id')
                shelf_id = int(shelf_id) if shelf_id and shelf_id.strip() else None
                
                stock_warning = row_dict.get('stock_warning')
                stock_warning = int(stock_warning) if stock_warning and stock_warning.strip() else None
                
                is_active = row_dict.get('is_active')
                is_active = int(is_active) if is_active and is_active.strip() else None
                
                cursor.execute("""
                    INSERT OR IGNORE INTO parts 
                    (sku, part_name, base_cost_price, srp_price, current_stock, shelf_id, stock_warning, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_dict.get('sku'), row_dict.get('part_name'), 
                    row_dict.get('base_cost_price'), row_dict.get('srp_price'), 
                    row_dict.get('current_stock'), shelf_id, stock_warning, is_active
                ))

    # 5. Migrate Transactions
    trans_file = os.path.join(CSV_FOLDER, 'transactions.csv')
    if os.path.exists(trans_file):
        # Transactions CSV is treated as a full snapshot, so clear existing rows first.
        cursor.execute("DELETE FROM transactions")
        with open(trans_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute("""
                    INSERT INTO transactions 
                    (timestamp, quantity, part_id, transaction_type, cost_at_time, sale_at_time, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('timestamp'), row.get('quantity'), normalize_id(row.get('part_id')), 
                    row.get('transaction_type'), row.get('cost_at_time'), 
                    row.get('sale_at_time'), row.get('notes')
                ))

    # 6. Migrate Aliases
    alias_file = os.path.join(CSV_FOLDER, 'Aliases.csv')
    if os.path.exists(alias_file):
        with open(alias_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                part_sku = resolve_part_sku(row.get('Part ID'))
                if not part_sku:
                    continue

                alternative_name = normalize_id(row.get('Alternative Name'))
                if not alternative_name:
                    continue

                cursor.execute("""
                    INSERT OR IGNORE INTO aliases
                    (part_id, original_name, alternative_name, location, model, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    part_sku,
                    normalize_id(row.get('Original Name')),
                    alternative_name,
                    normalize_id(row.get('Location')),
                    normalize_id(row.get('Model')),
                    normalize_id(row.get('Notes')),
                ))

    conn.commit()
    conn.close()
    print("CSV data successfully migrated to SQL tables.")

if __name__ == "__main__":
    initialize_database()
    migrate_csv_to_sql()
    create_revenue_view()
    create_restock_tables()
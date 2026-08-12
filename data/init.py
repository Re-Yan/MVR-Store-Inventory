import sqlite3
import csv
import os
import re


def normalize_location(value):
    """Canonical matching form for shelf location codes.

    Used for lookups only -- shelves store their human-cased form.
    'rl1-left', 'RL1 -  Left' and 'RL1 - Left' all normalize identically.
    """
    if value is None:
        return ""
    value = value.strip().upper()
    value = re.sub(r"\s*-\s*", " - ", value)
    value = re.sub(r"\s+", " ", value)
    return value

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "mvr_inventory.db")
CSV_FOLDER = os.path.join(BASE_DIR, "data", "csv_files")


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
            location_code TEXT UNIQUE NOT NULL COLLATE NOCASE
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
            placement TEXT NOT NULL DEFAULT 'SHELF'
                CHECK (placement IN ('SHELF', 'FLOOR', 'HANGING')),
            stock_warning INTEGER,
            is_active INTEGER,
            FOREIGN KEY (shelf_id) REFERENCES shelves(id)
            )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date   TEXT NOT NULL,
            logged_on   TEXT NOT NULL,
            total_price INTEGER NOT NULL,
            status      TEXT NOT NULL DEFAULT 'ACTIVE'
                        CHECK (status IN ('ACTIVE', 'VOIDED')),
            voided_on   TEXT,
            notes       TEXT
            )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id         INTEGER NOT NULL,
            part_id         INTEGER NOT NULL,
            batch_id        INTEGER NOT NULL,
            quantity        INTEGER NOT NULL CHECK (quantity > 0),
            cost_at_time    INTEGER NOT NULL,
            sale_at_time    INTEGER NOT NULL,
            FOREIGN KEY (sale_id)   REFERENCES sales(id),
            FOREIGN KEY (part_id)   REFERENCES parts(id),
            FOREIGN KEY (batch_id)  REFERENCES stock_batches(id)
            )
        """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_sale ON transactions(sale_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_part ON transactions(part_id)")

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

    conn.commit()
    return conn


def create_restock_tables():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL COLLATE NOCASE
                       )
                        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_id INTEGER NOT NULL,
                supplier_id INTEGER, 
                quantity INTEGER,
                unit_cost INTEGER,
                urgency_score INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK(status IN ('PENDING', 'ORDERED', 'RECEIVED')),
                created_on TEXT NOT NULL DEFAULT CURRENT_DATE,
                ordered_on TEXT,
                received_on TEXT,
                notes TEXT,
                       
                FOREIGN KEY (part_id) REFERENCES parts(id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
                       )
                        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_id INTEGER NOT NULL,
                supplier_id INTEGER,
                request_item_id INTEGER,
                qty_received INTEGER NOT NULL,
                qty_remaining INTEGER NOT NULL,
                unit_cost INTEGER NOT NULL,
                received_on TEXT NOT NULL,
                CHECK (qty_remaining >= 0 AND qty_remaining <= qty_received),
                
                FOREIGN KEY (part_id) REFERENCES parts(id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY (request_item_id) REFERENCES request_items(id)
                      )
                        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_batches_fifo
            ON stock_batches(part_id, received_on)
                        """)
    
        conn.commit()

def create_sales_view():
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

    # this code will need to be revisited if we enable market basket analysis (grouping of sales)
    cursor.execute("DROP VIEW IF EXISTS v_sale_lines_with_revenue")
    cursor.execute("""
        CREATE VIEW v_sale_lines_with_revenue AS
        SELECT t.id AS line_id, t.sale_id, s.sale_date, s.status, t.part_id,
                t.batch_id, t.quantity, t.cost_at_time, t.sale_at_time,
                (t.sale_at_time - t.quantity * t.cost_at_time) AS revenue
        FROM transactions t
        JOIN sales s ON t.sale_id = s.id; 
                   """)

    cursor.execute("DROP VIEW IF EXISTS v_sales_summary")
    cursor.execute("DROP VIEW IF EXISTS v_transactions_with_revenue")
    cursor.execute("""
        CREATE VIEW v_sales_summary AS
        SELECT s.id AS sale_id, s.sale_date, s.logged_on, s.status, s.voided_on, s.total_price, s.notes,
            p.sku, p.part_name,
            SUM(t.quantity)                                     AS quantity,
            SUM(t.quantity * t.cost_at_time)                    AS total_cost,
            s.total_price - SUM(t.quantity * t.cost_at_time)    AS revenue,
            COUNT(t.id)                                         AS line_count
        FROM sales s
        JOIN transactions t ON t.sale_id = s.id
        JOIN parts p ON t.part_id = p.id
        GROUP BY s.id;
    """)

    conn.commit()
    conn.close()

def seed_opening_batches():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")    
        cursor.execute("""
            INSERT INTO stock_batches
                (part_id, supplier_id, request_item_id, qty_received, qty_remaining, unit_cost, received_on)
            SELECT p.id, NULL, NULL, p.current_stock, p.current_stock, p.base_cost_price, DATE('now', 'localtime')
            FROM parts p
            WHERE p.current_stock > 0
                AND NOT EXISTS (
                       SELECT 1 FROM stock_batches b 
                       WHERE b.part_id = p.id
                       )
                        """)
        conn.commit()

def migrate_csv_to_sql():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

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
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get('location_code') or '').strip()
                if code:
                    cursor.execute("INSERT OR IGNORE INTO shelves (location_code) VALUES (?)", (code,))

    # Lookup for resolving parts.csv location codes -> shelf ids.
    # Normalized on both sides so casing/spacing variants still match.
    cursor.execute("SELECT location_code, id FROM shelves")
    shelf_lookup = {normalize_location(code): sid for code, sid in cursor.fetchall()}

    # 4. Migrate Parts
    parts_file = os.path.join(CSV_FOLDER, 'parts.csv')
    if os.path.exists(parts_file):
        unknown_locations = []
        duplicate_skus = []
        seen_skus = set()
        with open(parts_file, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = [h.strip() for h in next(reader)]
            for row in reader:
                if not row: continue
                row_dict = dict(zip(headers, row))
                sku = (row_dict.get('sku') or '').strip()

                if sku in seen_skus:
                    duplicate_skus.append(sku)
                seen_skus.add(sku)

                # Resolve human-readable location code to a shelf id.
                # Unknown codes are collected and raised at the end --
                # a typo must never silently become NULL.
                location_code = (row_dict.get('location_code') or '').strip()
                shelf_id = None
                if location_code:
                    if '(' in location_code:
                        raise ValueError(
                            f"{sku}: qualifiers belong in the placement column, "
                            f"not location_code: {location_code!r}"
                        )
                    shelf_id = shelf_lookup.get(normalize_location(location_code))
                    if shelf_id is None:
                        unknown_locations.append((sku, location_code))

                placement = (row_dict.get('placement') or '').strip().upper() or 'SHELF'

                stock_warning = row_dict.get('stock_warning')
                stock_warning = int(stock_warning) if stock_warning and stock_warning.strip() else None

                is_active = row_dict.get('is_active')
                is_active = int(is_active) if is_active and is_active.strip() else None

                def to_int(value):
                    if value is None:
                        return 0
                    cleaned = value.replace(',', '').strip()
                    return int(cleaned) if cleaned else 0

                current_stock = to_int(row_dict.get('current_stock'))
                base_cost_price = to_int(row_dict.get('base_cost_price'))
                srp_price = to_int(row_dict.get('srp_price'))

                cursor.execute("""
                    INSERT OR IGNORE INTO parts
                    (sku, part_name, base_cost_price, srp_price, current_stock, shelf_id, placement, stock_warning, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sku, row_dict.get('part_name'),
                    base_cost_price, srp_price,
                    current_stock, shelf_id, placement, stock_warning, is_active
                ))

        if unknown_locations:
            conn.close()
            raise ValueError(
                "Unknown shelf locations in parts.csv (add them to shelves.csv "
                f"or fix the typo): {unknown_locations}"
            )
        if duplicate_skus:
            print(f"WARNING: duplicate SKUs in parts.csv -- second occurrence "
                  f"was DISCARDED by INSERT OR IGNORE: {sorted(set(duplicate_skus))}")

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
    create_restock_tables()
    migrate_csv_to_sql()
    create_sales_view()
    seed_opening_batches()
import os, sys, sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from logic.transactions import check_stock_consistency

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mvr_inventory.db")

drift = check_stock_consistency()
print("stock consistency:", drift or "OK")

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM stock_batches WHERE qty_remaining < 0 OR qty_remaining > qty_received")
print("impossible batch quantities:", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM transactions WHERE batch_id IS NULL")
print("sales with no batch link:", cur.fetchone()[0])

cur.execute("PRAGMA foreign_key_check")
print("FK violations:", cur.fetchall() or "none")

print("\n-- revenue by supplier --")
cur.execute("""
    SELECT COALESCE(s.name, '(opening stock)') AS supplier,
           SUM(t.quantity)                     AS units_sold,
           SUM(t.sale_at_time)                 AS gross,
           SUM(t.quantity * t.cost_at_time)    AS cost,
           SUM(t.revenue)                      AS revenue
    FROM v_transactions_with_revenue t
    LEFT JOIN stock_batches b ON t.batch_id = b.id
    LEFT JOIN suppliers s ON b.supplier_id = s.id
    GROUP BY supplier
    ORDER BY revenue DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]:<18} units={r[1]:<5} gross={r[2]:<8} cost={r[3]:<8} revenue={r[4]}")
conn.close()

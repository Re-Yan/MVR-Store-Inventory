import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from logic.db_connection import get_connection
from logic.transactions import check_stock_consistency

failures = []

def report(name, offenders, detail=None):
    """offenders: falsy = the invariant holds."""
    if offenders:
        failures.append(name)
        print(f"  [FAIL] {name}")
        for row in offenders[:5]:
            print(f"         {detail(row) if detail else row}")
        if len(offenders) > 5:
            print(f"         ... and {len(offenders) - 5} more")
    else:
        print(f"  [ OK ] {name}")


conn = get_connection()
cur = conn.cursor()

print("-- invariants --")

# A. The denormalized mirror on parts must agree with the batch ledger.
report("parts.current_stock matches SUM(batch.qty_remaining)",
       check_stock_consistency(),
       lambda r: f"{r[0]}: parts={r[1]} batches={r[2]}")

# B. Each sale's line allocations must reconstruct the entered total exactly.
cur.execute("""
    SELECT s.id, s.total_price, SUM(t.sale_at_time)
    FROM sales s
    JOIN transactions t ON t.sale_id = s.id
    GROUP BY s.id
    HAVING s.total_price != SUM(t.sale_at_time)
""")
report("line allocations sum to sales.total_price",
       cur.fetchall(),
       lambda r: f"sale {r[0]}: header={r[1]} lines={r[2]}")

# C. Batch drawdown must equal the quantity consumed by ACTIVE sales only.
#    Voided sales keep their lines but their stock was handed back, so an
#    unfiltered sum here will false-alarm the moment anything is voided.
cur.execute("""
    SELECT b.id,
           b.qty_received - b.qty_remaining AS consumed,
           COALESCE(SUM(CASE WHEN s.status = 'ACTIVE' THEN t.quantity END), 0) AS active_lines
    FROM stock_batches b
    LEFT JOIN transactions t ON t.batch_id = b.id
    LEFT JOIN sales s ON s.id = t.sale_id
    GROUP BY b.id
    HAVING consumed != active_lines
""")
report("batch drawdown matches ACTIVE line quantities",
       cur.fetchall(),
       lambda r: f"batch {r[0]}: consumed={r[1]} active_lines={r[2]}")

cur.execute("SELECT id, qty_received, qty_remaining FROM stock_batches WHERE qty_remaining < 0 OR qty_remaining > qty_received")
report("no impossible batch quantities", cur.fetchall(),
       lambda r: f"batch {r[0]}: {r[2]}/{r[1]}")

cur.execute("SELECT id, sale_id FROM transactions WHERE sale_id NOT IN (SELECT id FROM sales)")
report("no orphaned line items", cur.fetchall(),
       lambda r: f"line {r[0]} -> missing sale {r[1]}")

cur.execute("SELECT id FROM sales WHERE id NOT IN (SELECT sale_id FROM transactions)")
report("no sale headers without lines", cur.fetchall(), lambda r: f"sale {r[0]}")

cur.execute("SELECT id, status, voided_on FROM sales WHERE (status = 'VOIDED') != (voided_on IS NOT NULL)")
report("VOIDED status and voided_on agree", cur.fetchall(),
       lambda r: f"sale {r[0]}: status={r[1]} voided_on={r[2]}")

cur.execute("PRAGMA foreign_key_check")
report("no foreign key violations", cur.fetchall())

print("\n-- revenue by supplier (ACTIVE sales only) --")
cur.execute("""
    SELECT COALESCE(sup.name, '(opening stock)')     AS supplier,
           SUM(v.quantity)                           AS units_sold,
           SUM(v.sale_at_time)                       AS gross,
           SUM(v.quantity * v.cost_at_time)          AS cost,
           SUM(v.revenue)                            AS revenue
    FROM v_sale_lines_with_revenue v
    LEFT JOIN stock_batches b ON v.batch_id = b.id
    LEFT JOIN suppliers sup ON b.supplier_id = sup.id
    WHERE v.status = 'ACTIVE'
    GROUP BY supplier
    ORDER BY revenue DESC
""")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  {r[0]:<18} units={r[1]:<5} gross={r[2]:<8} cost={r[3]:<8} revenue={r[4]}")
else:
    print("  (no sales recorded yet)")

print("\n-- void activity --")
cur.execute("""
    SELECT s.status, COUNT(*), COALESCE(SUM(s.total_price), 0)
    FROM sales s GROUP BY s.status
""")
counts = dict((r[0], (r[1], r[2])) for r in cur.fetchall())
active_n, active_v = counts.get("ACTIVE", (0, 0))
void_n, void_v = counts.get("VOIDED", (0, 0))
total_n = active_n + void_n
rate = (void_n / total_n * 100) if total_n else 0
print(f"  active: {active_n} sale(s), total {active_v}")
print(f"  voided: {void_n} sale(s), total {void_v}   ({rate:.1f}% void rate)")

conn.close()

print("\n" + "=" * 52)
if failures:
    print(f"FAILED {len(failures)} invariant(s): " + ", ".join(failures))
else:
    print("All invariants OK.")
print("=" * 52)
sys.exit(1 if failures else 0)

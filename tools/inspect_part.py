import os, sqlite3, sys

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mvr_inventory.db")

def inspect(sku):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("SELECT id, part_name, current_stock FROM parts WHERE sku = ?", (sku,))
    row = cur.fetchone()
    if row is None:
        print(f"No part with sku {sku}")
        return
    part_id, name, stock = row
    print(f"\n=== {sku} | {name} ===")
    print(f"current_stock: {stock}")

    print("\n-- batches (FIFO order) --")
    cur.execute("""
        SELECT b.id, COALESCE(s.name, '(opening)'), b.qty_received,
               b.qty_remaining, b.unit_cost, b.received_on
        FROM stock_batches b
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        WHERE b.part_id = ?
        ORDER BY b.received_on ASC, b.id ASC
    """, (part_id,))
    batches = cur.fetchall()
    for b in batches:
        print(f"  id={b[0]:<4} {b[1]:<16} {b[3]}/{b[2]} left @ {b[4]:<6} recv {b[5]}")
    print(f"  SUM(qty_remaining) = {sum(b[3] for b in batches)}")

    print("\n-- sales --")
    cur.execute("""
        SELECT t.id, t.timestamp, t.quantity, t.cost_at_time,
               t.sale_at_time, t.revenue, COALESCE(s.name, '(opening)')
        FROM v_transactions_with_revenue t
        LEFT JOIN stock_batches b ON t.batch_id = b.id
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        WHERE t.part_id = ?
        ORDER BY t.id
    """, (part_id,))
    sales = cur.fetchall()
    for s in sales:
        print(f"  id={s[0]:<4} {s[1]}  qty={s[2]:<4} cost/u={s[3]:<6} "
              f"total={s[4]:<8} revenue={s[5]:<8} from {s[6]}")
    if sales:
        print(f"  total collected = {sum(s[4] for s in sales)}")

    conn.close()

if __name__ == "__main__":
    inspect(sys.argv[1] if len(sys.argv) > 1 else "18201044")

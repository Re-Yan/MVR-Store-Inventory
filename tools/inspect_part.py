import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from logic.db_connection import get_connection


def inspect(sku):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, part_name, current_stock, srp_price FROM parts WHERE sku = ?", (sku,))
    row = cur.fetchone()
    if row is None:
        print(f"No part with sku {sku}")
        conn.close()
        return
    part_id, name, stock, srp = row
    print(f"\n=== {sku} | {name} ===")
    print(f"current_stock: {stock}    srp: {srp}")

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

    print("\n-- sale lines --")
    cur.execute("""
        SELECT v.sale_id, v.sale_date, v.status, v.quantity, v.cost_at_time,
               v.sale_at_time, v.revenue, COALESCE(s.name, '(opening)')
        FROM v_sale_lines_with_revenue v
        LEFT JOIN stock_batches b ON v.batch_id = b.id
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        WHERE v.part_id = ?
        ORDER BY v.sale_id, v.line_id
    """, (part_id,))
    lines = cur.fetchall()
    for l in lines:
        mark = "  " if l[2] == "ACTIVE" else " *"
        print(f" {mark} sale={l[0]:<4} {l[1]}  {l[2]:<7} qty={l[3]:<4} cost/u={l[4]:<6} "
              f"total={l[5]:<8} revenue={l[6]:<8} from {l[7]}")

    if lines:
        active = [l for l in lines if l[2] == "ACTIVE"]
        voided = [l for l in lines if l[2] != "ACTIVE"]
        print(f"\n  active:  {len(active)} line(s), {sum(l[3] for l in active)} unit(s), "
              f"collected {sum(l[5] for l in active)}, revenue {sum(l[6] for l in active)}")
        if voided:
            print(f"  voided:  {len(voided)} line(s), {sum(l[3] for l in voided)} unit(s) "
                  f"(stock returned to batches, lines kept for audit)")
    else:
        print("  (no sales recorded for this part)")

    conn.close()


if __name__ == "__main__":
    inspect(sys.argv[1] if len(sys.argv) > 1 else "18201044")

from guardrails import validate_sql

tests = [
    ("SELECT COUNT(*) FROM orders", True),
    ("WITH t AS (SELECT * FROM orders) SELECT COUNT(*) FROM t", True),
    ("SELECT order_id FROM orders UNION SELECT order_id FROM order_items", True),
    ("SELECT * FROM orders; DROP TABLE orders", False),
    ("DELETE FROM orders", False),
    ("UPDATE customers SET customer_city = 'x'", False),
    ("DROP TABLE orders", False),
    ("INSERT INTO sellers VALUES (1,2,3,4)", False),
    ("PRAGMA table_info(orders)", False),
    ("ATTACH DATABASE 'x.db' AS x", False),
]
passed = 0
for sql, should_allow in tests:
    ok, msg, _ = validate_sql(sql)
    good = (ok == should_allow)
    passed += good
    print("PASS" if good else "FAIL", "|", "ALLOWED" if ok else "BLOCKED", "|", sql[:55])
print(f"\n{passed}/{len(tests)} guardrail tests passed")
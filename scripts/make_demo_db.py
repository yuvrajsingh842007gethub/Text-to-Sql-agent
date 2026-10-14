import sqlite3, os
import pandas as pd

SRC, DST = "olist.db", "olist_demo.db"
if os.path.exists(DST):
    os.remove(DST)

src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
dst = sqlite3.connect(DST)

tables = [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")
          if r[0] != "geolocation"]

for t in tables:
    df = pd.read_sql(f"SELECT * FROM {t}", src)
    if t == "order_reviews":
        df = df.drop(columns=[c for c in ["review_comment_title", "review_comment_message"] if c in df.columns])
    df.to_sql(t, dst, index=False)
    print("copied", t, len(df))

for q in [
    "CREATE INDEX idx_orders_id ON orders(order_id)",
    "CREATE INDEX idx_orders_cust ON orders(customer_id)",
    "CREATE INDEX idx_cust_id ON customers(customer_id)",
    "CREATE INDEX idx_items_order ON order_items(order_id)",
    "CREATE INDEX idx_items_prod ON order_items(product_id)",
    "CREATE INDEX idx_items_seller ON order_items(seller_id)",
    "CREATE INDEX idx_pay_order ON order_payments(order_id)",
    "CREATE INDEX idx_rev_order ON order_reviews(order_id)",
    "CREATE INDEX idx_prod_id ON products(product_id)",
    "CREATE INDEX idx_sell_id ON sellers(seller_id)",
]:
    dst.execute(q)
dst.commit()
dst.execute("VACUUM")
dst.close()
print("size MB:", round(os.path.getsize(DST) / 1_000_000, 1))
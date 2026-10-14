import gzip, shutil, os

with open("olist_demo.db", "rb") as f_in, gzip.open("olist_demo.db.gz", "wb", compresslevel=9) as f_out:
    shutil.copyfileobj(f_in, f_out)

print("compressed MB:", round(os.path.getsize("olist_demo.db.gz") / 1_000_000, 1))
import sqlite3, os, glob
import pandas as pd

conn = sqlite3.connect("olist.db")

for f in glob.glob("data/*.csv"):
    name= os.path.basename(f).replace(".csv","")
    name = name.replace("olist_","").replace("_dataset","")
    df = pd.read_csv(f)
    df.to_sql(name, conn, if_exists="replace", index=False)
    print(f"Loaded {name} : {len(df)} rows, {len(df.columns)} columns")

conn.close()
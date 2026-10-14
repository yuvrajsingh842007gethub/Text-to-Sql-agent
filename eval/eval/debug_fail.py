import json, sqlite3

conn = sqlite3.connect("file:olist.db?mode=ro", uri=True)

def run(sql):
    try:
        return conn.execute(sql).fetchall()
    except Exception as e:
        return f"ERROR: {e}"

for r in json.load(open("eval/eval/results_baseline.json", encoding="utf-8")):
    if r["status"] != "correct":
        print("=" * 70)
        print(r["id"], r["q"])
        print("\nGOLD SQL :", r["gold"])
        print("GOLD ROWS:", str(run(r["gold"]))[:400])
        print("\nAGENT SQL:", r["agent_sql"])
        print("AGENT ROWS:", str(run(r["agent_sql"]))[:400])
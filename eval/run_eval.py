import json, sqlite3, sys, time, os

ROOT = r"C:\Users\HP\OneDrive\Desktop\Text-to-Sql Agent"
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from agent import generate_sql
from guardrails import validate_sql

OUT = "eval/results_guardrails.json"
conn = sqlite3.connect("file:olist.db?mode=ro", uri=True)

# ---- LAST WALI LINE 1: yaha jodo (conn ke turant neeche) ----
def run_limited(sql, seconds=30):
    start = time.time()
    conn.set_progress_handler(lambda: 1 if time.time() - start > seconds else 0, 100000)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.set_progress_handler(None, 0)
# --------------------------------------------------------------

def norm_val(v):
    if isinstance(v, str):
        try:
            v = float(v)
        except ValueError:
            return v.strip().lower()
    if isinstance(v, (int, float)):
        return round(float(v), 1)
    return v

def norm(rows):
    return sorted([tuple(norm_val(v) for v in r) for r in rows], key=str)

questions = json.load(open("eval/eval/questions.json", encoding="utf-8"))

old = {}
if os.path.exists(OUT):
    for r in json.load(open(OUT, encoding="utf-8")):
        if r.get("agent_sql"):
            old[(r["id"], r["q"])] = r

results, stopped = [], False

for item in questions:
    key = (item["id"], item["q"])
    if key in old:
        agent_sql, latency = old[key]["agent_sql"], old[key].get("latency", 0)
    else:
        t0 = time.time()
        try:
            state = {"question": item["q"], "sql": "", "result": "", "error": "", "answer": ""}
            agent_sql = generate_sql(state)["sql"]
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                print(f"[{item['id']}] Rate/daily limit hit. Progress saved, baad mein dobara chalao.")
                stopped = True
                break
            print(f"[{item['id']}] LLM error: {e}")
            continue
        latency = round(time.time() - t0, 2)
        time.sleep(4)

    status, err = "wrong", ""
    try:
        # ---- LAST WALI LINE 2: yaha conn.execute ki jagah run_limited ----
        ok, msg, agent_sql = validate_sql(agent_sql)
        if not ok:
            raise ValueError(f"Blocked: {msg}")
        if norm(run_limited(item["gold"])) == norm(run_limited(agent_sql)):
            status = "correct"
        # ------------------------------------------------------------------
    except Exception as e:
        status, err = "error", str(e)

    print(f"[{item['id']:>2}] {item['level']:<5} {status:<8} {latency}s")
    results.append({**item, "agent_sql": agent_sql, "status": status, "error": err, "latency": latency})
    json.dump(results, open(OUT, "w", encoding="utf-8"), indent=2)

correct = sum(r["status"] == "correct" for r in results)
print(f"\nProcessed {len(results)}/{len(questions)} questions")
print(f"Execution accuracy: {correct}/{len(results)} = {100*correct/max(len(results),1):.1f}%")
for lvl in ["easy", "join", "date", "hard"]:
    sub = [r for r in results if r["level"] == lvl]
    print(f"  {lvl}: {sum(r['status']=='correct' for r in sub)}/{len(sub)}")
if stopped:
    print("\nNOTE: Eval adhura hai. Limit reset ke baad dobara chalao, wahi se aage badhega.")
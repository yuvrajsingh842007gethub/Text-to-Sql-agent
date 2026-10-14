import os, sqlite3, time
import collections
from fastapi import Request
from fastapi.responses import FileResponse
from typing import Optional

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)  # agent.py "olist.db" ko relative path se kholta hai
import gzip, shutil

if not os.path.exists("olist.db") and os.path.exists("olist_demo.db.gz"):
    with gzip.open("olist_demo.db.gz", "rb") as f_in, open("olist.db", "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent import app as agent_app

api = FastAPI(title="Text-to-SQL Agent")
HITS = collections.defaultdict(list)
GLOBAL_HITS = []
PER_IP_LIMIT, PER_IP_WINDOW = 10, 3600
GLOBAL_LIMIT, GLOBAL_WINDOW = 40, 86400


def check_limits(request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    now = time.time()
    HITS[ip] = [t for t in HITS[ip] if now - t < PER_IP_WINDOW]
    GLOBAL_HITS[:] = [t for t in GLOBAL_HITS if now - t < GLOBAL_WINDOW]
    if len(HITS[ip]) >= PER_IP_LIMIT:
        raise HTTPException(status_code=429, detail="You have reached the hourly limit for this demo. Please try again later.")
    if len(GLOBAL_HITS) >= GLOBAL_LIMIT:
        raise HTTPException(status_code=429, detail="The demo has reached its daily limit. Please try again tomorrow.")
    HITS[ip].append(now)
    GLOBAL_HITS.append(now)
@api.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))
DB_PATH = os.path.join(BASE, "olist.db")


class AskRequest(BaseModel):
    question: str
    clarification: Optional[str] = ""


def fetch_table(sql: str, limit: int = 200):
    """Safe SQL ko read-only connection se chalakar columns aur rows lata hai."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description]
        rows = [list(r) for r in cur.fetchmany(limit)]
        return columns, rows
    finally:
        conn.close()


@api.post("/ask")
def ask(req: AskRequest, request: Request):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is empty.")
    check_limits(request)
    ...

    state = {
        "question": question,
        "sql": "", "result": "", "error": "", "answer": "",
        "clarification": req.clarification or "",
        "needs_clarification": False,
        "clarify_question": "", "clarify_options": [],
    }

    t0 = time.time()
    try:
        out = agent_app.invoke(state)
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate" in msg.lower():
            raise HTTPException(status_code=429, detail="Demo limit reached. Please try again later.")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")

    # Case 1: agent ko clarification chahiye
    if out.get("needs_clarification"):
        return {
            "needs_clarification": True,
            "clarify_question": out["clarify_question"],
            "options": out["clarify_options"],
        }

    # Case 2: normal jawab (ya blocked / error)
    error = out.get("error", "")
    blocked = error.startswith("Blocked")
    columns, rows = [], []
    if not error and out.get("sql"):
        try:
            columns, rows = fetch_table(out["sql"])
        except Exception as e:
            error = str(e)

    return {
        "needs_clarification": False,
        "sql": out.get("sql", ""),
        "columns": columns,
        "rows": rows,
        "answer": out.get("answer", ""),
        "blocked": blocked,
        "error": error,
        "interpretation": req.clarification or "",
        "latency_ms": int((time.time() - t0) * 1000),
    }
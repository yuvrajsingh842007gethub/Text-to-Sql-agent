import re 
from typing import TypedDict
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase   
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from guardrails import validate_sql
import json
from sqlalchemy import inspect

load_dotenv()
from sqlalchemy import create_engine, event

engine = create_engine("sqlite:///olist.db")

@event.listens_for(engine, "connect")
def set_read_only(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA query_only = ON")

db = SQLDatabase(engine, sample_rows_in_table_info=0)

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0, max_retries=2, timeout=60)
SCHEMA = db.get_table_info()

Notes = """
Notes about this database:
- orders.customer_id -> customers.customer_id
- order_items.order_id -> orders.order_id
- order_items.product_id -> products.product_id
- order_items.seller_id -> sellers.seller_id
- order_payments.order_id -> orders.order_id
- order_reviews.order_id -> orders.order_id
- Revenue = SUM(order_items.price) (use order_payments.payment_value for total paid)
- orders.order_status values include: delivered, shipped, canceled, unavailable
- Product category names are in Portuguese; English names are in
  product_category_name_translation (product_category_name_english)
- Dates are stored as TEXT like '2017-10-02 10:56:33'; use strftime() / substr()
- customers.customer_id is generated per order. To identify a real customer across orders,
  always use customers.customer_unique_id (group and count by customer_unique_id).
"""

class State(TypedDict):
    question: str
    sql: str
    result: str
    error: str
    answer: str
    clarification: str         
    needs_clarification: bool
    clarify_question: str
    clarify_options: list


#Create function
def clean_sql(text:str) -> str:
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE)
    return text.replace("```","").strip()


def generate_sql(state: State):
    clar = state.get("clarification", "")
    extra = f"\nUser-confirmed interpretation (follow this exactly): {clar}" if clar else ""

    prompt = f"""You are an expert SQLite analyst.

Schema:
{SCHEMA}
{Notes}

Write ONE read-only SQLite query to answer the question.
Return ONLY the SQL, no explanation.

Question: {state['question']}{extra}"""
    sql = clean_sql(llm.invoke(prompt).content)
    return {"sql": sql}




def execute(state: State):
    ok, msg, safe_sql = validate_sql(state["sql"])
    if not ok:
        return {"result": "", "error": f"Blocked: {msg}"}
    try:
        result = db.run(safe_sql)
        return {"sql": safe_sql, "result": str(result)[:3000], "error": ""}
    except Exception as e:
        return {"result": "", "error": str(e)}






VAGUE_WORDS = [
    "best", "top", "worst", "good", "bad", "popular", "important",
    "active", "loyal", "valuable", "successful", "performing",
    "recent", "latest", "biggest", "key",
]

EXPLICIT_HINTS = [
    " by ", "based on", "according to", "in terms of", "ranked by", "sorted by",
]


def looks_ambiguous(q: str) -> bool:
    ql = " " + q.lower() + " "
    has_vague = any(w in ql for w in VAGUE_WORDS)
    has_explicit = any(h in ql for h in EXPLICIT_HINTS)
    return has_vague and not has_explicit


def compact_schema() -> str:
    insp = inspect(engine)
    return "\n".join(
        f"{t}: {', '.join(c['name'] for c in insp.get_columns(t))}"
        for t in insp.get_table_names()
    )


COMPACT_SCHEMA = compact_schema()


def parse_json(text: str):
    text = text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def check_ambiguity(state: State):
    q = state["question"]

    # user already clarified, or the question looks clear
    if state.get("clarification") or not looks_ambiguous(q):
        return {"needs_clarification": False}

    prompt = f"""You help a SQL agent decide if a question is ambiguous.
A question is ambiguous ONLY if the metric or criterion is missing
(e.g. "best customer" could mean highest revenue, most orders, or highest average order value).

Database columns:
{COMPACT_SCHEMA}

Question: {q}

IMPORTANT: The user's question may be in Hindi, Hinglish or English.
Always write the clarifying question and ALL options in simple English only.

Return ONLY JSON:
{{"ambiguous": true or false,
  "question": "one short clarifying question",
  "options": ["interpretation 1", "interpretation 2", "interpretation 3"]}}

Rules: 2 to 4 options; each option must be answerable using the columns above;
put the most common interpretation FIRST."""

    try:
        data = parse_json(llm.invoke(prompt).content)
        if data.get("ambiguous") and len(data.get("options", [])) >= 2:
            return {
                "needs_clarification": True,
                "clarify_question": data["question"],
                "clarify_options": data["options"][:4],
            }
    except Exception:
        pass  # if the LLM returns bad JSON, continue normally

    return {"needs_clarification": False}






def summizer(state: State):
    if state["error"]:
        return {"answer": f"Query failed: {state['error']}"}

    clar = state.get("clarification", "")
    interp = f"\nInterpretation used: {clar}" if clar else ""

    prompt = f"""Question: {state['question']}{interp}
SQL result: {state['result']}

Give a short, clear answer in English, based only on this result.
If an interpretation was used, start with one line: "Interpretation: <interpretation>"."""
    return {"answer": llm.invoke(prompt).content}



#Create a nodes
def route_after_check(state: State):          # NAYA function
    return "ask" if state.get("needs_clarification") else "go"

g = StateGraph(State)
g.add_node("check_ambiguity", check_ambiguity)    # NAYI line
g.add_node("generate_sql", generate_sql)
g.add_node("execute", execute)
g.add_node("summarize", summizer)
g.set_entry_point("check_ambiguity")              # BADLI hui line (pehle "generate_sql" tha)
g.add_conditional_edges(                          # NAYI lines
    "check_ambiguity",
    route_after_check,
    {"ask": END, "go": "generate_sql"},
)
g.add_edge("generate_sql", "execute")
g.add_edge("execute", "summarize")
g.add_edge("summarize", END)
app = g.compile()



if __name__ == "__main__":
    while True:
        q = input("\nQuestion (type exit to quit): ").strip()
        if q.lower() == "exit":
            break

        base = {
            "question": q, "sql": "", "result": "", "error": "", "answer": "",
            "clarification": "", "needs_clarification": False,
            "clarify_question": "", "clarify_options": [],
        }
        out = app.invoke(base)

        if out.get("needs_clarification"):
            print("\n" + out["clarify_question"])
            for i, o in enumerate(out["clarify_options"], 1):
                print(f"  {i}. {o}")
            print("  0. You decide (use option 1)")
            choice = input("Option number: ").strip()
            idx = int(choice) - 1 if choice.isdigit() and int(choice) > 0 else 0
            idx = min(idx, len(out["clarify_options"]) - 1)
            out = app.invoke({**base, "clarification": out["clarify_options"][idx]})

        print("\nSQL:", out["sql"])
        print("Result:", out["result"][:300])
        print("Answer:", out["answer"])
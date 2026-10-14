# Text-to-SQL Agent

I built this to see how far an LLM can get at answering questions about a real database when you don't just trust whatever SQL it writes. You type a question in plain English, the agent writes a query, checks it, runs it, and shows you the answer along with the SQL it used. If the question is vague (like "who is the best customer?"), it asks what you mean before answering.

Live demo: https://YOUR-RENDER-LINK.onrender.com

It runs on Render's free tier, so if nobody has used it for a while the first request can take a minute to wake up.

## The data

I used the Olist Brazilian e-commerce dataset from Kaggle: about 100k orders spread over 9 tables (orders, items, payments, reviews, customers, sellers, products and so on). For the deployed version I dropped the geolocation table and the review comment text so the database fits on GitHub. None of my test questions use them.

## How it works

```
question -> is it vague? -> (ask the user to pick a meaning)
         -> LLM writes SQL -> validate -> run on read-only SQLite -> short answer
```

- LangGraph wires the steps together. The LLM is `openai/gpt-oss-120b` on Groq.
- Validation uses `sqlglot`. Only a single SELECT (or WITH / UNION) gets through, and I add a LIMIT if the query has none.
- The database connection itself is read-only (`PRAGMA query_only = ON`), so even if validation missed something, a write would fail.
- The vague-question check is a cheap keyword filter first (words like "best", "top", "worst"), and only then an LLM call that proposes 2 to 4 meanings based on the columns that actually exist.
- Backend is FastAPI. The frontend is a single HTML file with a bit of JavaScript and Chart.js. Visitors are limited to 10 questions an hour, and the whole demo to 40 a day, because the Groq free tier has a daily token cap.

## Results

I wrote 40 questions with hand-written gold SQL (8 easy, 7 joins, 5 date questions, 20 harder ones). A question counts as correct if the agent's query returns the same rows as the gold query. Row order is ignored and numbers are rounded to one decimal.

| | Easy | Join | Date | Hard | Total |
|---|---|---|---|---|---|
| Baseline | 8/8 | 7/7 | 5/5 | 19/20 | 39/40 |
| With guardrails + read-only DB | 8/8 | 7/7 | 5/5 | 19/20 | 39/40 |

The score didn't move after adding guardrails, which is what I expected, since they are there for safety and not accuracy. The hard questions include things like double counting (one order can have several items and payments), `customer_id` vs `customer_unique_id`, percentages, a month-over-month window function, and joins across four tables.

For the clarification step I used 20 separate questions, 10 vague and 10 clear. It asked a follow-up on all 10 vague ones and wrongly asked on 1 of the 10 clear ones ("What is the latest delivered order date?"). Honestly that one is arguable, because the data has three different delivery dates. I left my label alone instead of changing it to get a better number.

## Things that went wrong along the way

- **customer_id is not a customer.** In Olist, `customer_id` is generated per order. The first "best customer" answer grouped by it and was basically meaningless. I added a note to the prompt telling the model to use `customer_unique_id`.
- **My guardrail didn't actually run.** The validator passed all 10 of its unit tests, but when I tried "Drop the customers table" through the real app, it worked and the table was gone. The executor was never calling the validator. I restored the table from the CSV, fixed the wiring, and added the read-only connection as a second layer. I've since tried three destructive prompts through the full app ("Drop the customers table", "Delete all orders from the database", "Update all customer cities to Delhi") and they were blocked.
- **Some of my early "failures" were my eval, not the agent.** Three questions failed at first. One returned month `11` where my gold query returned `'11'`. Another had an ambiguous question where the agent counted more carefully than my gold SQL did. The third only differed in month format. I fixed the comparison and made those questions more specific, then re-ran.
- **I ran out of Groq tokens.** Re-running the full benchmark a few times used up the free daily limit. The eval script now reuses saved SQL, so a re-run doesn't call the LLM again.

## Run it yourself

```bash
git clone https://github.com/yuvrajsingh842007gethub/Text-to-Sql-agent.git
cd Text-to-Sql-agent
python -m venv .venv
# Windows: .venv\Scripts\activate    Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Make a `.env` file with your Groq key:

```
GROQ_API_KEY=your_key_here
```

Then:

```bash
uvicorn server:api --reload
```

and open http://127.0.0.1:8000. The demo database unpacks itself from `olist_demo.db.gz` the first time. If you want the full dataset, download the Olist CSVs into `data/` and run `python load_data.py`.

To run the benchmarks (these call the LLM, so they use tokens):

```bash
python eval/run_eval.py
python eval/run_clarify_eval.py
```

## What's not great

- It's tuned for this one dataset. The prompt has notes about Olist's tables and quirks, so a different database would need its own notes. You can't upload your own CSV.
- 40 questions is small, I wrote them myself, and the agent already scores high on them. They show it works but they won't show small improvements.
- A vague question that doesn't use words like "best" or "top" (for example "which customers matter most?") slips past the keyword filter and just gets a default interpretation.
- One benchmark question (Q29) failed with an execution error and I haven't tracked down why yet.
- Answers take anywhere from about 2 to 30 seconds, mostly model time.

## What I'd do next

- Feed SQL errors back to the model and let it retry.
- Only send the relevant tables to the model (retrieval over the schema) to cut tokens.
- Write the benchmark questions in Hinglish and messy phrasing to see how much accuracy drops.

Built by Yuvraj Singh.

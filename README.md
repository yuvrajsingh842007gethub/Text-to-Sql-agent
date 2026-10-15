# Text-to-SQL Agent

A small project where you ask questions about a database in plain English and get back the answer, the result table and the SQL that was used. If the question is vague, like "who is the best customer?", it asks what you mean first (most orders, most revenue, and so on).

Live demo: https://text-to-sql-agent-cve0.onrender.com

It's on Render's free plan, so the first request after a quiet period can take up to a minute.

## Stack

Python, LangGraph, Groq (openai/gpt-oss-120b), sqlglot, SQLite, FastAPI, plain HTML/JS with Chart.js.

## Data

The Olist Brazilian e-commerce dataset from Kaggle, about 100k orders over 9 tables. The deployed copy leaves out the geolocation table and review comments so it fits on GitHub (it's stored as `olist_demo.db.gz` and unpacked on startup).

## How it works

1. A keyword check flags vague questions. If one is flagged, the LLM suggests a few meanings based on the real columns and the user picks one.
2. The LLM writes a single SQLite query from the schema.
3. The query is checked with sqlglot: only one SELECT (WITH and UNION are fine), and a LIMIT is added if missing.
4. It runs on a read-only connection, and the LLM turns the rows into a short answer.

The read-only connection is there because of a bug I had. My validator passed its own tests, but when I tried "Drop the customers table" in the running app it went straight through, because the execute step never called the validator. I reloaded the table from the CSV, fixed that, and made the connection read-only so a write fails even if validation misses something.

The demo also limits each visitor to 10 questions an hour and the whole app to 40 a day, since the Groq free tier has a daily token cap.

## Results

I wrote 40 questions with my own gold SQL (8 easy, 7 joins, 5 dates, 20 harder ones) and compared the rows returned by the agent's query with the rows from the gold query.

| | Easy | Join | Date | Hard | Total |
|---|---|---|---|---|---|
| Agent | 8/8 | 7/7 | 5/5 | 19/20 | 39/40 |

The same score came out before and after adding the guardrails, which makes sense since they are about safety. Some of my first failures were really problems with my test (for example the month came back as 11 and my gold query had '11'), so I fixed the comparison and made a couple of questions more specific.

For the vague-question check I used a separate set of 20 questions, 10 vague and 10 clear. It asked a follow-up on all 10 vague ones and also asked on 1 of the clear ones ("What is the latest delivered order date?"), which I left as a miss.

## Run it locally

```bash
git clone https://github.com/yuvrajsingh842007gethub/Text-to-Sql-agent.git
cd Text-to-Sql-agent
python -m venv .venv
# Windows: .venv\Scripts\activate    Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Put your Groq key in a `.env` file:

```
GROQ_API_KEY=your_key_here
```

Then start it and open http://127.0.0.1:8000:

```bash
uvicorn server:api --reload
```

To use the full dataset, download the Olist CSVs into `data/` and run `python load_data.py`. The benchmarks are `python eval/run_eval.py` and `python eval/run_clarify_eval.py` (they call the LLM, so they use tokens).

## Known issues

- The prompt has notes written for Olist (which tables join, order statuses, and so on), so it won't work well on a different database without changes. There's no CSV upload.
- 40 questions is a small set and I wrote it myself, so the score shows it works but not much more than that.
- The vague-question check starts from a word list, so something like "which customers matter most?" isn't caught.
- Question 29 timed out at first. The model's query was correct but slow because my local database had no indexes on the join columns. Adding indexes fixed it.
- Answers take about 2 to 30 seconds.

## Next

Letting the model retry when its SQL errors, sending only the relevant tables to the model, and testing with Hinglish questions.

Yuvraj Singh

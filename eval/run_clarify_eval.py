import json, sys, time, os

ROOT = r"C:\Users\HP\OneDrive\Desktop\Text-to-Sql Agent"
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from agent import check_ambiguity, looks_ambiguous

questions = json.load(open("eval/clarify_questions.json", encoding="utf-8"))
results, stopped = [], False

for item in questions:
    state = {
        "question": item["q"], "sql": "", "result": "", "error": "", "answer": "",
        "clarification": "", "needs_clarification": False,
        "clarify_question": "", "clarify_options": [],
    }
    llm_called = looks_ambiguous(item["q"])
    try:
        out = check_ambiguity(state)
    except Exception as e:
        if "429" in str(e) or "rate" in str(e).lower():
            print("Rate/daily limit hit. Baad mein dobara chalao.")
            stopped = True
            break
        raise

    asked = bool(out.get("needs_clarification"))
    correct = (asked == item["ambiguous"])
    print(f"[{item['id']:>2}] expected={'ASK ' if item['ambiguous'] else 'SKIP'} "
          f"got={'ASK ' if asked else 'SKIP'} {'OK ' if correct else 'MISS'} "
          f"(LLM called: {llm_called})  {item['q']}")
    if asked:
        print("      ", out["clarify_question"], out["clarify_options"])

    results.append({**item, "asked": asked, "correct": correct, "llm_called": llm_called,
                    "options": out.get("clarify_options", [])})
    if llm_called:
        time.sleep(4)

amb = [r for r in results if r["ambiguous"]]
clr = [r for r in results if not r["ambiguous"]]
print(f"\nProcessed {len(results)}/{len(questions)}")
print(f"Clarification rate (ambiguous -> asked): {sum(r['asked'] for r in amb)}/{len(amb)}")
print(f"False-alarm rate (clear -> asked):       {sum(r['asked'] for r in clr)}/{len(clr)}")
print(f"LLM calls used: {sum(r['llm_called'] for r in results)}")

json.dump(results, open("eval/results_clarify.json", "w", encoding="utf-8"), indent=2)
import sqlglot
from sqlglot import exp

MAX_ROWS = 1000

def validate_sql(sql: str):
    """Returns (ok, message, safe_sql)"""
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        return False, "Empty query", sql
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except Exception as e:
        return False, f"SQL parse error: {e}", sql

    if len(statements) != 1:
        return False, "Only one statement is allowed", sql

    stmt = statements[0]
    if not isinstance(stmt, (exp.Select, exp.Union)):
        return False, "Only SELECT queries are allowed", sql
    if stmt.find(exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create):
        return False, "Write operations are not allowed", sql

    if isinstance(stmt, exp.Select) and not stmt.args.get("limit"):
        stmt = stmt.limit(MAX_ROWS)
    return True, "ok", stmt.sql(dialect="sqlite")
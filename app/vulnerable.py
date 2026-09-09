'''
This is a demonstartion of a vulnerable system
- Takes a question
- Asks llm.py for SQL,
- runs that SQL against the database, returns the rows.

'''

from .db import run_sql
from .llm import get_sql_from_llm
# python -m app.db in terminal tells us what is in the table if forgotten

def run_vulnerable(question: str) -> dict:
    sql = get_sql_from_llm(question)
    rows = run_sql(sql)
    return {"sql": sql, "rows": rows, "error": None}

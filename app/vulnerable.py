'''
This is a demonstartion of a vulnerable system
- Takes a question
- Asks llm.py for SQL,
- runs that SQL against the database, returns the rows.

'''

from .db import run_sql
# python -m app.db in terminal tells us what is in the table if forgotten

usr_question = "SELECT * FROM customers"
def run_vulnerable(question: str) -> dict:
    sql_test = question
    rows = run_sql(sql_test)
    print(rows)
    return rows

run_vulnerable(usr_question)
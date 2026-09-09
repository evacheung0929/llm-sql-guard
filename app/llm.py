'''

This piece of code talks to calude api, returninig SQL

'''

import os
import re

from dotenv import load_dotenv
import anthropic

# reads .env and copies the values into os.environ
load_dotenv()
API_Key = os.environ.get('ANTHROPIC_API_KEY')
anthropic_client = anthropic.Client(api_key=API_Key)


SQL_SCHEMA = """
customers(id, name, email, created_at)
accounts(id, customer_id, sort_code, account_number, balance)
transactions(id, account_id, ts, description, amount)
support_notes(id, customer_id, note)
audit_log(id, ts, actor, action)
"""


def get_sql_from_llm(question: str) -> str:
    message_content = f"""  You are a SQL assistant for a retail bank's customer app with SQLite. Here to help to answer customer's question

                            Use only these tables and columns:
                            {SQL_SCHEMA}

                            Customer question: {question}

                            The logged-in user is customer_id = 1. 
                            Return only the SQL statement. Do not include Markdown fences, comments, explanations, or alternative queries.
                        """
    message = anthropic_client.messages.create(
        model="claude-haiku-4-5",
        messages=[{"role": "user", "content": message_content}],
        max_tokens=100,
    )
    response = message.content[0].text.strip()
    match = re.search(r"```(?:sql)?\s*(.*?)```", response, re.IGNORECASE | re.DOTALL)
    sql = (match.group(1) if match else response).strip()
    print(sql)
    return sql

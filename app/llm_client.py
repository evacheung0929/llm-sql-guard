"""
Text-to-SQL step: calls the Claude API to translate a natural-language
question into a single SQL SELECT statement against the banking schema.

This is the actual attack surface for "LLM SQL injection": if a user's
natural-language input can steer the model into emitting SQL beyond a
simple SELECT (via prompt injection), that SQL reaches sql_guard.py before
main.py decides whether to execute it. The system prompt below is a
first line of defence, not a guarantee — sql_guard.py is the real backstop.
"""
import os

from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

SCHEMA_DESCRIPTION = """\
customers(id, name, email, account_number, sort_code, created_at)
accounts(id, customer_id, account_type, balance, currency, created_at)
transactions(id, account_id, transaction_type, amount, recipient_name, recipient_account, reference, status, created_at)
"""

SYSTEM_PROMPT = f"""You are a SQL generation assistant for a UK retail banking database (SQLite).

Schema:
{SCHEMA_DESCRIPTION}
Rules:
- Output ONLY a single SQL SELECT statement — no explanation, no markdown fences, no comments.
- Never write more than one statement.
- Never use DROP, DELETE, INSERT, UPDATE, ALTER, CREATE, ATTACH, or PRAGMA.
- Only reference the tables listed above.

Convert the user's question into one SQL SELECT query."""

_client: Optional[Anthropic] = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        _client = Anthropic(api_key=API_KEY)
    return _client


def generate_sql(user_question: str) -> str:
    """Call Claude to translate a natural-language question into SQL."""
    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_question}],
    )
    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return _strip_markdown_fences(text.strip())


def _strip_markdown_fences(text: str) -> str:
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text

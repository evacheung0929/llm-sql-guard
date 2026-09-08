"""
Database setup: schema + synthetic UK banking data.

This is the target database for the text-to-SQL pipeline in llm_client.py /
main.py. It is intentionally realistic (customers, accounts, transactions)
so that generated SQL and injection attempts have something meaningful to
return.
"""
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# app/db.py -> app/ -> project root
DATABASE_PATH = Path(__file__).resolve().parent.parent / "banking.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    account_number TEXT UNIQUE NOT NULL,
    sort_code TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    account_type TEXT NOT NULL,
    balance REAL DEFAULT 0.0,
    currency TEXT DEFAULT 'GBP',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    amount REAL NOT NULL,
    recipient_name TEXT,
    recipient_account TEXT,
    reference TEXT,
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_input TEXT,
    generated_sql TEXT NOT NULL,
    is_safe BOOLEAN,
    guard_issues TEXT,
    executed BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

UK_NAMES = [
    "Alice Johnson", "Bob Smith", "Catherine Brown", "David Miller",
    "Emma Wilson", "Frank Davis", "Grace Lee", "Henry Taylor",
]

UK_EMAILS = [
    "alice.johnson@email.com", "bob.smith@email.com", "catherine.b@email.com",
    "david.miller@email.com", "emma.wilson@email.com", "frank.davis@email.com",
    "grace.lee@email.com", "henry.taylor@email.com",
]


def generate_sort_code() -> str:
    return f"{random.randint(10, 99)}-{random.randint(10, 99)}-{random.randint(10, 99)}"


def generate_account_number() -> str:
    return f"{random.randint(10000000, 99999999)}"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(seed: bool = True) -> None:
    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript(SCHEMA)

    if seed:
        cursor.execute("SELECT COUNT(*) FROM customers")
        if cursor.fetchone()[0] > 0:
            conn.close()
            return  # already seeded

        customer_ids = []
        for name, email in zip(UK_NAMES, UK_EMAILS):
            cursor.execute(
                "INSERT INTO customers (name, email, account_number, sort_code) "
                "VALUES (?, ?, ?, ?)",
                (name, email, generate_account_number(), generate_sort_code()),
            )
            customer_ids.append(cursor.lastrowid)

        account_ids = []
        account_types = ["Current", "Savings", "Business"]
        for customer_id in customer_ids:
            for account_type in account_types[: random.randint(1, 2)]:
                cursor.execute(
                    "INSERT INTO accounts (customer_id, account_type, balance) "
                    "VALUES (?, ?, ?)",
                    (customer_id, account_type, round(random.uniform(100, 50000), 2)),
                )
                account_ids.append(cursor.lastrowid)

        base_date = datetime.now() - timedelta(days=90)
        transaction_types = ["Transfer", "Deposit", "Withdrawal", "Payment"]
        recipients = ["ACME Corp", "Utility Provider", "Salary Payment", "Freelance Invoice"]
        for account_id in account_ids:
            for _ in range(random.randint(3, 8)):
                cursor.execute(
                    "INSERT INTO transactions "
                    "(account_id, transaction_type, amount, recipient_name, reference, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        account_id,
                        random.choice(transaction_types),
                        round(random.uniform(10, 5000), 2),
                        random.choice(recipients),
                        f"REF-{random.randint(100000, 999999)}",
                        base_date + timedelta(days=random.randint(0, 90)),
                    ),
                )

    conn.commit()
    conn.close()


def log_query(user_input: str, generated_sql: str, is_safe: bool, issues: list, executed: bool) -> None:
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_logs (user_input, generated_sql, is_safe, guard_issues, executed) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_input, generated_sql, is_safe, "; ".join(issues), executed),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
    init_db()
    print(f"Database initialised at {DATABASE_PATH}")

"""
Schema + synthetic UK banking data for the LLM-to-SQL Injection Lab.

Schema is fixed by the threat model and must not drift: app/llm.py describes
these exact tables to the model, T3's attacks target support_notes (stored
injection) and audit_log (destructive SQL), and T11's harness checks whether
audit_log still exists after an attack run.

NOTE: this module deliberately provides no query-logging helper. "No logging
of generated SQL" is flaw #6 of the v1 pipeline. audit_log exists as a table
the *bank* writes to, and as a target an attacker can destroy — not as a
record of this assistant's activity.
"""
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "bank.db"

# Session customer. The declared boundary is that only this customer's data
# may ever be returned. In v1 that boundary is enforced only by a sentence
# of English in the system prompt (flaw #4).
SESSION_CUSTOMER_ID = 1

SCHEMA = """
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS support_notes;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);

CREATE TABLE accounts (
    id              INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    sort_code       TEXT NOT NULL,
    account_number  TEXT NOT NULL,
    balance         REAL NOT NULL
);

CREATE TABLE transactions (
    id           INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES accounts(id),
    ts           TEXT NOT NULL,
    description  TEXT NOT NULL,
    amount       REAL NOT NULL
);

CREATE TABLE support_notes (
    id           INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(id),
    note         TEXT NOT NULL
);

CREATE TABLE audit_log (
    id      INTEGER PRIMARY KEY,
    ts      TEXT NOT NULL,
    actor   TEXT NOT NULL,
    action  TEXT NOT NULL
);
"""

CUSTOMERS = [
    (1, "Eleanor Whitfield", "e.whitfield@example.co.uk"),
    (2, "Rajiv Chandran",    "r.chandran@example.co.uk"),
    (3, "Fiona MacLeod",     "f.macleod@example.co.uk"),
    (4, "Tomasz Nowak",      "t.nowak@example.co.uk"),
    (5, "Adaeze Okafor",     "a.okafor@example.co.uk"),
]

# customer_id -> how many accounts (5 customers, 8 accounts total)
ACCOUNTS_PER_CUSTOMER = {1: 2, 2: 2, 3: 2, 4: 1, 5: 1}

DESCRIPTIONS = [
    "TESCO STORES 3412", "TFL TRAVEL CHARGE", "PRET A MANGER 88",
    "OCTOPUS ENERGY DD", "THAMES WATER DD", "SPOTIFY UK", "AMAZON.CO.UK",
    "SALARY - NORTHGATE LTD", "TRANSFER TO SAVINGS", "BOOTS 2201",
    "GREGGS 1140", "COUNCIL TAX DD", "VITALITY HEALTH DD", "SAINSBURYS 0921",
]

SUPPORT_NOTES = [
    (1, "Customer called about a duplicate direct debit on 14 Aug. Resolved, refund issued."),
    (1, "Address change requested; documents verified by branch staff."),
    (2, "Reported card lost while travelling. Replacement card despatched."),
    (3, "Disputed a contactless payment of GBP 42.10. Under investigation."),
    (4, "Requested an increase to the daily transfer limit. Declined pending review."),
    (5, "Asked about switching to a joint account. Information pack sent."),
]

AUDIT_LOG = [
    ("system",        "nightly_reconciliation completed"),
    ("j.patel",       "viewed customer 3 profile"),
    ("system",        "interest accrual posted"),
    ("s.hargreaves",  "approved card replacement for customer 2"),
    ("system",        "statement generation completed"),
]


def get_conn() -> sqlite3.Connection:
    """Read/WRITE connection. Least privilege is not applied in v1 (flaw #3).

    Deliberately no row_factory: rows come back as plain tuples, which are
    JSON-serialisable straight out of cursor.fetchall().
    """
    return sqlite3.connect(DB_PATH)

def run_sql(sql: str) -> list[tuple]:
    """Run the SQL against the database and return the rows.

    Deliberately no validation, no authorisation, no logging: flaw #3.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    conn.commit()
    conn.close()
    return rows

def seed() -> None:
    """Drop every table and recreate it with fresh synthetic data.

    Destructive and idempotent by design: T3/T11 need a known-good state to
    reset to after an attack has dropped or mutated a table.
    """
    rng = random.Random(42)  # deterministic, so attack evidence is reproducible
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    base = datetime(2026, 6, 1)

    for cid, name, email in CUSTOMERS:
        cur.execute(
            "INSERT INTO customers (id, name, email, created_at) VALUES (?, ?, ?, ?)",
            (cid, name, email, (base - timedelta(days=rng.randint(400, 2000))).isoformat(sep=" ", timespec="seconds")),
        )

    account_ids: list[int] = []
    next_account_id = 1
    for cid, _, _ in CUSTOMERS:
        for _ in range(ACCOUNTS_PER_CUSTOMER[cid]):
            cur.execute(
                "INSERT INTO accounts (id, customer_id, sort_code, account_number, balance) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    next_account_id,
                    cid,
                    f"{rng.randint(20, 60):02d}-{rng.randint(10, 99):02d}-{rng.randint(10, 99):02d}",
                    f"{rng.randint(10000000, 99999999)}",
                    round(rng.uniform(85.0, 24500.0), 2),
                ),
            )
            account_ids.append(next_account_id)
            next_account_id += 1

    # ~50 transactions spread across the 8 accounts
    for i in range(50):
        account_id = account_ids[i % len(account_ids)]
        description = rng.choice(DESCRIPTIONS)
        if description.startswith("SALARY"):
            amount = round(rng.uniform(1800, 3400), 2)
        else:
            amount = -round(rng.uniform(2.40, 320.0), 2)
        cur.execute(
            "INSERT INTO transactions (account_id, ts, description, amount) VALUES (?, ?, ?, ?)",
            (
                account_id,
                (base + timedelta(days=rng.randint(0, 89), minutes=rng.randint(0, 1439)))
                .isoformat(sep=" ", timespec="seconds"),
                description,
                amount,
            ),
        )

    cur.executemany(
        "INSERT INTO support_notes (customer_id, note) VALUES (?, ?)", SUPPORT_NOTES
    )

    for offset, (actor, action) in enumerate(AUDIT_LOG):
        cur.execute(
            "INSERT INTO audit_log (ts, actor, action) VALUES (?, ?, ?)",
            ((base + timedelta(days=offset)).isoformat(sep=" ", timespec="seconds"), actor, action),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed()
    conn = get_conn()
    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("customers", "accounts", "transactions", "support_notes", "audit_log")
    }
    conn.close()
    print(f"Seeded {DB_PATH}")
    for table, n in counts.items():
        print(f"  {table:<14} {n}")

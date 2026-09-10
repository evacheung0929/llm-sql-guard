# llm-sql-guard
* Note this is an on-goinging project, detail documentation and code will slowly be added 

A deliberately vulnerable natural-language-to-SQL banking assistant, built to study a specific failure mode: **what happens when authorisation is expressed as a sentence in a system prompt instead of enforced in the data layer.**

> ⚠️ **v1 is intentionally insecure.** It executes model-generated SQL without validation and renders results without escaping. It runs against a synthetic local database and must never be deployed or pointed at real data.

---

## Why this exists

Retail banks are actively shipping LLM assistants that answer customer questions over account data. The common architecture is: user asks a question in English → an LLM writes SQL → the application runs it → rows come back.

That architecture has a quiet assumption buried in it. Somewhere, something has to guarantee that customer A can only ever see customer A's data. In a lot of early implementations, that guarantee lives in the system prompt — a line like `The logged-in user is customer_id = 1.`

This project builds that architecture honestly, at its most naive, and tests whether the guarantee holds.

**It does not.** A sentence of English is not an access control. This repository is the reproducible demonstration of why, and — in v2 — the enforcement layer that should have been there instead.

---

## Threat model

| | |
|---|---|
| **Asset** | The synthetic customer database: names, emails, sort codes, account numbers, balances, transaction history, support notes, audit log. |
| **Declared boundary** | `SESSION_CUSTOMER_ID = 1`. Only this customer's data may ever be returned. |
| **How the boundary is enforced in v1** | Only by a sentence in the system prompt (`app/llm.py`). There is no check anywhere in the data layer. |
| **Attacker** | An ordinary end user of the chat interface. No credentials, no network position, no access to the host. Their only capability is typing into a textarea. |
| **Attacker's goal** | Read data belonging to customers ≠ 1; read or destroy the `audit_log`; achieve code execution in another user's browser. |
| **Out of scope (v1)** | Host compromise, model weight extraction, denial of service, supply-chain attacks on dependencies. |

The point of interest is the **asymmetry**: the attacker's only tool is natural language, and the defence is also natural language. Nothing in the stack arbitrates between them.

---

## Architecture (v1)

```
   Browser (static/index.html)
        │  POST /ask  { "question": "..." }
        ▼
   FastAPI (app/main.py)
        │
        ▼
   app/vulnerable.py  ── run_vulnerable(question)
        │
        ├──► app/llm.py    get_sql_from_llm()   Claude (claude-haiku-4-5)
        │                  schema + "user is customer_id = 1" + question
        │                  returns: a raw SQL string
        │
        └──► app/db.py     run_sql(sql)          SQLite (bank.db)
                           executed unconditionally
        │
        ▼
   { sql, rows, error }  ──► rendered into the DOM via innerHTML
```

The entire pipeline is four files and about 400 lines. That is deliberate — the vulnerability should be legible, not buried.

The control flow that matters is two lines, in `app/vulnerable.py`:

```python
sql = get_sql_from_llm(question)   # the model writes arbitrary SQL
rows = run_sql(sql)                # ...which is executed, unconditionally
```

There is no step between them. That absence is the project.


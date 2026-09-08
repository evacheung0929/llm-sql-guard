"""
Defensive analysis of LLM-generated SQL, using sqlglot to parse the query
into an AST rather than pattern-matching on substrings (easy to evade).

Checks: exactly one statement, SELECT-only, only known tables, no UNION,
no tautological WHERE clause.
"""
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

DIALECT = "sqlite"
ALLOWED_TABLES = {"customers", "accounts", "transactions"}


@dataclass
class GuardReport:
    is_safe: bool
    statement_count: int
    tables_referenced: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def analyse(sql: str) -> GuardReport:
    """Parse `sql` and return a report of any structural red flags."""
    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except Exception as exc:  # sqlglot raises ParseError subclasses
        return GuardReport(is_safe=False, statement_count=0, issues=[f"Unparseable SQL: {exc}"])

    issues: list[str] = []
    if len(statements) != 1:
        issues.append(
            f"Expected exactly 1 statement, found {len(statements)} "
            "(possible stacked-query injection)"
        )

    tables_referenced: set[str] = set()
    for stmt in statements:
        if not isinstance(stmt, exp.Select):
            issues.append(f"Disallowed statement type: {type(stmt).__name__} (only SELECT is permitted)")

        for table in stmt.find_all(exp.Table):
            tables_referenced.add(table.name)

        if stmt.find(exp.Union):
            issues.append("UNION detected — possible data exfiltration via UNION-based injection")

        for eq in stmt.find_all(exp.EQ):
            left, right = eq.this, eq.expression
            if isinstance(left, exp.Literal) and isinstance(right, exp.Literal) and left.this == right.this:
                issues.append(f"Tautology detected in WHERE clause: {eq.sql(dialect=DIALECT)}")

    unknown_tables = tables_referenced - ALLOWED_TABLES
    if unknown_tables:
        issues.append(f"References tables outside the expected schema: {sorted(unknown_tables)}")

    return GuardReport(
        is_safe=len(issues) == 0,
        statement_count=len(statements),
        tables_referenced=sorted(tables_referenced),
        issues=issues,
    )

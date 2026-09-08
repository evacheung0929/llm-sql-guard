"""
FastAPI backend for the LLM SQL Guard mini-project.

POST /ask pipeline:
  1. question -> llm_client.generate_sql()   Claude generates SQL
  2. generated SQL -> sql_guard.analyse()    sqlglot checks its structure
  3. log the attempt to audit_logs
  4. enforce_guard=True and unsafe -> block
     enforce_guard=False (default)  -> execute anyway, to show what an
     undefended pipeline would have done
"""
import sqlite3
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .db import DATABASE_PATH, get_db, init_db, log_query
from .sql_guard import analyse
from . import llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DATABASE_PATH.exists():
        init_db()
    yield


app = FastAPI(
    title="LLM SQL Guard",
    description="Text-to-SQL pipeline with sqlglot-based injection detection",
    lifespan=lifespan,
)


class AskRequest(BaseModel):
    question: str
    enforce_guard: bool = False


class AskResponse(BaseModel):
    success: bool
    question: str
    generated_sql: Optional[str] = None
    guard: Optional[dict] = None
    executed: bool = False
    blocked_reason: Optional[str] = None
    results: list = []
    error: Optional[str] = None


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    question = request.question.strip()
    if not question:
        return AskResponse(success=False, question=question, error="Question cannot be empty")

    try:
        generated_sql = llm_client.generate_sql(question)
    except Exception as exc:
        return AskResponse(success=False, question=question, error=f"LLM generation failed: {exc}")

    report = analyse(generated_sql)
    guard_dict = {
        "is_safe": report.is_safe,
        "statement_count": report.statement_count,
        "tables_referenced": report.tables_referenced,
        "issues": report.issues,
    }

    if request.enforce_guard and not report.is_safe:
        log_query(question, generated_sql, report.is_safe, report.issues, executed=False)
        return AskResponse(
            success=False,
            question=question,
            generated_sql=generated_sql,
            guard=guard_dict,
            blocked_reason="Blocked by sql_guard: " + "; ".join(report.issues),
        )

    log_query(question, generated_sql, report.is_safe, report.issues, executed=True)
    try:
        conn = get_db()
        rows = [dict(row) for row in conn.execute(generated_sql).fetchall()]
        conn.close()
        return AskResponse(
            success=True,
            question=question,
            generated_sql=generated_sql,
            guard=guard_dict,
            executed=True,
            results=rows,
        )
    except sqlite3.Error as exc:
        return AskResponse(
            success=False,
            question=question,
            generated_sql=generated_sql,
            guard=guard_dict,
            executed=True,
            error=f"SQL execution error: {exc}",
        )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "database_exists": DATABASE_PATH.exists()}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    return FRONTEND_HTML


FRONTEND_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LLM SQL Guard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; }
  .container { max-width: 1100px; margin: 0 auto; padding: 2rem; }
  h1 { font-size: 1.8rem; margin-bottom: 0.25rem; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 1.5rem; }
  .banner { background: #7c2d12; border-left: 4px solid #ea580c; padding: 0.9rem; margin-bottom: 1.5rem; border-radius: 0.4rem; font-size: 0.85rem; }
  .panel { background: #1e293b; padding: 1.4rem; border-radius: 0.6rem; margin-bottom: 1.5rem; }
  textarea { width: 100%; padding: 0.7rem; background: #0f172a; color: #e2e8f0; border: 1px solid #475569; border-radius: 0.4rem; font-family: 'Courier New', monospace; font-size: 0.9rem; min-height: 90px; }
  .row { display: flex; align-items: center; gap: 0.6rem; margin-top: 0.8rem; }
  label { font-size: 0.85rem; color: #cbd5e1; }
  button { padding: 0.6rem 1.3rem; border: none; border-radius: 0.4rem; font-size: 0.95rem; cursor: pointer; background: #3b82f6; color: white; }
  button:hover { background: #2563eb; }
  pre { white-space: pre-wrap; word-break: break-word; background: #0f172a; padding: 0.8rem; border-radius: 0.4rem; font-size: 0.82rem; margin-top: 0.6rem; }
  .safe { color: #86efac; } .unsafe { color: #fca5a5; }
  table { width: 100%; border-collapse: collapse; margin-top: 0.8rem; font-size: 0.85rem; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #334155; }
  th { background: #0f172a; }
  .hidden { display: none; }
</style>
</head>
<body>
<div class="container">
  <h1>LLM SQL Guard</h1>
  <p class="subtitle">Text-to-SQL via Claude, validated with a sqlglot-based structural guard</p>
  <div class="banner">Security research tool. Toggle "Enforce guard" off to observe unguarded execution, on to see it blocked.</div>

  <div class="panel">
    <textarea id="question" placeholder="e.g. Show me all transactions over 1000 pounds"></textarea>
    <div class="row">
      <input type="checkbox" id="enforceGuard">
      <label for="enforceGuard">Enforce guard (block unsafe SQL instead of executing it)</label>
    </div>
    <div class="row">
      <button onclick="ask()">Ask</button>
    </div>
  </div>

  <div class="panel hidden" id="output">
    <div id="status"></div>
    <div><strong>Generated SQL</strong><pre id="sql"></pre></div>
    <div><strong>Guard report</strong><pre id="guard"></pre></div>
    <div id="resultsWrap"></div>
  </div>
</div>

<script>
async function ask() {
  const question = document.getElementById('question').value.trim();
  const enforce_guard = document.getElementById('enforceGuard').checked;
  if (!question) { alert('Enter a question'); return; }

  const res = await fetch('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, enforce_guard })
  });
  const data = await res.json();

  document.getElementById('output').classList.remove('hidden');
  const statusEl = document.getElementById('status');
  if (data.blocked_reason) {
    statusEl.innerHTML = `<p class="unsafe">BLOCKED: ${escapeHtml(data.blocked_reason)}</p>`;
  } else if (data.error) {
    statusEl.innerHTML = `<p class="unsafe">ERROR: ${escapeHtml(data.error)}</p>`;
  } else if (data.success) {
    statusEl.innerHTML = `<p class="safe">Executed. ${data.results.length} row(s) returned.</p>`;
  }

  document.getElementById('sql').textContent = data.generated_sql || '(none)';
  document.getElementById('guard').textContent = data.guard ? JSON.stringify(data.guard, null, 2) : '(none)';

  const wrap = document.getElementById('resultsWrap');
  wrap.innerHTML = '';
  if (data.results && data.results.length) {
    const keys = Object.keys(data.results[0]);
    let html = '<table><thead><tr>' + keys.map(k => `<th>${escapeHtml(k)}</th>`).join('') + '</tr></thead><tbody>';
    for (const row of data.results) {
      html += '<tr>' + keys.map(k => `<td>${escapeHtml(String(row[k]))}</td>`).join('') + '</tr>';
    }
    html += '</tbody></table>';
    wrap.innerHTML = html;
  }
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return text.replace(/[&<>"']/g, m => map[m]);
}
</script>
</body>
</html>
"""

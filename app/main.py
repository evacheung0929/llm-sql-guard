"""
FastAPI shell for the v1 (deliberately vulnerable) NL->SQL assistant.

This file is intentionally thin. It does no validation, no authorisation and
no logging of its own — all of that is either absent by design in v1, or
lives in app/vulnerable.py, which you write.

    GET  /      -> static/index.html
    POST /ask   -> {"question": str} -> app.vulnerable.run_vulnerable(question)
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="LLM-to-SQL Injection Lab (v1, vulnerable)",
    description="Deliberately vulnerable NL->SQL banking assistant. Do not deploy.",
)


class AskRequest(BaseModel):
    question: str


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/ask")
async def ask(request: AskRequest) -> dict:
    # Imported lazily so the page still serves before app/vulnerable.py exists.
    try:
        from .vulnerable import run_vulnerable
    except ImportError as exc:
        return {
            "sql": None,
            "rows": [],
            "error": f"app/vulnerable.py is not ready yet ({exc}). This file is yours to write (T2).",
        }

    try:
        return run_vulnerable(request.question)
    except Exception as exc:
        # v1 leaks the raw error to the client. Deliberate: error messages are
        # a reconnaissance channel, and you want to see them while attacking.
        return {"sql": None, "rows": [], "error": f"{type(exc).__name__}: {exc}"}

"""
app/llm — the ONLY place in the project that talks to a model.

Everyone (classification, extraction, maker, checker) calls:

    from app.llm import complete
    result: dict = complete(prompt, schema)

and gets back a dict that matches `schema` (a JSON Schema). Nobody imports
anthropic or runs `claude` themselves. Why one entry point:
  * we switch backends with one env var, without touching anyone's code;
  * replay mode makes tests and the demo run with no Wi-Fi and no account;
  * every call is recorded, so the audit log can say which model answered.

Backends, picked by LLM_BACKEND:
  replay  answers recorded in fixtures/llm/<hash>.json (default: safe for tests)
  cli     `claude -p` on the demo laptop's subscription
  api     Anthropic SDK with ANTHROPIC_API_KEY (for the jury)

LLM_RECORD=1 with cli/api also saves each answer into fixtures/llm/, which is
how we build the replay set: run once live, commit the fixtures.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "llm"
MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5-5")
TIMEOUT_S = int(os.getenv("LLM_TIMEOUT_S", "60"))


class LLMError(RuntimeError):
    """Raised when a backend fails or returns something that isn't valid JSON."""


def _key(prompt: str, schema: dict) -> str:
    # Same prompt + same schema -> same file. sort_keys so dict order doesn't matter.
    blob = prompt + "\n" + json.dumps(schema, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _replay(prompt: str, schema: dict) -> dict:
    path = FIXTURES / f"{_key(prompt, schema)}.json"
    if not path.exists():
        # Fail loudly: a missing recording means the prompt changed and must be re-recorded.
        raise LLMError(f"No recorded answer for this prompt: {path.name}. "
                       "Run once with LLM_BACKEND=cli LLM_RECORD=1.")
    return json.loads(path.read_text(encoding="utf-8"))["answer"]


def _cli(prompt: str, schema: dict) -> dict:
    # Flags from the team plan. Check `claude --help` on the demo laptop once:
    # if the output shape differs, only this function changes.
    cmd = ["claude", "-p", prompt,
           "--output-format", "json",
           "--json-schema", json.dumps(schema),
           "--tools", "",
           "--no-session-persistence"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S, check=True)
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise LLMError(f"claude CLI failed: {e}") from e
    envelope = json.loads(out.stdout)
    # With a schema the answer is in structured_output; otherwise it's text in "result".
    if isinstance(envelope, dict) and "structured_output" in envelope:
        return envelope["structured_output"]
    return json.loads(envelope["result"])


def _api(prompt: str, schema: dict) -> dict:
    import anthropic  # imported here so replay mode needs no SDK installed

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    # Forcing a single tool whose input_schema is our schema is the reliable way
    # to get JSON in exactly that shape.
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[{"name": "answer", "description": "Return the answer.", "input_schema": schema}],
        tool_choice={"type": "tool", "name": "answer"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in msg.content:
        if block.type == "tool_use":
            return block.input
    raise LLMError("API returned no tool_use block")


_BACKENDS = {"replay": _replay, "cli": _cli, "api": _api}


def complete(prompt: str, schema: dict[str, Any]) -> dict:
    """Ask the model; return a dict matching `schema`."""
    backend = os.getenv("LLM_BACKEND", "replay")
    if backend not in _BACKENDS:
        raise LLMError(f"Unknown LLM_BACKEND={backend!r}; use replay, cli or api")
    answer = _BACKENDS[backend](prompt, schema)

    if backend != "replay" and os.getenv("LLM_RECORD") == "1":
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / f"{_key(prompt, schema)}.json").write_text(
            json.dumps({"model": MODEL, "backend": backend, "answer": answer},
                       ensure_ascii=False, indent=2), encoding="utf-8")
    return answer


def current_model() -> str:
    """For the audit log: which model answered."""
    return "replay" if os.getenv("LLM_BACKEND", "replay") == "replay" else MODEL

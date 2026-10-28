"""The model interface in replay mode: no network, no account."""
import json

import pytest

import app.llm as llm

SCHEMA = {"type": "object", "properties": {"type": {"type": "string"}}, "required": ["type"]}


def test_replay_returns_recorded_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "FIXTURES", tmp_path)
    monkeypatch.setenv("LLM_BACKEND", "replay")
    prompt = "Classify this page: BILANȚ la 31.12.2024"
    (tmp_path / f"{llm._key(prompt, SCHEMA)}.json").write_text(
        json.dumps({"answer": {"type": "bilant"}}), encoding="utf-8")
    assert llm.complete(prompt, SCHEMA) == {"type": "bilant"}


def test_replay_missing_recording_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "FIXTURES", tmp_path)
    monkeypatch.setenv("LLM_BACKEND", "replay")
    with pytest.raises(llm.LLMError):
        llm.complete("never recorded", SCHEMA)


def test_unknown_backend(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "gpt")
    with pytest.raises(llm.LLMError):
        llm.complete("x", SCHEMA)

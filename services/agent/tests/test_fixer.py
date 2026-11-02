import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import types

from sherpa.fixer import agent as fixer_agent
from sherpa.fixer.agent import run_fixer, self_check
from sherpa.fixer.pr import pr_body
from sherpa.fixer.tools import ToolError, Workspace

STORES = Path(__file__).resolve().parents[3] / "demo-stores"


@pytest.fixture
def ember(tmp_path):
    dest = tmp_path / "ember-oak"
    shutil.copytree(STORES / "ember-oak", dest, ignore=shutil.ignore_patterns("node_modules"))
    return Workspace(dest)


def test_workspace_blocks_escape_and_secrets(ember):
    with pytest.raises(ToolError):
        ember.read_file("../../etc/passwd")
    with pytest.raises(ToolError):
        ember.write_file(".env", "X=1")
    with pytest.raises(ToolError):
        ember.list_dir("node_modules")
    ember.write_file(".env.example", "PAYPAL_CLIENT_ID=")


def test_apply_patch_requires_unique_match(ember):
    with pytest.raises(ToolError):
        ember.apply_patch("server.js", "res", "x")
    assert ember.apply_patch("server.js", "const PORT = process.env.PORT || 8080;", "const PORT = 8080;")
    assert "server.js" in ember.changed


def test_self_check_flags_every_baseline_problem(ember):
    problems = " ".join(self_check(ember))
    for needle in (
        "legacy SDK",
        "Venmo",
        "Pay Later",
        "client-supplied total",
        "verify-webhook-signature",
        "role=",
    ):
        assert needle in problems


def _response(*parts):
    return SimpleNamespace(
        candidates=[SimpleNamespace(content=types.Content(role="model", parts=list(parts)))]
    )


def _call(name, **args):
    return types.Part(function_call=types.FunctionCall(name=name, args=args))


async def test_agent_loop_requires_build_and_self_check(ember, monkeypatch):
    script = [
        _response(_call("read_file", path="server.js")),
        _response(_call("finish", summary="done", changes=[])),  # rejected: no build yet
        _response(_call("finish", summary="done", changes=[])),  # rejected again
        _response(_call("finish", summary="done", changes=[])),
        _response(_call("finish", summary="done", changes=[])),
    ]
    calls = {"n": 0}

    async def fake_generate(model, contents, config):
        calls["n"] += 1
        return script.pop(0)

    async def no_refs():
        return ""

    events = []

    async def emit(kind, **data):
        events.append((kind, data))

    monkeypatch.setattr(fixer_agent, "generate", fake_generate)
    monkeypatch.setattr(fixer_agent, "load_references", no_refs)
    outcome = await run_fixer(ember, [], emit)
    assert outcome.model_calls == 5
    assert outcome.summary == "done"
    assert outcome.build_ok is False
    assert outcome.unresolved  # still reports what was not fixed
    assert any(k == "tool" and d["tool"] == "read_file" for k, d in events)


def test_pr_body_has_no_assistant_attribution():
    audit = {
        "total": 15,
        "categories": {"presentment": {"score": 0, "max": 20}},
        "findings": [
            {
                "code": "SDK_LEGACY",
                "severity": "high",
                "title": "Legacy SDK",
                "fix": "Upgrade",
                "evidence": {},
            }
        ],
    }
    outcome = SimpleNamespace(
        summary="Upgraded checkout.",
        changes=[{"finding": "SDK_LEGACY", "change": "v6"}],
        files_changed=["views/cart.html"],
    )
    body = pr_body(audit, outcome, "https://store.example")
    assert "Opened by Sherpa" in body
    assert "| 🟠 high | Legacy SDK | v6 |" in body
    lowered = body.lower()
    for word in ("gemini", "co-authored", "generated with"):
        assert word not in lowered


async def test_file_events_stream_content_and_diffs(ember):
    from sherpa.fixer.agent import emit_file

    events = []

    async def emit(kind, **data):
        events.append((kind, data))

    await emit_file(emit, ember, "server.js", "read", None)
    before = ember.peek("server.js")
    ember.apply_patch(
        "server.js",
        "const PORT = process.env.PORT || 8080;",
        "const PORT = Number(process.env.PORT) || 8080;",
    )
    await emit_file(emit, ember, "server.js", "edit", before)
    ember.write_file("routes/new.js", "module.exports = 1;\n")
    await emit_file(emit, ember, "routes/new.js", "create", None)

    read, edit, create = (d for _, d in events)
    assert read["action"] == "read" and "express" in read["content"] and read["diff"] == ""
    assert edit["diff"].startswith("diff --git a/server.js b/server.js")
    assert "+const PORT = Number(process.env.PORT) || 8080;" in edit["diff"]
    assert create["action"] == "create" and "+module.exports = 1;" in create["diff"]

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app import config
from app.llm import runner
from app.llm.runner import LLMError, strict_schema
from app.schemas import Profile

EXTRACTED = {
    "full_name": "Ali Veli",
    "headline": "Backend &amp; Data Developer",
    "email": None,
    "phone": None,
    "location": "İstanbul",
    "links": [],
    "summary": None,
    "experience": [
        {
            "company": "Örnek A.Ş.",
            "title": "Backend Developer",
            "location": None,
            "start_date": "2024-02",
            "end_date": None,
            "bullets": ["API yazdım."],
            "skills": ["Python"],
        }
    ],
    "education": [],
    "skills": {"languages": ["Python"], "frameworks": [], "tools": ["Docker"]},
    "languages": [],
    "certifications": [],
}


def _fake_cli(monkeypatch, provider: str, handler) -> list:
    """Replace the subprocess call with `handler(cmd) -> (returncode, stdout)`.
    Works on every OS; the binary itself is Python so it always resolves."""
    calls = []

    def fake_run(cmd, stdin, cwd, timeout=None):
        calls.append({"cmd": cmd, "stdin": stdin, "timeout": timeout})
        code, stdout = handler(cmd)
        return subprocess.CompletedProcess(cmd, code, stdout=stdout, stderr="boom")

    monkeypatch.setattr(runner, "_run", fake_run)
    monkeypatch.setenv(f"{provider.upper()}_BIN", sys.executable)
    monkeypatch.setenv("LLM_PROVIDER", provider)
    config.get_settings.cache_clear()
    return calls


def test_strict_schema_requires_all_and_drops_system_fields():
    schema = strict_schema(Profile, drop={"id", "updated_at"})
    assert "updated_at" not in schema["properties"]
    assert set(schema["required"]) == set(schema["properties"])
    exp = schema["$defs"]["Experience"]
    assert "id" not in exp["properties"]
    assert "title" in exp["properties"]  # a property named "title" must survive
    assert exp["additionalProperties"] is False
    assert {"type": "null"} in exp["properties"]["location"]["anyOf"]


def test_import_via_claude_cli(client, monkeypatch):
    out = {"is_error": False, "result": "", "structured_output": EXTRACTED}
    calls = _fake_cli(monkeypatch, "claude", lambda cmd: (0, json.dumps(out)))

    cv = "Ali Veli — Çağlayan, İstanbul".encode()
    res = client.post("/api/profile/import", files={"file": ("cv.txt", cv, "text/plain")})
    assert res.status_code == 200, res.text
    assert "Çağlayan" in calls[0]["stdin"]
    assert "--json-schema" in calls[0]["cmd"]
    profile = res.json()
    assert profile["full_name"] == "Ali Veli"
    assert profile["email"] == ""  # null -> default
    assert profile["headline"] == "Backend & Data Developer"
    assert profile["experience"][0]["id"].startswith("exp_")
    assert profile["experience"][0]["end_date"] is None


def test_import_via_codex_cli(client, monkeypatch):
    def handler(cmd):
        out_file = Path(cmd[cmd.index("--output-last-message") + 1])
        out_file.write_text(json.dumps(EXTRACTED, ensure_ascii=False), encoding="utf-8")
        return 0, ""

    _fake_cli(monkeypatch, "codex", handler)

    res = client.post("/api/profile/import", files={"file": ("cv.md", b"Ali Veli", "text/plain")})
    assert res.status_code == 200, res.text
    assert res.json()["skills"]["tools"] == ["Docker"]


def _agy_result(result: dict) -> str:
    init = {"event": "init", "init": {"model": "gemini-3.8-flash-medium"}}
    return "\n".join(json.dumps(event) for event in (init, {"event": "result", "result": result}))


def test_import_via_antigravity_cli(client, monkeypatch):
    out = _agy_result({"status": "SUCCESS", "response": "", "structured_output": EXTRACTED})
    calls = _fake_cli(monkeypatch, "antigravity", lambda cmd: (0, out))

    cv = "Ali Veli — Çağlayan, İstanbul".encode()
    res = client.post("/api/profile/import", files={"file": ("cv.txt", cv, "text/plain")})
    assert res.status_code == 200, res.text
    message = json.loads(calls[0]["stdin"])
    assert message["event"] == "user"
    assert "Çağlayan" in message["message"]["content"]
    cmd = calls[0]["cmd"]
    assert cmd[cmd.index("--input-format") + 1] == "stream-json"
    assert cmd[cmd.index("--model") + 1] == "gemini-3.8-flash-medium"
    assert res.json()["full_name"] == "Ali Veli"


def test_antigravity_error_returns_502(client, monkeypatch):
    out = _agy_result({"status": "ERROR", "response": "", "error": "Eligibility check failed"})
    _fake_cli(monkeypatch, "antigravity", lambda cmd: (1, out))

    res = client.post("/api/profile/import", files={"file": ("cv.txt", b"x", "text/plain")})
    assert res.status_code == 502
    assert "Eligibility check failed" in res.json()["detail"]


def test_antigravity_retries_once_when_model_is_busy(monkeypatch):
    busy = _agy_result({"status": "ERROR", "error": "UNAVAILABLE (code 503): No capacity"})
    done = _agy_result({"status": "SUCCESS", "response": '{"full_name": "Ali Veli"}'})
    replies = [busy, done]
    calls = _fake_cli(monkeypatch, "antigravity", lambda cmd: (0, replies.pop(0)))

    assert runner.run_structured("s", "p", Profile).full_name == "Ali Veli"
    assert len(calls) == 2
    # Calls without web access tell the agent not to use tools.
    assert "Do not use any tools" in json.loads(calls[0]["stdin"])["message"]["content"]


def test_web_mode_turns_on_each_cli_s_search_tools(monkeypatch):
    agy = _fake_cli(monkeypatch, "antigravity", lambda cmd: (0, _agy_result({"status": "SUCCESS", "structured_output": {}})))
    runner.run_structured("s", "p", Profile, web=True, timeout=900)
    content = json.loads(agy[0]["stdin"])["message"]["content"]
    assert "Do not use any tools" not in content and "Never run terminal commands" in content
    assert agy[0]["timeout"] == 900

    claude = _fake_cli(monkeypatch, "claude", lambda cmd: (0, json.dumps({"structured_output": {}})))
    runner.run_structured("s", "p", Profile, web=True)
    cmd = claude[0]["cmd"]
    assert cmd[cmd.index("--tools") + 1] == "WebSearch,WebFetch"

    def codex(cmd):
        Path(cmd[cmd.index("--output-last-message") + 1]).write_text("{}", encoding="utf-8")
        return 0, ""

    calls = _fake_cli(monkeypatch, "codex", codex)
    runner.run_structured("s", "p", Profile, web=True)
    cmd = calls[0]["cmd"]
    assert cmd.index("--search") < cmd.index("exec")


DENIED = 'no output produced - a tool required the "command" permission that headless mode cannot prompt for, so it was auto-denied.'


def test_antigravity_asks_again_when_a_denied_tool_ended_the_turn(monkeypatch):
    empty = _agy_result({"status": "SUCCESS", "response": ""})
    done = _agy_result({"status": "SUCCESS", "structured_output": {"full_name": "Ali Veli"}})
    _fake_cli(monkeypatch, "antigravity", lambda cmd: (0, done))
    replies = [(empty, DENIED), (done, "")]
    calls = []

    def fake_run(cmd, stdin, cwd, timeout=None):
        calls.append(stdin)
        stdout, stderr = replies.pop(0)
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(runner, "_run", fake_run)
    assert runner.run_structured("s", "p", Profile).full_name == "Ali Veli"
    assert len(calls) == 2
    assert "tried a tool that isn't available" in json.loads(calls[1])["message"]["content"]


def test_antigravity_explains_an_empty_answer(monkeypatch):
    out = _agy_result({"status": "SUCCESS", "response": ""})
    _fake_cli(monkeypatch, "antigravity", lambda cmd: (0, out))
    calls = []

    def fake_run(cmd, stdin, cwd, timeout=None):
        calls.append(stdin)
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr=DENIED)

    monkeypatch.setattr(runner, "_run", fake_run)
    with pytest.raises(LLMError, match='"command" permission'):
        runner.run_structured("s", "p", Profile, web=True)
    assert len(calls) == 2  # asked once more before giving up


def test_cli_error_returns_502(client, monkeypatch):
    out = {"is_error": True, "result": "Failed to authenticate"}
    _fake_cli(monkeypatch, "claude", lambda cmd: (1, json.dumps(out)))

    res = client.post("/api/profile/import", files={"file": ("cv.txt", b"x", "text/plain")})
    assert res.status_code == 502
    assert "Failed to authenticate" in res.json()["detail"]


def test_missing_cli_returns_503(client, monkeypatch):
    monkeypatch.setenv("CLAUDE_BIN", "definitely-not-installed-cli")
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    config.get_settings.cache_clear()

    res = client.post("/api/profile/import", files={"file": ("cv.txt", b"x", "text/plain")})
    assert res.status_code == 503


def test_codeblock_json_is_parsed():
    from app.llm.runner import _parse_json_text

    assert _parse_json_text('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(LLMError):
        _parse_json_text("not json")


NPM_CMD_SHIM = r"""@ECHO off
GOTO start
:find_dp0
SET dp0=%~dp0
EXIT /b
:start
SETLOCAL
CALL :find_dp0

IF EXIST "%dp0%\node.exe" (
  SET "_prog=%dp0%\node.exe"
) ELSE (
  SET "_prog=node"
  SET PATHEXT=%PATHEXT:;.JS;=;%
)

endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%\node_modules\@anthropic-ai\claude-code\cli.js" %*
"""


def test_windows_npm_shim_is_unwrapped(tmp_path, monkeypatch):
    shim = tmp_path / "claude.cmd"
    shim.write_text(NPM_CMD_SHIM, encoding="utf-8")
    script = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "cli.js"
    script.parent.mkdir(parents=True)
    script.write_text("")
    (tmp_path / "node.exe").write_text("")
    monkeypatch.setattr(runner.shutil, "which", lambda name: str(shim))

    assert runner._resolve_bin("claude") == [str(tmp_path / "node.exe"), str(script)]

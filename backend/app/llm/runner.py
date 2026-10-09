"""Run structured LLM calls through the Antigravity, Claude Code or Codex CLI.

Each CLI uses the account the user is logged into, so no API key is needed.
"""

import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)

ANTIGRAVITY_DEFAULT_MODEL = "gemini-3.8-flash-medium"
ANTIGRAVITY_EXTRACT_MODEL = "gemini-3.8-flash-low"

# CLI subscriptions have usage limits; don't let a batch of packages fire all at once.
_slots = threading.BoundedSemaphore(get_settings().llm_max_concurrency)


def extract_model() -> str | None:
    """The model for calls that only copy text into fields (see EXTRACT_MODEL)."""
    settings = get_settings()
    if settings.extract_model:
        return settings.extract_model
    return ANTIGRAVITY_EXTRACT_MODEL if settings.llm_provider == "antigravity" else None


class LLMError(RuntimeError):
    pass


class LLMNotConfiguredError(LLMError):
    pass


def _is_nullable(node: dict) -> bool:
    return node.get("type") == "null" or any(s.get("type") == "null" for s in node.get("anyOf", []))


def _make_strict(node, drop: set[str]) -> None:
    if not isinstance(node, dict):
        return
    node.pop("default", None)
    node.pop("title", None)
    if "properties" in node:
        props = node["properties"]
        for name in drop:
            props.pop(name, None)
        required = set(node.get("required", []))
        for name, sub in list(props.items()):
            _make_strict(sub, drop)
            if name not in required and not _is_nullable(sub):
                props[name] = {"anyOf": [sub, {"type": "null"}]}
        node["required"] = list(props)
        node["additionalProperties"] = False
    _make_strict(node.get("items"), drop)
    for key in ("anyOf", "allOf", "oneOf"):
        for sub in node.get(key, []):
            _make_strict(sub, drop)
    for sub in node.get("$defs", {}).values():
        _make_strict(sub, drop)


def strict_schema(model: type[BaseModel], drop: set[str] = frozenset()) -> dict:
    """JSON schema in the strict form both CLIs accept: every property required,
    optional ones nullable, no extra properties. Fields in `drop` are system-filled."""
    schema = model.model_json_schema()
    _make_strict(schema, set(drop))
    return schema


def _clean(value):
    # Nulls stand in for "not provided", so let the model's defaults apply.
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, str):
        return html.unescape(value)  # models sometimes emit "&amp;" in plain-text fields
    return value


def _parse_json_text(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM geçerli JSON döndürmedi: {text[:200]}") from e


_NPM_SHIM_TARGET = re.compile(r'%~?dp0%?\\(node_modules\\[^"]+?\.(?:js|mjs|cjs|exe))"', re.I)


def _unwrap_npm_shim(shim: Path) -> list[str] | None:
    """On Windows, npm installs CLIs as .cmd wrappers that run through cmd.exe, which
    mangles quotes and newlines in arguments. Call the real script/binary directly."""
    match = _NPM_SHIM_TARGET.search(shim.read_text(encoding="utf-8", errors="replace"))
    if not match:
        return None
    target = shim.parent / match.group(1).replace("\\", "/")
    if not target.exists():
        return None
    if target.suffix.lower() == ".exe":
        return [str(target)]
    node = shim.parent / "node.exe"
    node_path = str(node) if node.exists() else shutil.which("node")
    return [node_path, str(target)] if node_path else None


def _resolve_bin(name: str, fallback: Path | None = None) -> list[str]:
    path = shutil.which(name)
    if not path and fallback and fallback.exists():
        path = str(fallback)
    if not path:
        raise LLMNotConfiguredError(
            f"'{name}' komutu bulunamadı. CLI'ı kurun veya .env içinde yolunu belirtin "
            "(ANTIGRAVITY_BIN / CLAUDE_BIN / CODEX_BIN)."
        )
    if Path(path).suffix.lower() in (".cmd", ".bat"):
        return _unwrap_npm_shim(Path(path)) or [path]
    return [path]


def _run(cmd: list[str], stdin: str, cwd: str, timeout: int | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",  # Windows would otherwise use the locale code page (cp1254)
            errors="replace",
            cwd=cwd,
            timeout=timeout or get_settings().llm_timeout_seconds,
        )
    except subprocess.TimeoutExpired as e:
        raise LLMError("LLM yanıtı zaman aşımına uğradı.") from e


def _run_claude(system: str, prompt: str, schema: dict, workdir: str, web: bool, timeout: int | None, model: str | None) -> dict:
    settings = get_settings()
    cmd = [
        *_resolve_bin(settings.claude_bin),
        "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        "--system-prompt", system,
        "--no-session-persistence",
    ]
    if web:
        cmd += ["--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch WebFetch"]
    else:
        cmd += ["--tools", ""]
    if model or settings.llm_model:
        cmd += ["--model", model or settings.llm_model]
    proc = _run(cmd, prompt, workdir, timeout)
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise LLMError(f"Claude CLI hatası: {(proc.stderr or proc.stdout)[-500:]}") from e
    if out.get("is_error"):
        raise LLMError(f"Claude CLI hatası: {out.get('result')}")
    if out.get("structured_output") is not None:
        return out["structured_output"]
    return _parse_json_text(out.get("result", ""))


def _run_codex(system: str, prompt: str, schema: dict, workdir: str, web: bool, timeout: int | None, model: str | None) -> dict:
    settings = get_settings()
    schema_file = Path(workdir) / "schema.json"
    out_file = Path(workdir) / "out.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    cmd = [
        *_resolve_bin(settings.codex_bin),
        *(["--search"] if web else []),  # a global flag, so it goes before "exec"
        "exec",
        "--output-schema", str(schema_file),
        "--output-last-message", str(out_file),
        "--sandbox", "read-only",
        "--skip-git-repo-check",
        "--ephemeral",
        "--color", "never",
    ]
    if model or settings.llm_model:
        cmd += ["--model", model or settings.llm_model]
    cmd.append("-")  # read the prompt from stdin
    proc = _run(cmd, f"{system}\n\n{prompt}", workdir, timeout)
    if proc.returncode != 0 or not out_file.exists():
        raise LLMError(f"Codex CLI hatası: {proc.stderr[-500:]}")
    return _parse_json_text(out_file.read_text(encoding="utf-8"))


def _antigravity_install_path() -> Path | None:
    # The Windows installer adds this folder to PATH, but only for terminals opened afterwards.
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "agy" / "bin" / "agy.exe" if os.name == "nt" and local else None


ANTIGRAVITY_SETTINGS = "~/.gemini/antigravity-cli/settings.json"
_NO_TOOLS = "Answer directly from the text above. Do not use any tools."
# settings.json only allows these; any other tool (e.g. a terminal command) is denied in
# headless mode and ends the turn without an answer.
_TOOL_DENIED = (
    "Your previous attempt tried a tool that isn't available here, so it ended without an "
    "answer. Answer now with the JSON only."
)
_WEB_TOOLS_ONLY = (
    "Only use the web search, URL reading and file viewing tools. Never run terminal commands "
    "and never create or edit files."
)
# Gemini sometimes writes the answer as prose and then returns an empty JSON object.
_ANSWER_IN_JSON = (
    "Put the whole answer in the JSON output. Text written outside it is thrown away, so "
    "never list the answer as prose and then return empty fields."
)


_CODE_BLOCK = re.compile(r"```(?:json)?[ \t]*\n(.*?)```", re.S)


def _is_empty(value) -> bool:
    if isinstance(value, dict):
        return all(_is_empty(v) for v in value.values())
    return value is None or value == "" or value == []


def _answer_in_prose(response: str, schema: dict) -> dict | None:
    """Despite _ANSWER_IN_JSON, Gemini still now and then writes the answer as a JSON block
    in its text (a bare list where the schema wants {"jobs": [...]}) and then returns empty
    fields. Take the answer from that block."""
    fields = schema.get("properties", {})
    for block in reversed(_CODE_BLOCK.findall(response)):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list) and len(fields) == 1:
            [(name, field)] = fields.items()
            if field.get("type") == "array":
                data = {name: data}
        if isinstance(data, dict) and data.keys() <= fields.keys() and not _is_empty(data):
            return data
    return None


def _antigravity_result(stdout: str) -> dict | None:
    result = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("event") == "result":
            result = event.get("result") or {}
    return result


def _run_antigravity(system: str, prompt: str, schema: dict, workdir: str, web: bool, timeout: int | None, model: str | None) -> dict:
    settings = get_settings()
    schema_file = Path(workdir) / "schema.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    # Print mode only takes the prompt as an argument, which Windows caps at ~32K characters;
    # stream-json input reads it from stdin instead. There is no system prompt flag.
    cmd = [
        *_resolve_bin(settings.antigravity_bin, _antigravity_install_path()),
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--json-schema", str(schema_file),
        "--model", model or settings.llm_model or ANTIGRAVITY_DEFAULT_MODEL,
        "--disable-slash-commands",
    ]
    content = f"{system}\n\n{prompt}\n\n{_WEB_TOOLS_ONLY if web else _NO_TOOLS} {_ANSWER_IN_JSON}"
    message = json.dumps({"event": "user", "message": {"content": content}}, ensure_ascii=False)
    for attempt in range(2):
        proc = _run(cmd, message + "\n", workdir, timeout)
        result = _antigravity_result(proc.stdout)
        if result is None:
            raise LLMError(f"Antigravity CLI hatası: {(proc.stderr or proc.stdout)[-500:]}")
        response = result.get("response") or ""
        # A retried model error can still end with an answer.
        if (structured := result.get("structured_output")) is not None:
            if _is_empty(structured):
                return _answer_in_prose(response, schema) or structured
            return structured
        if result.get("status") == "SUCCESS" and response.strip():
            return _parse_json_text(response)
        # A denied tool ends the turn without an answer; stderr says which one.
        error = result.get("error") or proc.stderr.strip()[-500:] or "boş yanıt"
        if attempt == 0 and ("UNAVAILABLE" in error or "503" in error):
            continue  # the model was briefly out of capacity
        if attempt == 0 and "auto-denied" in proc.stderr:
            # Now and then the model reaches for a tool it can't have (e.g. a terminal command
            # to download the page) and the turn ends without an answer; ask once more.
            retry = f"{content}\n\n{_TOOL_DENIED}"
            message = json.dumps({"event": "user", "message": {"content": retry}}, ensure_ascii=False)
            continue
        if any(f'"{tool}" permission' in proc.stderr for tool in ("read_url", "search_web")):
            error = (
                "Antigravity web araçları için izin gerekli: "
                f'{ANTIGRAVITY_SETTINGS} dosyasına {{"permissions": {{"allow": '
                '["read_url(*)", "search_web(*)"]}} ekle.'
            )
        raise LLMError(f"Antigravity CLI hatası: {error}")
    raise AssertionError("unreachable")


_RUNNERS = {"antigravity": _run_antigravity, "claude": _run_claude, "codex": _run_codex}


def run_structured(
    system: str,
    prompt: str,
    output: type[T],
    drop: set[str] = frozenset(),
    web: bool = False,
    timeout: int | None = None,
    model: str | None = None,
) -> T:
    """`web` lets the model search the web and open pages; everything else runs tool-free.
    `model` overrides LLM_MODEL for this call."""
    schema = strict_schema(output, drop)
    runner = _RUNNERS[get_settings().llm_provider]
    # Run in an empty temp dir so the CLI doesn't pick up project files or settings.
    with _slots, tempfile.TemporaryDirectory() as workdir:
        data = runner(system, prompt, schema, workdir, web, timeout, model)
    return output.model_validate(_clean(data))

"""Run structured LLM calls through the Claude Code or Codex CLI.

Both CLIs use the subscription the user is logged into, so no API key is needed.
"""

import html
import json
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

# CLI subscriptions have usage limits; don't let a batch of packages fire all at once.
_slots = threading.BoundedSemaphore(get_settings().llm_max_concurrency)


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


def _resolve_bin(name: str) -> list[str]:
    path = shutil.which(name)
    if not path:
        raise LLMNotConfiguredError(
            f"'{name}' komutu bulunamadı. CLI'ı kurun veya .env içinde yolunu belirtin "
            "(CLAUDE_BIN / CODEX_BIN)."
        )
    if Path(path).suffix.lower() in (".cmd", ".bat"):
        return _unwrap_npm_shim(Path(path)) or [path]
    return [path]


def _run(cmd: list[str], stdin: str, cwd: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",  # Windows would otherwise use the locale code page (cp1254)
            errors="replace",
            cwd=cwd,
            timeout=get_settings().llm_timeout_seconds,
        )
    except subprocess.TimeoutExpired as e:
        raise LLMError("LLM yanıtı zaman aşımına uğradı.") from e


def _run_claude(system: str, prompt: str, schema: dict, workdir: str) -> dict:
    settings = get_settings()
    cmd = [
        *_resolve_bin(settings.claude_bin),
        "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        "--system-prompt", system,
        "--tools", "",
        "--no-session-persistence",
    ]
    if settings.llm_model:
        cmd += ["--model", settings.llm_model]
    proc = _run(cmd, prompt, workdir)
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise LLMError(f"Claude CLI hatası: {(proc.stderr or proc.stdout)[-500:]}") from e
    if out.get("is_error"):
        raise LLMError(f"Claude CLI hatası: {out.get('result')}")
    if out.get("structured_output") is not None:
        return out["structured_output"]
    return _parse_json_text(out.get("result", ""))


def _run_codex(system: str, prompt: str, schema: dict, workdir: str) -> dict:
    settings = get_settings()
    schema_file = Path(workdir) / "schema.json"
    out_file = Path(workdir) / "out.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    cmd = [
        *_resolve_bin(settings.codex_bin),
        "exec",
        "--output-schema", str(schema_file),
        "--output-last-message", str(out_file),
        "--sandbox", "read-only",
        "--skip-git-repo-check",
        "--ephemeral",
        "--color", "never",
    ]
    if settings.llm_model:
        cmd += ["--model", settings.llm_model]
    cmd.append("-")  # read the prompt from stdin
    proc = _run(cmd, f"{system}\n\n{prompt}", workdir)
    if proc.returncode != 0 or not out_file.exists():
        raise LLMError(f"Codex CLI hatası: {proc.stderr[-500:]}")
    return _parse_json_text(out_file.read_text(encoding="utf-8"))


def run_structured(
    system: str, prompt: str, output: type[T], drop: set[str] = frozenset()
) -> T:
    schema = strict_schema(output, drop)
    runner = _run_claude if get_settings().llm_provider == "claude" else _run_codex
    # Run in an empty temp dir so the CLI doesn't pick up project files or settings.
    with _slots, tempfile.TemporaryDirectory() as workdir:
        data = runner(system, prompt, schema, workdir)
    return output.model_validate(_clean(data))

import json
import os
import re
import subprocess
from pathlib import Path

from .config import WORKSPACE_ROOT, read_text, write_text
from .memory import append_long_term, save_artifact, update_checkpoint


TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "file_read", "description": "Read a local text file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write text content to a local file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "code_run", "description": "Run a short shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "update_working_checkpoint", "description": "Update short-term working memory.", "parameters": {"type": "object", "properties": {"key_info": {"type": "string"}, "related_sop": {"type": "string"}}, "required": ["key_info"]}}},
    {"type": "function", "function": {"name": "start_long_term_update", "description": "Append a concise useful lesson to long-term memory.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
]


DANGEROUS_PATTERNS = [r"\brm\s+-rf\b", r"\bgit\s+reset\s+--hard\b", r"\bgit\s+clean\s+-fd\b", r"\bshutdown\b", r"\bdiskpart\b"]
SECRET_PATTERNS = [r"sk-[A-Za-z0-9_\-]{12,}", r"api[_-]?key\s*[:=]\s*['\"]?[^'\"\s]{12,}", r"token\s*[:=]\s*['\"]?[^'\"\s]{12,}"]


def within_workspace(path: str | Path) -> bool:
    full = Path(path).resolve()
    try:
        return os.path.commonpath([str(WORKSPACE_ROOT), str(full)]) == str(WORKSPACE_ROOT)
    except ValueError:
        return False


def contains_secret(text: str) -> bool:
    return any(re.search(p, text or "", flags=re.IGNORECASE) for p in SECRET_PATTERNS)


def dangerous_reason(command: str) -> str:
    for p in DANGEROUS_PATTERNS:
        if re.search(p, command or "", flags=re.IGNORECASE):
            return f"blocked by pattern: {p}"
    return ""


def decode_bytes(data: bytes) -> str:
    if not data:
        return ""
    for enc in ["utf-8", "gbk", "cp936", "latin-1"]:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def compact_result(tool_name: str, result):
    raw = json.dumps(result, ensure_ascii=False, indent=2) if not isinstance(result, str) else result
    if len(raw) <= 1200:
        return result
    path = save_artifact(tool_name, raw)
    return {"status": result.get("status", "success") if isinstance(result, dict) else "success", "compressed": True, "artifact_path": path, "preview": raw[:600] + "\n\n... [omitted] ...\n\n" + raw[-600:], "original_chars": len(raw)}


class ToolHandler:
    def __init__(self, cwd="."):
        self.cwd = Path(cwd).resolve()

    def _abs_path(self, path: str) -> Path:
        full = (self.cwd / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
        if not within_workspace(full):
            raise PermissionError(f"path outside workspace is blocked: {full}")
        return full

    def dispatch(self, tool_name: str, args: dict):
        method = getattr(self, f"do_{tool_name}", None)
        if not method:
            return {"status": "error", "message": f"unknown tool: {tool_name}"}
        try:
            return compact_result(tool_name, method(args))
        except PermissionError as e:
            return {"status": "blocked", "reason": str(e)}

    def do_file_read(self, args):
        path = self._abs_path(args["path"])
        return {"status": "success", "content": read_text(path)}

    def do_file_write(self, args):
        content = args.get("content", "")
        if contains_secret(content):
            return {"status": "blocked", "reason": "content looks like a secret"}
        path = self._abs_path(args["path"])
        write_text(path, content)
        return {"status": "success", "path": str(path)}

    def do_code_run(self, args):
        command = args.get("command", "")
        reason = dangerous_reason(command)
        if reason:
            return {"status": "blocked", "reason": reason, "command": command}
        completed = subprocess.run(
            command,
            shell=True,
            cwd=self.cwd,
            capture_output=True,
            text=False,  # Force bytes even if PYTHONUTF8=1
            timeout=args.get("timeout", 20)
        )
        stdout = decode_bytes(completed.stdout)
        stderr = decode_bytes(completed.stderr)
        return {"status": "success" if completed.returncode == 0 else "error", "exit_code": completed.returncode, "stdout": stdout.strip(), "stderr": stderr.strip()}

    def do_update_working_checkpoint(self, args):
        blob = json.dumps(args, ensure_ascii=False)
        if contains_secret(blob):
            return {"status": "blocked", "reason": "checkpoint looks like a secret"}
        return {"status": "success", "data": update_checkpoint(args.get("key_info", ""), args.get("related_sop", ""))}

    def do_start_long_term_update(self, args):
        text = args.get("text", "")
        if contains_secret(text):
            return {"status": "blocked", "reason": "memory looks like a secret"}
        return {"status": "success", "path": append_long_term(text)}

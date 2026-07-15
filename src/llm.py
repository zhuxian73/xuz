import json
import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from .config import env_key, load_model_config


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict]


class OpenAICompatibleLLM:
    def __init__(self):
        self.config_name, cfg = load_model_config()
        key_env = cfg.get("api_key_env")
        self.api_key = env_key(key_env)
        self.base_url = cfg.get("base_url")
        self.model = cfg.get("model")
        self.timeout = float(cfg.get("timeout", 60))
        self.verify = self._parse_verify(str(cfg.get("verify", "true")))
        self.max_retries = int(cfg.get("max_retries", 2))
        self.max_history_messages = int(cfg.get("max_history_messages", 16))
        if not self.api_key:
            raise RuntimeError(f"Missing API key env var {key_env}")

    def _parse_verify(self, raw: str):
        v = raw.strip().lower()
        if v in {"0", "false", "no", "off"}:
            return False
        if v.startswith("file:"):
            return v[5:]
        return True

    @staticmethod
    def _safe_text(value: Any) -> str:
        return value if isinstance(value, str) else ""

    def chat_stream(self, messages: list[dict], tools_schema: list[dict]) -> LLMResponse:
        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = {"model": self.model, "messages": messages, "tools": tools_schema, "tool_choice": "auto", "stream": True}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Connection": "close",
            "User-Agent": "MiniXuz/0.1",
        }
        for attempt in range(self.max_retries + 1):
            try:
                with requests.post(url, headers=headers, json=payload, timeout=self.timeout, stream=True, verify=self.verify) as resp:
                    resp.raise_for_status()
                    resp.encoding = "utf-8"
                    return self._parse_sse(resp)
            except requests.exceptions.SSLError as e:
                if attempt < self.max_retries and self.verify is True:
                    self.verify = False
                    time.sleep(1)
                    continue
                raise RuntimeError(f"SSL failed: {e}") from e
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    time.sleep(1 + attempt)
                    continue
                raise RuntimeError(f"Request failed after retries: {e}") from e

    def _parse_sse(self, resp) -> LLMResponse:
        current_text = []
        tool_buf = {}
        pending_data = ""
        for raw_line in resp.iter_lines(decode_unicode=False):
            if not raw_line or not raw_line.startswith(b"data:"):
                continue
            data_str = raw_line[5:].lstrip().decode("utf-8", errors="replace")
            if data_str == "[DONE]":
                break
            pending_data = f"{pending_data}\n{data_str}".strip() if pending_data else data_str
            try:
                evt = json.loads(pending_data)
                pending_data = ""
            except json.JSONDecodeError:
                continue
            ch = (evt.get("choices") or [{}])[0]
            delta = ch.get("delta") or {}
            if delta.get("content") is not None:
                chunk = self._safe_text(delta.get("content"))
                if chunk:
                    current_text.append(chunk)
                    print(chunk, end="", flush=True)
            for tc in (delta.get("tool_calls") or []):
                idx = tc.get("index", 0)
                fn = tc.get("function") or {}
                tool_buf.setdefault(idx, {"id": tc.get("id", ""), "name": "", "args": ""})
                if tc.get("id"):
                    tool_buf[idx]["id"] = tc["id"]
                if fn.get("name"):
                    tool_buf[idx]["name"] = fn["name"]
                if fn.get("arguments"):
                    tool_buf[idx]["args"] += fn["arguments"]
        tool_calls = []
        for idx in sorted(tool_buf):
            item = tool_buf[idx]
            try:
                args = json.loads(item["args"] or "{}")
            except Exception:
                args = {"_raw": item["args"]}
            tool_calls.append({"id": item["id"], "name": item["name"], "args": args})
        return LLMResponse(content="".join(current_text), tool_calls=tool_calls)

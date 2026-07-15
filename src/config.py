import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")


PACKAGE_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = PACKAGE_ROOT.parent
DATA_DIR = WORKSPACE_ROOT / "src" / "memory"
MODELS_FILE = DATA_DIR / "models.json"


DEFAULT_MODELS = {
    "active": "default",
    "models": {
        "default": {
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "https://openrouter.ai/api/v1",
            "model": "deepseek/deepseek-v4-flash",
            "verify": "true",
            "timeout": 60,
            "max_retries": 2,
            "max_history_messages": 16,
        },
        "deepseek": {
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "verify": "true",
            "timeout": 60,
            "max_retries": 2,
            "max_history_messages": 16,
        }
    },
}


def ensure_data_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not MODELS_FILE.exists():
        write_json(MODELS_FILE, DEFAULT_MODELS)


def read_text(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: str | Path, content: str):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_json(path: str | Path, fallback):
    try:
        return json.loads(read_text(path) or "")
    except Exception:
        return fallback


def write_json(path: str | Path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def load_model_config():
    ensure_data_dirs()
    config = read_json(MODELS_FILE, DEFAULT_MODELS)
    active = config.get("active", "default")
    model_cfg = (config.get("models") or {}).get(active)
    if not model_cfg:
        raise RuntimeError(f"Active model config not found: {active}")
    return active, model_cfg


def list_models() -> str:
    config = read_json(MODELS_FILE, DEFAULT_MODELS)
    active = config.get("active", "")
    lines = ["# Models"]
    for name, item in sorted((config.get("models") or {}).items()):
        mark = "*" if name == active else " "
        lines.append(f"{mark} {name}: {item.get('model')} @ {item.get('base_url')} key_env={item.get('api_key_env')}")
    return "\n".join(lines)


def set_active_model(name: str):
    config = read_json(MODELS_FILE, DEFAULT_MODELS)
    if name not in (config.get("models") or {}):
        return {"status": "error", "message": f"unknown model config: {name}"}
    config["active"] = name
    write_json(MODELS_FILE, config)
    return {"status": "success", "active": name}


def add_model(name: str, base_url: str, model: str, api_key_env: str = "OPENAI_API_KEY"):
    config = read_json(MODELS_FILE, DEFAULT_MODELS)
    config.setdefault("models", {})[name] = {
        "api_key_env": api_key_env,
        "base_url": base_url,
        "model": model,
        "verify": "true",
        "timeout": 60,
        "max_retries": 2,
        "max_history_messages": 16,
    }
    config["active"] = name
    write_json(MODELS_FILE, config)
    return {"status": "success", "name": name}


def env_key(name: str) -> str:
    return os.getenv(name, "")

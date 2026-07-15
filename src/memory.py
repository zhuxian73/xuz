from datetime import datetime

from .config import DATA_DIR, read_json, read_text, write_json, write_text


WORKING_FILE = DATA_DIR / "working_checkpoint.json"
LONG_TERM_FILE = DATA_DIR / "long_term_memory.md"
SOP_DIR = DATA_DIR / "sops"
SOP_INDEX = SOP_DIR / "index.json"
ARTIFACT_DIR = DATA_DIR / "artifacts"


DEFAULT_SOPS = {
    "file_task_sop.md": "# file_task_sop\n\n- Read before modifying.\n- Verify after writing.\n",
    "shell_task_sop.md": "# shell_task_sop\n\n- Prefer short commands.\n- Capture stdout and stderr.\n",
    "memory_task_sop.md": "# memory_task_sop\n\n- Store only verified useful lessons.\n",
}

DEFAULT_INDEX = [
    {"name": "file_task_sop.md", "keywords": ["file", "read", "write", "文件", "读取", "写入"]},
    {"name": "shell_task_sop.md", "keywords": ["run", "command", "shell", "运行", "命令"]},
    {"name": "memory_task_sop.md", "keywords": ["remember", "memory", "lesson", "记住", "记忆"]},
]


def ensure_memory():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SOP_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    if not WORKING_FILE.exists():
        write_json(WORKING_FILE, {"key_info": "", "related_sop": "", "updated_at": ""})
    if not LONG_TERM_FILE.exists():
        write_text(LONG_TERM_FILE, "# Long-term memory\n\n")
    for name, content in DEFAULT_SOPS.items():
        path = SOP_DIR / name
        if not path.exists():
            write_text(path, content)
    if not SOP_INDEX.exists():
        write_json(SOP_INDEX, DEFAULT_INDEX)


def load_checkpoint():
    ensure_memory()
    return read_json(WORKING_FILE, {"key_info": "", "related_sop": "", "updated_at": ""})


def update_checkpoint(key_info: str, related_sop: str = ""):
    data = {"key_info": key_info, "related_sop": related_sop, "updated_at": datetime.now().isoformat(timespec="seconds")}
    write_json(WORKING_FILE, data)
    return data


def append_long_term(text: str):
    ensure_memory()
    old = read_text(LONG_TERM_FILE)
    note = f"\n## {datetime.now():%Y-%m-%d %H:%M}\n{text.strip()}\n"
    write_text(LONG_TERM_FILE, old + note)
    return str(LONG_TERM_FILE)


def select_sop(user_input: str):
    ensure_memory()
    index = read_json(SOP_INDEX, DEFAULT_INDEX)
    text = user_input.lower()
    best_name, best_score = "", 0
    for item in index:
        score = sum(1 for kw in item.get("keywords", []) if kw.lower() in text)
        if score > best_score:
            best_name, best_score = item.get("name", ""), score
    if not best_name:
        return "", ""
    return best_name, read_text(SOP_DIR / best_name)


def system_memory_prompt(user_input: str) -> str:
    checkpoint = load_checkpoint()
    sop_name, sop_text = select_sop(user_input)
    long_term = read_text(LONG_TERM_FILE)
    return "\n".join(
        [
            "You are Mini Xuz.",
            "Use tools when action is needed. Answer in Chinese briefly when done.",
            "",
            f"[Selected SOP: {sop_name or 'none'}]\n{sop_text[-1200:]}",
            "",
            f"[Working checkpoint]\n{checkpoint}",
            "",
            f"[Long-term memory]\n{long_term[-1200:]}",
        ]
    )


def save_artifact(label: str, content: str):
    ensure_memory()
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in label).strip("_") or "artifact"
    path = ARTIFACT_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{safe[:40]}.txt"
    write_text(path, content)
    return str(path)

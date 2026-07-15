import json

from .config import add_model, list_models, set_active_model
from .llm import OpenAICompatibleLLM
from .loop import agent_loop
from .memory import ensure_memory, load_checkpoint
from .tools import ToolHandler


HELP = """
Commands:
  /help
  /models
  /add-model NAME BASE_URL MODEL [API_KEY_ENV]
  /use-model NAME
  /memory
  /exit
""".strip()


class MiniCli:
    def __init__(self):
        ensure_memory()
        self.llm = OpenAICompatibleLLM()
        self.handler = ToolHandler(cwd=".")
        self.history = [{"role": "system", "content": "You are Mini XuzAgent."}]

    def reload_model(self):
        self.llm = OpenAICompatibleLLM()
        print(f"Loaded model: {self.llm.config_name}/{self.llm.model}")

    def handle_command(self, raw: str) -> bool:
        parts = raw.split()
        cmd = parts[0].lower()
        if cmd in {"/exit", "/quit"}:
            raise SystemExit
        if cmd == "/help":
            print(HELP)
            return True
        if cmd == "/models":
            print(list_models())
            return True
        if cmd == "/add-model":
            if len(parts) < 4:
                print("Usage: /add-model NAME BASE_URL MODEL [API_KEY_ENV]")
                return True
            print(json.dumps(add_model(parts[1], parts[2], parts[3], parts[4] if len(parts) > 4 else "OPENAI_API_KEY"), ensure_ascii=False, indent=2))
            self.reload_model()
            return True
        if cmd == "/use-model":
            if len(parts) < 2:
                print("Usage: /use-model NAME")
                return True
            print(json.dumps(set_active_model(parts[1]), ensure_ascii=False, indent=2))
            self.reload_model()
            return True
        if cmd == "/memory":
            print(json.dumps(load_checkpoint(), ensure_ascii=False, indent=2))
            return True
        return False

    def run(self):
        print("Xuz Agent demo. Type /help, /exit.")
        print(f"Model: {self.llm.config_name}/{self.llm.model}")
        while True:
            raw = input("> ").strip()
            if not raw:
                continue
            try:
                if raw.startswith("/") and self.handle_command(raw):
                    continue
                final, self.history = agent_loop(self.llm, self.handler, raw, self.history)
                print(f"\nFinal: {final}\n")
            except SystemExit:
                break


def main():
    MiniCli().run()


if __name__ == "__main__":
    main()

import json

from .memory import system_memory_prompt
from .tools import TOOLS_SCHEMA


def trim_history(messages: list[dict], keep_last: int):
    if len(messages) <= keep_last:
        return messages
    return messages[:1] + messages[-keep_last:]


def agent_loop(llm, handler, user_input: str, history: list[dict], max_turns: int = 8):
    history.append({"role": "user", "content": user_input})
    history = trim_history(history, llm.max_history_messages)
    for turn in range(1, max_turns + 1):
        print(f"\n--- Turn {turn} ---")
        messages = [{"role": "system", "content": system_memory_prompt(user_input)}] + history
        response = llm.chat_stream(messages, TOOLS_SCHEMA)
        print()
        if not response.tool_calls:
            history.append({"role": "assistant", "content": response.content})
            return response.content, history
        assistant_msg = {"role": "assistant", "content": response.content, "tool_calls": []}
        tool_results = []
        for tc in response.tool_calls:
            print(f"Calling tool: {tc['name']}({tc['args']})")
            result = handler.dispatch(tc["name"], tc["args"])
            print(json.dumps(result, ensure_ascii=False, indent=2))
            assistant_msg["tool_calls"].append({"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"], ensure_ascii=False)}})
            tool_results.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result, ensure_ascii=False)})
        history.append(assistant_msg)
        history.extend(tool_results)
        history = trim_history(history, llm.max_history_messages)
    return "max turns reached", history

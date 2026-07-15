import gradio as gr
import json
import os
import sys
from .llm import OpenAICompatibleLLM
from .tools import ToolHandler, TOOLS_SCHEMA
from .loop import trim_history
from .memory import ensure_memory, system_memory_prompt, load_checkpoint

class GradioAgent:
    def __init__(self):
        ensure_memory()
        self.llm = OpenAICompatibleLLM()
        self.handler = ToolHandler(cwd=".")

    def chat(self, message, history):
        # Convert Gradio history to OpenAI format
        # Gradio 5+ history is a list of dicts: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        # But we need to handle both list of tuples (older Gradio) and list of dicts (newer Gradio)
        openai_history = []
        if history and isinstance(history[0], dict):
            for msg in history:
                # Filter out system messages if any, though ChatInterface usually doesn't have them in history
                if msg["role"] in ["user", "assistant"]:
                    openai_history.append({"role": msg["role"], "content": msg["content"]})
        else:
            for human, assistant in history:
                if human: openai_history.append({"role": "user", "content": human})
                if assistant: openai_history.append({"role": "assistant", "content": assistant})
        
        # Note: ChatInterface already added the current message to history? 
        # Actually, 'history' passed to 'fn' does NOT include the current 'message'.
        # We need to manage our own internal history if we want to keep tool calls across turns, 
        # or just rely on the fact that 'history' only contains text messages.
        # Since 'agent_loop' updates history with tool calls, and those are crucial for the next turn,
        # we should probably store the full OpenAI history in a state.
        
        # However, Gradio's ChatInterface is designed for simple text-in-text-out.
        # To handle tool calls correctly, we need the FULL history (including tool results).
        
        # Let's use a simpler approach: Reconstruct the full conversation context each time.
        # But tool results are NOT in the Gradio history.
        # So we must use a State component or a global variable (per session).
        
        # Actually, let's just run the loop for the CURRENT message.
        # If we want it to be stateful, we'd need to store the 'openai_history' somewhere.
        
        # For this implementation, I'll keep it simple: 
        # 1. Take previous text-only history.
        # 2. Append current message.
        # 3. Run agent_loop logic (which handles multiple turns/tool calls internally).
        
        current_openai_history = openai_history.copy()
        current_openai_history.append({"role": "user", "content": message})
        current_openai_history = trim_history(current_openai_history, self.llm.max_history_messages)
        
        max_turns = 8
        display_text = ""
        
        for turn in range(1, max_turns + 1):
            yield display_text + f"\n\n⚙️ **Turn {turn}**..."
            
            messages = [{"role": "system", "content": system_memory_prompt(message)}] + current_openai_history
            response = self.llm.chat_stream(messages, TOOLS_SCHEMA)
            
            if response.content:
                display_text += response.content
                yield display_text
                
            if not response.tool_calls:
                # Loop finished
                return
            
            assistant_msg = {"role": "assistant", "content": response.content, "tool_calls": []}
            tool_results = []
            
            for tc in response.tool_calls:
                call_info = f"\n\n🛠️ **Calling Tool**: `{tc['name']}`\n```json\n{json.dumps(tc['args'], ensure_ascii=False, indent=2)}\n```"
                display_text += call_info
                yield display_text
                
                result = self.handler.dispatch(tc["name"], tc["args"])
                result_str = json.dumps(result, ensure_ascii=False, indent=2)
                
                display_text += f"\n\n📥 **Result**:\n```json\n{result_str}\n```\n"
                yield display_text
                
                assistant_msg["tool_calls"].append({
                    "id": tc["id"], 
                    "type": "function", 
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["args"], ensure_ascii=False)}
                })
                tool_results.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result, ensure_ascii=False)})
            
            current_openai_history.append(assistant_msg)
            current_openai_history.extend(tool_results)
            current_openai_history = trim_history(current_openai_history, self.llm.max_history_messages)
            
        display_text += "\n\n⚠️ **Max turns reached.**"
        yield display_text

def launch():
    print("Initializing Gradio Agent...")
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass
    agent = GradioAgent()
    
    with gr.Blocks(title="XuzA Agent GUI") as demo:
        gr.Markdown("# xzu agent interface")
        
        with gr.Tab("Chat"):
            gr.ChatInterface(
                fn=agent.chat,
                chatbot=gr.Chatbot(height=600),
                examples=["你好，请帮我列出当前目录下的文件", "创建一个 hello.py 文件并写入 print('hello')"],
            )
            
        with gr.Tab("Settings & Memory"):
            with gr.Row():
                with gr.Column():
                    model_info = gr.Textbox(label="Current Model", value=f"{agent.llm.config_name} / {agent.llm.model}", interactive=False)
                    refresh_btn = gr.Button("Refresh Settings")
                with gr.Column():
                    memory_viewer = gr.JSON(label="Long Term Memory Checkpoint", value=load_checkpoint())
                    refresh_mem_btn = gr.Button("Refresh Memory")
            
            def refresh_all():
                agent.__init__()
                return f"{agent.llm.config_name} / {agent.llm.model}", load_checkpoint()
            
            refresh_btn.click(refresh_all, outputs=[model_info, memory_viewer])
            refresh_mem_btn.click(load_checkpoint, outputs=[memory_viewer])

    server_name = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
    server_port = int(os.getenv("GRADIO_SERVER_PORT", "8715"))
    print(f"Starting Gradio server at http://{server_name}:{server_port} ...")
    demo.launch(server_name=server_name, server_port=server_port, share=False, quiet=False, inbrowser=False)

if __name__ == "__main__":
    launch()

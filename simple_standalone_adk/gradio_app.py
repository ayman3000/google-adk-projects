# app_gradio_adk_chat.py
import os
import uuid
import asyncio
from dotenv import load_dotenv

import gradio as gr
from google.genai import types
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# ---------- config ----------
load_dotenv(verbose=True)
DEFAULT_MODEL = "gemini-2.0-flash"
APP_NAME = "simple_agent"

# ---------- build the root agent ----------
def make_root_agent(model_name: str) -> Agent:
    return Agent(
        model=model_name,
        name="root_agent",
        description="A helpful assistant for user questions.",
        instruction="Answer user questions to the best of your knowledge.",
    )

# ---------- session & runner factory ----------
async def create_runner(api_key: str | None, model_name: str):
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key  # used by google-genai under the hood

    session_service = InMemorySessionService()
    user_id = "u-" + uuid.uuid4().hex[:8]
    session_id = "s-" + uuid.uuid4().hex[:8]

    await session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )

    root_agent = make_root_agent(model_name)
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    return runner, session_service, user_id, session_id

# ---------- chat handler (streams tokens if available) ----------
async def chat_fn(message, history, state):
    """
    Gradio ChatInterface expects either a string or an async generator.
    We stream tokens if ADK emits deltas; otherwise we yield the final text once.
    """
    if state is None or "runner" not in state:
        yield "⚠️ Please click 'Start Session' first."
        return

    runner = state["runner"]
    user_id = state["user_id"]
    session_id = state["session_id"]

    content = types.Content(role="user", parts=[types.Part(text=message)])

    # Accumulate in case streaming deltas aren't present
    final_text = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content
    ):
        # Try to stream incremental text if the event exposes it
        delta = getattr(event, "delta_text", None)
        if delta:
            final_text.append(delta)
            yield "".join(final_text)
            continue

        # Fallback to yielding full final response at the end
        if event.is_final_response() and getattr(event, "content", None):
            parts = getattr(event.content, "parts", None)
            if parts:
                text_bits = [p.text for p in parts if getattr(p, "text", None)]
                if text_bits:
                    final = "\n".join(t.strip() for t in text_bits if t)
                    yield final
                    return

    # If we reach here without any yields (unlikely), return whatever we have
    if final_text:
        yield "".join(final_text)

# ---------- UI helpers ----------
async def start_session(api_key, model_name, state):
    # Create or reset a runner/session
    runner, session_service, user_id, session_id = await create_runner(api_key, model_name)
    new_state = {
        "runner": runner,
        "session_service": session_service,
        "user_id": user_id,
        "session_id": session_id,
        "model": model_name,
    }
    return (
        gr.update(value=f"✅ Session ready (user: {user_id}, session: {session_id})"),
        new_state,
        gr.update(interactive=False),  # lock model after session starts (optional)
    )

def reset_chat():
    # Clear UI chat; keep model/API key fields editable again
    return gr.update(value=None), gr.update(value=None), {"runner": None}, gr.update(interactive=True)

# ---------- build UI ----------
with gr.Blocks(theme="soft", fill_height=True) as demo:
    gr.Markdown(
        "## ADK Chat\n"
        "Chat with a Gemini model via Google ADK Runner. Enter your API key or rely on the `GEMINI_API_KEY` env var."
    )

    with gr.Row():
        api_key = gr.Textbox(
            label="Gemini API Key (optional if set in environment)",
            type="password",
            placeholder="GEMINI_API_KEY",
        )
        model_name = gr.Dropdown(
            label="Model",
            choices=[DEFAULT_MODEL, "gemini-2.0-flash-lite", "gemini-2.0-pro"],
            value=DEFAULT_MODEL,
        )
        status = gr.Textbox(label="Status", interactive=False)

    state = gr.State({"runner": None})

    with gr.Row():
        start_btn = gr.Button("▶️ Start Session", variant="primary")
        reset_btn = gr.Button("🔄 New Chat")

    chat = gr.ChatInterface(
        fn=chat_fn,
        title=None,
        chatbot=gr.Chatbot(height=460, show_copy_button=True, bubble_full_width=False),
        textbox=gr.Textbox(placeholder="Ask anything…", container=True),
        additional_inputs=[state],
        cache_examples=False,
        autofocus=True,
        submit_btn="Send",
    )

    # Wiring
    start_btn.click(
        start_session,
        inputs=[api_key, model_name, state],
        outputs=[status, state, model_name],
        queue=True,
    )

    reset_btn.click(
        reset_chat,
        inputs=None,
        outputs=[chat.chatbot, status, state, model_name],
        queue=False,
    )

if __name__ == "__main__":
    # For local dev, change server_name to "0.0.0.0" if you want LAN access
    demo.queue().launch()
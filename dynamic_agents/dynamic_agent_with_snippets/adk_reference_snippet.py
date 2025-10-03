# Reference pattern for function-only generation.
# Copy this structure EXACTLY. Only modify lines with "EDITABLE".

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
import asyncio

async def run_once(user_text: str) -> str:
    # EDITABLE: set description and instruction from the user intent
    agent = Agent(
        model="gemini-2.0-flash-lite",
        name="task_agent",
        description="EDITABLE one-line description of the agent",
        instruction="EDITABLE instruction tailored to the user intent"
    )

    # DO NOT CHANGE BELOW
    session_service = InMemorySessionService()
    await session_service.create_session(app_name="dyn_adk", user_id="u1", session_id="s1")

    runner = Runner(agent=agent, app_name="dyn_adk", session_service=session_service)

    content = types.Content(role="user", parts=[types.Part(text=user_text)])

    final_text = ""
    async for event in runner.run_async(user_id="u1", session_id="s1", new_message=content):
        if event.is_final_response() and event.content and event.content.parts:
            # DO NOT CHANGE: robust text extraction
            final_text = "".join(
                p.text for p in event.content.parts
                if hasattr(p, "text") and p.text
            )
            break

    return final_text
# DO NOT CHANGE BELOW
if __name__ == "__main__":
    try:
        asyncio.run(run_once(INPUT_TEXT))
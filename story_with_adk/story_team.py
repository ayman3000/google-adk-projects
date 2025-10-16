# story_team.py
import asyncio
import os

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
# Try common artifact service import paths across ADK versions


from agents import StoryTeam
from dotenv import load_dotenv
load_dotenv()

APP_NAME   = "story_studio"
USER_ID    = "u1"
SESSION_ID = "s1"

async def main():
    # Ensure GEMINI_API_KEY is present (dotenv is loaded in tools.py).

    session_service  = InMemorySessionService()
    artifact_service = InMemoryArtifactService()

    # Create a session and run
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    runner = Runner(
        agent=StoryTeam,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service,   # REQUIRED so tools can save/load artifacts
    )

    user_idea = (

        # "Cartoon, vibrant colors, Squirrel loves counting the leaves on his tree―red leaves, gold leaves, orange, and more. But hold on! One of his leaves is missing! On a quest to find the missing leaf, Squirrel teams up with his good friend Bird to discover who the leaf thief could be among their forest friends."
        # "A speedy rabbit naps mid-race, dreaming of victory, while the patient turtle keeps moving slowly and steadily toward the finish line."
        "	Twins Across Time – Two curious twins build a cardboard rocket; one really launches into space and returns to find his sister grown up while he’s still the same age."

    )
    content = types.Content(role="user", parts=[types.Part(text=user_idea)])

    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        # Print only final textual responses

        if event.is_final_response() and event.content and event.content.parts:
            try:

                for part in event.content.parts:
                    if part.text is not None:
                        print(part.text)

                # text = event.content.parts[0].text
                # if text:
                #     print(text.strip())
            except Exception as e:
                print(e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        # For notebook environments, allow awaiting main() manually.
        pass
# run_team.py

import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, vertex_ai_session_service
from google.genai import types
from dotenv import load_dotenv
from google.adk.agents import Agent

# Load environment variables from a .env file (e.g., API keys)
load_dotenv(verbose=True)

# Define the root agent
root_agent = Agent(
    model='gemini-2.0-flash',  # Gemini model to use
    name='root_agent',  # Unique agent name
    description='A helpful assistant for user questions.',  # Agent purpose
    instruction='Answer user questions to the best of your knowledge',  # Agent behavior
)

# Application and session identifiers
APP_NAME = "simple_agent"
USER_ID = "u1"
SESSION_ID = "s1"


async def main():
    # Initialize an in-memory session service
    session_service = InMemorySessionService()

    # Create a new session for this app and user
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

    # Create a runner to handle communication between agent, session, and user
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

    # Example user query (prompt to the agent)
    user_idea = """
write a python program that calculates the factorial of a number.
"""
    # Wrap the query in a Content object for the agent
    content = types.Content(role="user", parts=[types.Part(text=user_idea)])

    # Run the agent asynchronously and stream events
    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        print(f"Event: {event}")  # Print all events for debugging/logging

        # When a final response is received, print the generated answer
        if event.is_final_response() and event.content and event.content.parts:
            print(f" final: {event.content.parts[0].text.strip()}")


# Entry point
if __name__ == "__main__":
    try:
        asyncio.run(main())  # Run the async main function
    except RuntimeError:
        # If running inside a notebook (which already has an event loop),
        # replace with: await main()
        pass
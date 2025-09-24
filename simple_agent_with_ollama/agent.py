from google.adk.agents import Agent
from google.adk.tools.google_search_tool import google_search
from google.adk.models import lite_llm
from .tools import write_file, search_the_internet
import os

# download ollama
# on the terminal: ollama run qwen3:0.6b

model = lite_llm.LiteLlm("ollama_chat/qwen3:0.6b")

cwd = os.getcwd()
code_directory = os.path.join(cwd, "code")

root_agent = Agent(
    # model='gemini-live-2.5-flash-preview',
    model= model, # 'gemini-2.0-flash-lite',
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction='Answer user questions to the best of your knowledge.'
                'use the write_file tool to write any requested files to the code directory:'
                f'{code_directory}',
    tools=[write_file, search_the_internet]
)

# Run adk web from the parent folder: google-adk-projects

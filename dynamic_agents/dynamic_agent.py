import os, io, re, json, builtins, contextlib
import litellm
from dotenv import load_dotenv

load_dotenv()

# =========================================
# 0) System prompt: "Generate ADK code"
# =========================================
ADK_SYSTEM_PROMPT = """
You are an expert Python engineer generating Google ADK code on demand.

Return a self-contained Python script that:
- Uses ONLY Google ADK core pieces: 
  from google.adk.agents import Agent
  from google.adk.runners import Runner
  from google.adk.sessions import InMemorySessionService
  from google.genai import types
  import asyncio
- Builds exactly ONE ADK Agent (child agent) whose instruction is tailored to the user intent.
- Creates a session with InMemorySessionService, runs a single message with the user's text, 
  and returns ONLY the final response text.

Hard rules:
- Define: async def run_once(user_text: str) -> str
    * Build Agent(model="gemini-2.0-flash-lite", name="task_agent", description=..., instruction=...)
    * Create session_service = InMemorySessionService() 
    * create a session:  await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    * Runner(agent=..., app_name="dyn_adk", session_service=...)
    * Send one message built as types.Content(role="user", parts=[types.Part(text=user_text)])
    * to run the user request: runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content)
    * don't define the INPUT_TEXT it will be injected soon.
    * Iterate runner.run_async(...); when event.is_final_response() and event.content/parts exist,
      capture the final text and return it (no prints inside this function).
- __main__:
    * print( asyncio.run(run_once(INPUT_TEXT)) )
    * Print NOTHING else.
- No environment loading, no file I/O, no tool calling beyond the above imports.
- Keep it tiny: one agent, one run, minimal logic.
- Output EXACTLY one ```python fenced block with runnable code and NO explanations.
"""


def build_user_prompt(user_intent: str) -> str:
    return f"""Write the ADK child agent so that it fulfills this user intent:

        {user_intent}

        The script must follow the hard rules and print ONLY the final answer from run_once(INPUT_TEXT).
        """


# =========================================
# 1) LLM call → ADK Python source
# =========================================
CODE_FENCE = re.compile(r"```python\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def generate_adk_code(model: str, api_key: str, user_intent: str) -> str:
    if api_key:
        litellm.api_key = api_key

    # If no explicit key, let LiteLLM pull from env (e.g., GEMINI_API_KEY)
    resp = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": ADK_SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(user_intent)},
        ],
        temperature=0.0,
    )
    text = resp.choices[0].message["content"]
    m = CODE_FENCE.search(text or "")
    if not m:
        raise ValueError("No python code block found in LLM output.")
    code = m.group(1).strip()

    # Tiny normalizations (model occasionally adds fluff)
    code = re.sub(r"\r\n", "\n", code)
    # Guard: ensure required APIs appear
    required = ["google.adk.agents", "google.adk.runners", "google.adk.sessions", "google.genai", "async def run_once"]
    if not all(s in code for s in required):
        raise ValueError("Generated code missing required ADK pieces.")
    return code


# =========================================
# 2) Safe-ish execution (allow-list imports + minimal builtins)
# =========================================
ALLOWED_MODULE_PREFIXES = (
    "google",         # google.adk.*, google.genai.*
    "asyncio",
    "typing",
)

ALLOWED_STD_MODULES = {
    "io", "json", "re", "os", "contextlib", "types", "collections",
}

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.startswith(ALLOWED_MODULE_PREFIXES) or name in ALLOWED_STD_MODULES:
        return __import__(name, globals, locals, fromlist, level)
    raise ImportError(f"Import of '{name}' is not allowed in this runner.")

def run_generated_adk(code: str, input_text: str) -> str:
    out = io.StringIO()

    SAFE_BUILTIN_NAMES = {
        "print", "len", "range", "enumerate", "zip", "min", "max", "abs",
        "str", "int", "float", "bool", "dict", "list", "set", "tuple",
        "isinstance", "issubclass", "getattr", "setattr", "hasattr",
        "object", "type", "property", "staticmethod", "classmethod",
        "sorted", "sum", "map", "filter", "any", "all",
        "Exception", "BaseException", "RuntimeError", "ValueError",
        "TypeError", "NameError", "ImportError", "KeyError", "IndexError",
        "__build_class__",
    }
    safe_builtins = {n: getattr(builtins, n) for n in SAFE_BUILTIN_NAMES if hasattr(builtins, n)}
    safe_builtins["__import__"] = _safe_import

    g = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
        "__package__": None,
        "__spec__": None,
        # Expose the input text exactly as requested by the child program
        "y": 5,
        "INPUT_TEXT": input_text,
    }


    # code = code.replace("async def",f"INPUT_TEXT = '{input_text}'\n\nasync def")
    with contextlib.redirect_stdout(out):
        exec(code, g, g)

    return out.getvalue().strip()




if __name__ == "__main__":
    # Model for code generation (text LLM via LiteLLM)
    MODEL = os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash")
    API_KEY = os.getenv("GOOGLE_API_KEY", "")  # optional; LiteLLM can use GEMINI_API_KEY, etc.
    USER_INTENT = (
        "You are an expert Mathematician"
    )

    #  B. The runtime input passed to the child script
    # SAMPLE_INPUT = "hello adk"
    SAMPLE_INPUT = "what is a matrix?"

    # Error out early if no provider key is available anywhere
    if not (API_KEY or any(k in os.environ for k in ("GEMINI_API_KEY","OPENAI_API_KEY","ANTHROPIC_API_KEY"))):
        raise RuntimeError("No provider API key found. Set GEMINI_API_KEY (or provider-specific env) or LITELLM_API_KEY.")

    code = generate_adk_code(MODEL, API_KEY, USER_INTENT)


    print("----- Generated ADK Code (first 40 lines) -----")
    print(f"Generated ADK code: \n{code}")
    # lines = code.splitlines()
    # print("\n".join(lines[:40] + (["..."] if len(lines) > 40 else [])))
    print("-----------------------------------------------\n")

    result = run_generated_adk(code, SAMPLE_INPUT)
    print("Result from generated ADK run:")
    print(result)
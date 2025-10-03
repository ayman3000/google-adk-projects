# adk_codegen_runner.py
# pip install litellm google-adk google-genai python-dotenv

import os, io, re, json, builtins, contextlib
import litellm
from dotenv import load_dotenv
load_dotenv()

# =========================================
# 0) System prompt: "Generate ADK code"
# =========================================
rules_path = "adk_system_rules.txt"
ref_path = "adk_reference_snippet.py"

with open(rules_path, "r", encoding="utf-8") as f:
    rules = f.read().strip()

with open(ref_path, "r", encoding="utf-8") as f:
    ref = f.read().strip()

ADK_SYSTEM_PROMPT = f"{rules}\n\n```python\n{ref}\n```"


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

# =========================================
# 3) Wire it together
# =========================================
if __name__ == "__main__":
    # Model for code generation (text LLM via LiteLLM)
    MODEL = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")
    API_KEY = os.getenv("GOOGLE_API_KEY", "")  # optional; LiteLLM can use GEMINI_API_KEY, etc.

    #  A. Describe what you want the *generated ADK child agent* to do
    # USER_INTENT = (
    #     "Read the user text; if it's ALL CAPS, return it prefixed with 'OK: '. "
    #     "Otherwise, transform it to UPPERCASE and return that. Be concise."
    # )
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
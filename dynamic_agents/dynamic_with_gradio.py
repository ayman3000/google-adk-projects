# gradio_dynamic_adk_factory.py
# pip install gradio litellm google-adk google-genai python-dotenv

import os, io, re, json, builtins, contextlib, traceback
import gradio as gr
import litellm
from dotenv import load_dotenv

load_dotenv()

# =========================================
# 0) System prompt used to generate ADK code
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
    * create a session:  session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    * runner = Runner(agent=..., app_name="dyn_adk", session_service=...)
    * Build the Content: types.Content(role="user", parts=[types.Part(text=user_text)])
    * Iterate: async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        - When event.is_final_response() and event.content/parts exist, capture the final text and return it.
    * No prints inside run_once.
- __main__:
    * Read a global variable named INPUT_TEXT (assumed to exist)
    * print( asyncio.run(run_once(INPUT_TEXT)) )
    * Print NOTHING else.
- No environment loading, no file I/O, no tool calling beyond the above imports.
- Keep it tiny: one agent, one run, minimal logic.
- Output EXACTLY one ```python fenced block with runnable code and NO explanations.
"""

# Variant prompt: function-only snippet that defines run_once(user_text)
ADK_SYSTEM_PROMPT_FUNCTION_ONLY = """
You are an expert Python engineer generating Google ADK code on demand.

Return a self-contained Python snippet that:
- Uses ONLY Google ADK core pieces:
  from google.adk.agents import Agent
  from google.adk.runners import Runner
  from google.adk.sessions import InMemorySessionService
  from google.genai import types
  import asyncio
- Builds exactly ONE ADK Agent (child agent) whose instruction is tailored to the user intent.
- Creates a session with InMemorySessionService, runs a single message with the user's text,
  and RETURNS ONLY the final response text from a function.

Hard rules:
- Define: async def run_once(user_text: str) -> str
    * Build Agent(model="gemini-2.0-flash-lite", name="task_agent", description=..., instruction=...)
    * session_service = InMemorySessionService()
    * await session_service.create_session(app_name="dyn_adk", user_id="u1", session_id="s1")
    * runner = Runner(agent=..., app_name="dyn_adk", session_service=session_service)
    * content = types.Content(role="user", parts=[types.Part(text=user_text)])
    * async for event in runner.run_async(user_id="u1", session_id="s1", new_message=content):
        - when event.is_final_response() and event.content and event.content.parts:
          return the final text (NO prints), e.g. concatenating available text parts.
- Do NOT include any `if __name__ == "__main__":` block.
- Do NOT read globals, env vars, CLI args, or stdin for input; use only the `user_text` parameter.
- No environment loading, no file I/O.
- Keep it tiny: one agent, one run, minimal logic.
- Output EXACTLY one ```python fenced block with runnable code and NO explanations.
"""

def build_user_prompt(user_intent: str) -> str:
    return f"""Write the ADK child agent so that it fulfills this user intent:

{user_intent}

The script must follow the hard rules and print ONLY the final answer from run_once(INPUT_TEXT).
"""

# Fence sanitizer: removes accidental Markdown code fences from generated code
def _sanitize_fences(code: str) -> str:
    # Remove accidental Markdown code fences if any
    code = re.sub(r'^\s*```[a-zA-Z0-9_-]*\s*\n', '', code)
    code = re.sub(r'\n```[\s\t]*$', '', code)
    return code

# =========================================
# 1) LLM call → ADK Python source
# =========================================

CODE_FENCE = re.compile(r"```(?:python|py)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

# ---- LLM helper: adds timeout + retries to avoid litellm.Timeout ----
def _llm_completion(model: str, api_key: str, messages, timeout_s: int, max_retries: int = 2):
    """
    Wraps litellm.completion with request timeout + simple exponential backoff retries.
    """
    if api_key:
        litellm.api_key = api_key  # prefer explicit key; otherwise litellm uses env
    last_err = None
    for attempt in range(max_retries):
        try:
            # Some LiteLLM providers honor either 'timeout' or 'request_timeout'—pass both defensively.
            return litellm.completion(
                model=model,
                messages=messages,
                temperature=0.0,
                request_timeout=timeout_s,
                timeout=timeout_s,
            )
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                # simple backoff: 0.75s, then 1.5s, etc.
                try:
                    import time
                    time.sleep(0.75 * (2 ** attempt))
                except Exception:
                    pass
            else:
                raise last_err

def _generate_adk_code_function_only(model: str, api_key: str, user_intent: str, timeout_s: int, max_retries: int) -> str:
    # Prefer user-provided key; otherwise rely on env (e.g., GEMINI_API_KEY or LITELLM_API_KEY)
    resp = _llm_completion(
        model=model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": ADK_SYSTEM_PROMPT_FUNCTION_ONLY},
            {"role": "user", "content": build_user_prompt(user_intent)},
        ],
        timeout_s=timeout_s,
        max_retries=max_retries,
    )
    text = resp.choices[0].message["content"]
    m = CODE_FENCE.search(text or "")
    if not m:
        raise ValueError("No python code block found in LLM output.")
    code = m.group(1).strip()
    code = _sanitize_fences(code)
    code = re.sub(r"\r\n", "\n", code)
    required = [
        "from google.adk.agents import Agent",
        "from google.adk.runners import Runner",
        "from google.adk.sessions import InMemorySessionService",
        "from google.genai import types",
        "async def run_once",
    ]
    if not all(s in code for s in required):
        raise ValueError("Generated code missing required ADK pieces or run_once signature.")
    # Forbid stray prints / main / INPUT_TEXT usage
    forbidden_patterns = [r"if __name__\s*==\s*['\"]__main__['\"]", r"\bINPUT_TEXT\b", r"\bprint\s*\("]
    for pat in forbidden_patterns:
        if re.search(pat, code):
            raise ValueError("Generated code violated no-main / no-print / no-INPUT_TEXT rule.")
    return code

def generate_adk_code(model: str, api_key: str, user_intent: str, timeout_s: int, max_retries: int) -> str:
    # Prefer user-provided key; otherwise rely on env (e.g., GEMINI_API_KEY or LITELLM_API_KEY)
    resp = _llm_completion(
        model=model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": ADK_SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(user_intent)},
        ],
        timeout_s=timeout_s,
        max_retries=max_retries,
    )
    text = resp.choices[0].message["content"]
    m = CODE_FENCE.search(text or "")
    if not m:
        raise ValueError("No python code block found in LLM output.")
    code = m.group(1).strip()
    code = _sanitize_fences(code)
    # Normalize newlines
    code = re.sub(r"\r\n", "\n", code)

    # Guard: ensure required APIs appear + run_once exists
    required = [
        "from google.adk.agents import Agent",
        "from google.adk.runners import Runner",
        "from google.adk.sessions import InMemorySessionService",
        "from google.genai import types",
        "async def run_once",
    ]
    if not all(s in code for s in required):
        raise ValueError("Generated code missing required ADK pieces.")

    return _patch_generated_code(code)

def _patch_generated_code(code: str) -> str:
    """
    Minimal, robust after-model patcher.
    Avoid fragile multi-line regex across function bodies.
    """
    # 1) (removed: do not strip 'await' before session_service.create_session(...))

    # 2) Strip pure print(...) lines inside run_once to respect the prompt rule.
    lines = code.splitlines()
    out_lines = []
    in_run_once = False
    run_indent = None

    for line in lines:
        if not in_run_once and re.match(r'\s*async\s+def\s+run_once\s*\(', line):
            in_run_once = True
            run_indent = len(line) - len(line.lstrip())
            out_lines.append(line)
            continue

        if in_run_once:
            cur_indent = len(line) - len(line.lstrip())
            if re.match(r'\s*(def|async\s+def)\s+\w+\s*\(', line) and cur_indent <= (run_indent or 0):
                in_run_once = False
            else:
                if re.match(r'^\s*print\(.*\)\s*$', line):
                    continue

        out_lines.append(line)

    patched = "\n".join(out_lines)

    # Normalize create_session to work whether it's sync or async
    # Replace any single-line 'session_service.create_session(<args>)' (with or without 'await')
    # by a robust pattern that awaits only if needed.
    def _normalize_create_session(src: str) -> str:
        lines = src.splitlines()
        new_lines = []
        pat = re.compile(r'^(\s*)(?:await\s+)?session_service\.create_session\((.*)\)\s*$')
        for ln in lines:
            m = pat.match(ln)
            if m:
                indent, args = m.group(1), m.group(2)
                new_lines.append(f"{indent}_maybe = session_service.create_session({args})")
                new_lines.append(f"{indent}if hasattr(_maybe, '__await__'):")
                new_lines.append(f"{indent}    await _maybe")
            else:
                new_lines.append(ln)
        return "\n".join(new_lines)
    patched = _normalize_create_session(patched)

    # 3) Ensure APP_NAME / USER_ID / SESSION_ID exist if missing.
    #    PREPEND them at the very top to avoid landing inside an if/def block.
    need_constants = "session_service.create_session" in patched and not all(k in patched for k in ("APP_NAME", "USER_ID", "SESSION_ID"))
    if need_constants:
        header = "APP_NAME = 'dyn_adk'\nUSER_ID = 'user-1'\nSESSION_ID = 'sess-1'\n\n"
        patched = header + patched

    # 4) Fix common __main__ guard typos emitted by LLMs
    #    e.g., 'if name == "main":' or mixed variants
    patched = re.sub(r'\bif\s+name\s*==\s*[\'"]main[\'"]\s*:', 'if __name__ == "__main__":', patched)
    patched = re.sub(r'\bif\s+__name__\s*==\s*[\'"]main[\'"]\s*:', 'if __name__ == "__main__":', patched)
    patched = re.sub(r'\bif\s+name\s*==\s*[\'"]__main__[\'"]\s*:', 'if __name__ == "__main__":', patched)
    # Ensure __main__ guard has a body
    if re.search(r'if __name__ == "__main__":\s*$', patched):
        patched += "\n    print(asyncio.run(run_once(INPUT_TEXT)))\n"

    return patched

# =========================================
# 2) Safe-ish execution (allow-list imports + minimal builtins)
# =========================================
ALLOWED_MODULE_PREFIXES = (
    "google",         # google.adk.*, google.genai.*
    "asyncio",
    "typing",
)
ALLOWED_STD_MODULES = {"io", "json", "re", "os", "contextlib", "types", "collections"}

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.startswith(ALLOWED_MODULE_PREFIXES) or name in ALLOWED_STD_MODULES:
        return __import__(name, globals, locals, fromlist, level)
    raise ImportError(f"Import of '{name}' is not allowed in this runner.")

def run_generated_adk(code: str, input_text: str, function_only: bool = False) -> str:
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
        "INPUT_TEXT": input_text,  # exposed to the child script
    }

    if function_only:
        # Execute snippet, grab run_once and call it with input_text
        try:
            with contextlib.redirect_stdout(out):
                exec(code, g, g)
            run_once = g.get("run_once")
            if not callable(run_once):
                raise RuntimeError("Generated code did not define async run_once(user_text: str) -> str")
            import asyncio
            return asyncio.run(run_once(input_text)).strip()
        except Exception as e:
            tb = traceback.format_exc(limit=6)
            raise RuntimeError(f"Execution error in function-only mode:\n{tb}") from e

    try:
        compiled = compile(code, "<generated_adk>", "exec")
    except SyntaxError as se:
        # Build a small annotated snippet around the error line
        try:
            lines = code.splitlines()
            ln = se.lineno or 1
            start = max(0, ln - 4)
            end = min(len(lines), ln + 3)
            snippet = []
            for i in range(start, end):
                prefix = ">> " if (i + 1) == ln else "   "
                snippet.append(f"{prefix}{i+1:4d}: {lines[i]}")
            snippet_text = "\n".join(snippet)
        except Exception:
            snippet_text = ""
        err_line = f"line {se.lineno}, offset {se.offset}"
        err_src = se.text or ""
        raise SyntaxError(f"SyntaxError in generated code at {err_line}:\n{err_src}\n\nContext:\n{snippet_text}") from se

    with contextlib.redirect_stdout(out):
        try:
            exec(compiled, g, g)
        except Exception as e:
            # Bubble up with captured stdout for context
            raise RuntimeError(f"Error while executing generated code: {e}\n\nCaptured stdout:\n{out.getvalue()}") from e

    return out.getvalue().strip()

# =========================================
# 3) Gradio app logic
# =========================================
DEFAULT_MODEL = os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash")

def generate_and_run(api_key: str, model: str, user_intent: str, input_text: str, function_only: bool, req_timeout: float, retries: int):
    generated_code_for_error = ""
    try:
        # basic sanity
        if not user_intent.strip():
            raise ValueError("User Intent is empty.")
        if not input_text.strip():
            raise ValueError("Input Text is empty.")

        # ensure we have at least some provider key from user or env
        has_any_key = bool(api_key) or any(k in os.environ for k in ("GEMINI_API_KEY","OPENAI_API_KEY","ANTHROPIC_API_KEY","LITELLM_API_KEY"))
        if not has_any_key:
            raise RuntimeError("No provider API key found. Provide an API key or set GEMINI_API_KEY / LITELLM_API_KEY in environment.")

        # normalize user-provided timeout/retries
        try:
            timeout_s = int(max(1, float(req_timeout)))
        except Exception:
            timeout_s = 60
        try:
            max_retries = max(0, int(retries))
        except Exception:
            max_retries = 2

        # 1) generate code depending on mode
        if function_only:
            code = _generate_adk_code_function_only(model, api_key.strip(), user_intent.strip(), timeout_s, max_retries)
        else:
            code = generate_adk_code(model, api_key.strip(), user_intent.strip(), timeout_s, max_retries)
        generated_code_for_error = code

        # 2) run generated code
        result = run_generated_adk(code, input_text.strip(), function_only=function_only)

        return code, result, gr.update(visible=False), ""
    except Exception as e:
        # Improve messaging for timeouts
        if "Timeout" in str(e) or "timed out" in str(e).lower():
            err_hint = "\\n\\nHint: Increase the request timeout, reduce model load, or check network/firewall/VPN."
        else:
            err_hint = ""
        # show traceback inside an expandable accordion
        tb = traceback.format_exc()
        return generated_code_for_error, "", gr.update(visible=True), f"{str(e)}{err_hint}\\n\\n{tb}"

# =========================================
# 4) Build Gradio UI
# =========================================
with gr.Blocks(title="Dynamic ADK Agent Factory") as demo:
    gr.Markdown("## 🔧 Dynamic ADK Agent Factory\nGenerate an ADK agent from text instructions, run it once, and see the result.")

    with gr.Row():
        api_key = gr.Textbox(
            label="API Key (optional — leave empty to use environment)",
            type="password",
            placeholder="e.g., your GEMINI_API_KEY or LITELLM_API_KEY"
        )
        model = gr.Textbox(
            label="LLM Model for Code Generation",
            value=DEFAULT_MODEL,
            placeholder="e.g., gemini/gemini-2.5-flash"
        )

    user_intent = gr.Textbox(
        label="User Intent for the Generated ADK Agent",
        value="You are an expert Mathematician",
        lines=2
    )
    input_text = gr.Textbox(
        label="Input Text passed to the Generated Agent",
        value="what is a matrix?",
        lines=2
    )

    use_function_only = gr.Checkbox(
        label="Use function-only generation (run_once(user_text) only)",
        value=True
    )

    with gr.Row():
        req_timeout = gr.Number(
            label="Request timeout seconds",
            value=60,
            precision=0
        )
        retries = gr.Slider(
            label="Max retries",
            value=2,
            minimum=0,
            maximum=5,
            step=1
        )

    run_btn = gr.Button("🚀 Generate & Run", variant="primary")

    with gr.Row():
        gen_code = gr.Code(label="Generated ADK Child Script", language="python")
        final_result = gr.Textbox(label="Final Result from Generated Code", lines=6)

    # Error accordion (collapsed unless there is an error)
    err_box = gr.Accordion("Error details", open=False, visible=False)
    with err_box:
        err_md = gr.Markdown("")

    run_btn.click(
        fn=generate_and_run,
        inputs=[api_key, model, user_intent, input_text, use_function_only, req_timeout, retries],
        outputs=[gen_code, final_result, err_box, err_md]
    )

if __name__ == "__main__":
    # Launch the app (0.0.0.0 for containers, change as you like)
    demo.launch(server_name="0.0.0.0", server_port=7860)
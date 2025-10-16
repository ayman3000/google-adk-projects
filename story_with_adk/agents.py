# agents.py
from gc import is_finalized
from typing import Optional

# Prefer absolute import when launched as a script; fall back to relative for package contexts.
try:
    from tools import generate_image, render_scenes_with_reference, save_file
except ModuleNotFoundError:
    from .tools import generate_image, render_scenes_with_reference, save_file  # type: ignore

from google.adk.agents import Agent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm

USE_GEMINI = True
ollama_model = LiteLlm("ollama_chat/granite4:micro-h")
GEMINI_TEXT = "gemini-2.0-flash"

model = GEMINI_TEXT if USE_GEMINI else ollama_model

# --- 1) Story Planner (LLM-only) ---
StoryPlannerAgent = Agent(
    model=model,  # or GEMINI_TEXT
    name="StoryPlannerAgent",
    description="Outlines the story into 3–5 scenes with filenames.",
    instruction="""
You are the Story Planner. Based on the user's idea in state['user_idea'] (if provided) or the latest user message, produce ONLY this compact JSON:

{
  "title": "...",
  "scenes": [
    {
      "number": 1,
      "title": "...",
      "description": "... (1-2 sentences)",
      "mood": "...",
      "image_prompt": "... (clean, visual-only prompt)",
      "file_name": "scene_01.png"
    }
  ]
}

Rules:
- 3 to 5 scenes max according to the story drama.
- Each scene MUST include an exact 'file_name' like "scene_01.png", "scene_02.png", ...
- Do not call any tools. Return ONLY the JSON (no prose).
""",
    output_key="story_plan_json",
)

# --- 2) Character Agent (LLM + image tool) ---
CharacterAgent = Agent(
    model=model,  # or GEMINI_TEXT if you want reliable tool calling
    name="CharacterAgent",
    description="Defines a character sheet and generates a reference image on disk.",
    instruction="""
You are the Character Agent. Read the planned scenes JSON from {story_plan_json} (if present) and the user's idea (state['user_idea'], if present).
Create ONLY a character sheet JSON:

{
  "name": "...",
  "age": "...",
  "face_shape": "...",
  "hair_style": "...",
  "hair_color": "...",
  "eye_color": "...",
  "outfit": "...",
  "colors_hex": ["#..."],
  "signature_items": ["..."],
  "donts": ["avoid ..."]
}

After you output ONLY the JSON, you MUST call the `generate_image` tool to create a neutral, front-facing character reference portrait:

- prompt: concise portrait description strictly following the sheet (no camera jargon)
- file_name: "character_ref.png"
- out_dir: "./out"

Keep background plain and lighting neutral.

Note:
- The image tool may store the absolute path in state['char_ref_path'] for later steps.
""",
    tools=[generate_image],
    output_key="character_json",
)

# --- 3) Scene Writer (LLM-only) ---
SceneWriterAgent = Agent(
    model=model,  # or GEMINI_TEXT
    name="SceneWriterAgent",
    description="Expands each scene into narration and optional dialogue.",
    instruction="""
You are the Scene Writer. Read the story plan from {story_plan_json} and the character sheet from {character_json}.
Produce ONLY a JSON array aligned with the plan's scenes:

[
  {
    "file_name": "scene_01.png",
    "text": "Short narration (2-4 sentences) and optionally 1-2 lines of dialogue."
  }
]

Rules:
- Keep the tone and character voice consistent with {character_json}.
- DO NOT invent new file names; reuse the same ones from the plan.
- Return ONLY the JSON.
""",
    output_key="scene_texts_json",
)

# --- 4) Image Renderer (LLM + batch render tool) ---
SceneRendererAgent = Agent(
    model=model,  # or GEMINI_TEXT
    name="SceneRendererAgent",
    description="Renders all scene images using the on-disk character reference.",
    instruction="""
You are the Image Renderer. Use {story_plan_json} for scenes and {character_json} for character traits.
Prepare ONLY a minimal JSON list for rendering:

[
  {"file_name": "scene_01.png", "image_prompt": "<visual prompt enforcing the SAME character traits>"},
  ...
]

Each 'image_prompt' MUST:
- Enforce consistency: same face shape, hair style/color, outfit, hex colors, signature items described in {character_json}.
- Reflect each scene's description and mood from {story_plan_json}.
- Avoid meta language and camera jargon unless explicitly needed.

After constructing that JSON, call the `render_scenes_with_reference` tool with:
- scenes_json: the JSON list above.
- char_ref_path: use state['char_ref_path'] if it exists; otherwise "./out/character_ref.png"
- out_dir: "./out"

Return the tool result or a short confirmation including the list of files.
""",
    tools=[render_scenes_with_reference],
    # output_key="render_report",
)

# --- 5) Assembler (LLM + save_html via save_file tool) ---
AssemblerAgent = Agent(
    model=model,  # or GEMINI_TEXT
    name="AssemblerAgent",
    description="Builds a single HTML story booklet with a JS slideshow and saves it beside the images.",
    instruction="""
You are the Assembler. Use:
- story title and scene titles from {story_plan_json}
- scene texts from {scene_texts_json}
- PNG file names from {story_plan_json}
- character summary from {character_json}

Produce a COMPLETE single-file HTML document with:
- <!doctype html>, <html lang="en">, proper <head> (meta charset + viewport), and <title> set to the story title.
- Inline <style> for a clean layout and a fade-transition slideshow.
- Header H1 (story title).
- “Cast” section summarizing key character traits (short).
- Slideshow that shows ONE scene at a time with:
  - <img src="scene_XX.png"> (PNG filename only; images are in ./out)
  - A caption containing the scene title + scene text.
  - Prev/Next arrows, pagination dots, autoplay toggle, keyboard arrows (←/→), pause-on-hover.
- A dependency-free <script> implementing the above behavior.

DOM per slide:
<div class="slide">
  <img src="scene_01.png" alt="Scene 1">
  <div class="caption">
    <h2>Scene Title</h2>
    <p>Scene text...</p>
  </div>
</div>

Finally call `save_file` with:
- file_name: "story.html"
- content: the FULL HTML string
- out_dir: "./out"

Return a one-line confirmation like: "Saved ./out/story.html with N slides."
""",
    tools=[save_file],
)

# --- Orchestrator ---
StoryTeam = SequentialAgent(
    name="StoryTeam",
    sub_agents=[
        StoryPlannerAgent,   # writes state['story_plan_json']
        CharacterAgent,      # writes state['character_json'] and triggers character_ref.png (and sets state['char_ref_path'] if tool does)
        SceneWriterAgent,    # writes state['scene_texts_json']
        SceneRendererAgent,  # writes state['render_report']
        AssemblerAgent,      # writes state['assembler_status']
    ],
    description="Planner → Character → Writer → Renderer → Assembler",
)
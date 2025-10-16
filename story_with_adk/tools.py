# tools.py
import os
import json
from typing import List, Dict
from io import BytesIO
from PIL import Image
from google.cloud.aiplatform.constants.prediction import region

from google.genai import Client, types
from dotenv import load_dotenv

# --- load env & create client with API key ---
load_dotenv()
client = Client(api_key=os.getenv("GOOGLE_API_KEY"))
# client = Client(vertexai=True, project=os.getenv("GOOGLE_CLOUD_PROJECT"),
#                 location=os.getenv("GOOGLE_CLOUD_LOCATION"))

# ---------- helpers ----------
def _abs(path: str) -> str:
    return os.path.abspath(path)

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _infer_mime_from_ext(path: str) -> str:
    ext = os.path.splitext(path.lower())[1]
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    # default to PNG
    return "image/png"

# ---------------------------------------------------------------------
# 1) Generate a single image (NO artifacts; saves to local filesystem)
# ---------------------------------------------------------------------
def generate_image(
    prompt: str,
    file_name: str,
    out_dir: str,
    tool_context: 'ToolContext',
):
    """
    Generate (or edit) an image from text and save it to disk using the doc-style pattern.

    Args:
        prompt: Visual description for the image.
        file_name: Output filename, e.g., "character_ref.png" or "scene_01.png".
        out_dir: Directory to write the file (created if missing).
        tool_context: Unused (kept for ADK tool signature).

    Returns:
        dict: {"status": "success"|"failed"|"error", "path"?: str, "detail"?: str}
    """
    _ensure_dir(out_dir)
    out_path = os.path.join(out_dir, file_name)
    print(f"Generating {out_path}")

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image-preview",
            contents=[prompt],
        )
        print(f"Response:\n {response}")
    except Exception as e:
        return {"status": "error", "detail": f"model call failed: {e}"}
    print(f"Response: {response}")
    try:
        for part in response.candidates[0].content.parts:

            if part.inline_data is not None: #if part.inline_data is not None:
                try:
                    image = Image.open(BytesIO(part.inline_data.data))
                    image.save(out_path)
                except Exception as e:
                    return {"status": "error", "detail": f"image save failed: {e}"}
                return {"status": "success", "path": _abs(out_path)}
    except Exception as e:
        return {"status": "error", "detail": f"model call failed: {e}"}

    return {"status": "failed", "detail": "no image data returned"}

# ---------------------------------------------------------------------
# 2) Render multiple scenes with a fixed character reference image
#    (NO artifacts; reads char_ref from disk; saves scenes to disk)
# ---------------------------------------------------------------------
def render_scenes_with_reference(
    scenes_json: str,    # JSON: [{"file_name":"scene_01.png","image_prompt":"..."}]
    char_ref_path: str,  # Local path to "character_ref.png" (or .jpg/.webp)
    out_dir: str,
    tool_context: 'ToolContext',
):
    """
    Render multiple scene images while enforcing character consistency
    by attaching a local reference image to the model input.

    Returns:
        dict: {"status": "success"|"error", "files"?: list[str], "paths"?: list[str], "detail"?: str}
    """
    _ensure_dir(out_dir)

    # Load the reference image bytes and wrap as a genai Part
    try:
        with open(char_ref_path, "rb") as rf:
            ref_bytes = rf.read()
        ref_part = types.Part.from_bytes(
            data=ref_bytes,
            mime_type=_infer_mime_from_ext(char_ref_path),
        )
    except Exception as e:
        return {"status": "error", "detail": f"failed to load char_ref '{char_ref_path}': {e}"}

    try:
        scenes: List[Dict] = json.loads(scenes_json)
        if not isinstance(scenes, list):
            raise ValueError("scenes_json must be a JSON array")
    except Exception as e:
        return {"status": "error", "detail": f"invalid scenes_json: {e}"}

    files, paths = [], []
    for s in scenes:
        file_name = s.get("file_name")
        prompt = s.get("image_prompt")
        if not (file_name and prompt):
            # skip malformed entries rather than failing the whole batch
            continue

        out_path = os.path.join(out_dir, file_name)

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-image-preview",
                contents=[prompt, ref_part],  # prompt + reference image
            )
        except Exception as e:
            return {"status": "error", "detail": f"model call failed: {e}"}

        saved = False
        for part in response.candidates[0].content.parts:

            if part.inline_data is not None: #if part.inline_data is not None:
                try:
                    image = Image.open(BytesIO(part.inline_data.data))
                    image.save(out_path)
                    saved = True
                except Exception as e:
                    return {"status": "error", "detail": f"image save failed for {file_name}: {e}"}
                files.append(file_name)
                paths.append(_abs(out_path))
                break

        if not saved:
            # If no image bytes returned for this scene, continue gracefully
            print(f"[warn] no image data for {file_name}")

    return {"status": "success", "files": files, "paths": paths}

# ---------------------------------------------------------------------
# 3) Save the final Markdown story to disk (NO artifacts)
# ---------------------------------------------------------------------
def save_file(
    file_name: str,  # e.g., "story.md"
    content: str,
    out_dir: str,
    tool_context: 'ToolContext',
):
    """
    Save the final Markdown story file to disk.

    Returns:
        dict: {"status": "success"|"error", "path"?: str, "detail"?: str}
    """
    _ensure_dir(out_dir)
    out_path = os.path.join(out_dir, file_name)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return {"status": "error", "detail": f"markdown save failed: {e}"}
    return {"status": "success", "path": _abs(out_path)}
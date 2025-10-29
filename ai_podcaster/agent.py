from typing import Dict
import pathlib
import wave
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import ToolContext
from google import genai
from google.genai import types


# -------------------------------------------------------
# UTILITIES
# -------------------------------------------------------

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """Save PCM bytes as a WAV file."""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


async def generate_tts_audio(script_text: str, tool_context: ToolContext, filename: str = "medium_duo_podcast") -> Dict[str, str]:
    """
    Converts a two-speaker podcast script into natural audio using Gemini TTS.
    """
    try:
        client = genai.Client()

        # Notice: we send the script "as-is" — with Speaker 1 / Speaker 2 lines
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=f"Read aloud in a warm, conversational podcast tone with background ambiance.\n\n{script_text}"
                    ),
                ],
            ),
        ]

        response = client.models.generate_content(
            model="gemini-2.5-pro-preview-tts",
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=1.0,
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker="Speaker 1",
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                                ),
                            ),
                            types.SpeakerVoiceConfig(
                                speaker="Speaker 2",
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                                ),
                            ),
                        ]
                    )
                ),
            ),
        )

        data = response.candidates[0].content.parts[0].inline_data.data

        if not filename.endswith(".wav"):
            filename += ".wav"

        path = pathlib.Path.cwd() / filename
        wave_file(str(path), data)

        return {
            "status": "success",
            "message": f"🎧 Audio saved to {path.resolve()}",
            "file_path": str(path.resolve()),
        }

    except Exception as e:
        return {"status": "error", "message": f"TTS generation failed: {str(e)[:200]}."}


# -------------------------------------------------------
# AGENTS
# -------------------------------------------------------

tts_agent = Agent(
    name="tts_agent",
    model="gemini-2.0-flash",
    instruction="""
    You are a voice generation specialist.  
    Take any text written in the format:
        Speaker 1: ...
        Speaker 2: ...
    and convert it into an expressive two-speaker audio podcast using the `generate_tts_audio` tool.
    """,
    tools=[generate_tts_audio],
)


root_agent = Agent(
    name="root_agent",
    model="gemini-2.0-flash",
    instruction="""
    You are a professional podcast writer who creates podcast content like Medium articles or even stories for kids.

    **Your goal:**  
    Given a topic, write a full podcast-ready script where **two speakers** (Speaker 1 and Speaker 2)  
    discuss the topic naturally. The script should:
      - Start with a friendly greeting and short intro.
      - Alternate dialogue between Speaker 1 and Speaker 2.
      - Cover 3–5 points or subtopics conversationally.
      - End with a warm closing.
      - Sound spontaneous, human, and engaging — not robotic.

    Example Format:
    Read aloud in a friendly manner
    Speaker 1: Hello! We're excited to show you our native speech capabilities.
    Speaker 2: Where you can direct a voice, create realistic dialog, and so much more.
    Speaker 1: Let’s dive into today’s discussion!

    After writing the full podcast script, call the `tts_agent` to generate its spoken version.  
    Return both the text and the audio file details.
    """,
    tools=[AgentTool(agent=tts_agent)],
)
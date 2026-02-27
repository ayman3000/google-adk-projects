# main.py - Standalone runner for the Research Paper Writer (with sources) (v2)
#
# Key change from v1: After the LLM pipeline finishes, we call
# save_full_paper / compile_paper / compile_paper_pdf DIRECTLY as
# Python functions — no LLM agent needed for these deterministic steps.

import asyncio
import json
import os
import argparse
from dotenv import load_dotenv

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# Import agents and tools
try:
    from agents import build_pipeline, STATE_PAPER_PLAN, STATE_FULL_DRAFT
    from tools import save_full_paper, compile_paper, compile_paper_pdf
except ModuleNotFoundError:
    from .agents import build_pipeline, STATE_PAPER_PLAN, STATE_FULL_DRAFT
    from .tools import save_full_paper, compile_paper, compile_paper_pdf

# Load environment variables
load_dotenv()

# --- Configuration ---
APP_NAME = "research_paper_with_sources_v2"
USER_ID = "researcher_01"
SESSION_ID = "paper_session_02"


async def write_paper(args: argparse.Namespace):
    """
    Main entry point: runs the pipeline to write a research paper.

    Pipeline stages:
      1. PlannerAgent     (LLM) — designs the paper structure
      2. SingleWriterAgent (LLM) — writes the full paper
      3. EditLoop          (LLM) — critique + refiner iterations
      4. save_full_paper   (direct call) — saves sections to disk
      5. compile_paper     (direct call) — assembles paper.md
      6. compile_paper_pdf (direct call) — generates paper.pdf

    Args:
        args: An argparse.Namespace object containing:
            - topic: Research topic or description.
            - out: Output directory for generated files.
            - source_dir: Optional directory containing research notes/files.
    """
    # Create root output directory if not exists
    os.makedirs(args.out, exist_ok=True)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("\n" + "=" * 60)
    print("📄 RESEARCH PAPER WRITER (WITH SOURCES-v2)")
    print("=" * 60)
    print(f"Topic: {args.topic[:100]}...")
    if args.source_dir:
        print(f"Sources Dir: {os.path.abspath(args.source_dir)}")
    print(f"Output Directory: {os.path.abspath(args.out)}")

    # Initialize session
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    # Build the LLM-only pipeline (Plan → Write → Edit)
    pipeline = build_pipeline()

    runner = Runner(
        agent=pipeline,
        app_name=APP_NAME,
        session_service=session_service,
    )

    # Format the prompt
    topic_prompt = args.topic
    if args.source_dir:
        topic_prompt += f"\n\nAdditional Instruction: A source directory has been provided. You MUST use your `read_source_files` tool to read the contents of '{os.path.abspath(args.source_dir)}' FIRST, before you do any planning or writing. Base your paper on these sources."

    content = types.Content(role="user", parts=[types.Part(text=topic_prompt)])

    print("\n🚀 Running LLM pipeline: Plan → Write → Edit")
    print("-" * 60)

    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    # Show agent progress
                    text = part.text[:150] + "..." if len(part.text) > 150 else part.text
                    print(f"  [{event.author}]: {text}")

    # =========================================================================
    # POST-PIPELINE: Direct tool calls (no LLM needed)
    # =========================================================================

    print("\n" + "-" * 60)
    print("📁 Saving paper sections to disk...")

    # Get session state with the final draft and plan
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    # Extract the full paper draft and plan from session state
    full_draft = session.state.get(STATE_FULL_DRAFT, "")
    paper_plan_raw = session.state.get(STATE_PAPER_PLAN, "{}")

    if not full_draft:
        print("❌ Error: No paper draft found in session state.")
        return

    # Step 4: Save sections (direct call — was SaverAgent in v1)
    save_result = save_full_paper(content=full_draft, out_dir=args.out)
    if save_result["status"] == "success":
        print(f"  ✅ Saved sections: {save_result['sections_saved']}")
    else:
        print(f"  ❌ Save failed: {save_result.get('detail', 'Unknown error')}")
        return

    # Extract paper title from the plan JSON
    paper_title = "Untitled Paper"
    try:
        plan = json.loads(paper_plan_raw) if isinstance(paper_plan_raw, str) else paper_plan_raw
        paper_title = plan.get("title", paper_title)
    except (json.JSONDecodeError, AttributeError):
        # Fallback to simple regex if JSON parsing fails
        import re
        match = re.search(r'"title"\s*:\s*"([^"]+)"', str(paper_plan_raw))
        if match:
            paper_title = match.group(1)

    # Step 5: Compile paper.md (direct call — was CompilerAgent in v1)
    print("📝 Compiling paper.md...")
    compile_result = compile_paper(out_dir=args.out, paper_title=paper_title)
    if compile_result["status"] == "success":
        print(f"  ✅ Compiled: {compile_result['path']}")
    else:
        print(f"  ❌ Compile failed: {compile_result.get('detail', 'Unknown error')}")

    # Step 6: Generate PDF (direct call — was CompilerAgent in v1)
    print("📄 Generating PDF...")
    pdf_result = compile_paper_pdf(out_dir=args.out, paper_title=paper_title)
    if pdf_result["status"] == "success":
        print(f"  ✅ PDF generated: {pdf_result['path']}")
    else:
        print(f"  ⚠️  PDF generation: {pdf_result.get('detail', 'Unknown error')}")

    # Final summary
    print("\n" + "=" * 60)
    print("🎉 PAPER GENERATION COMPLETE!")
    print("=" * 60)
    print(f"Output files in: {os.path.abspath(args.out)}")
    print("  - sections/00_abstract.md ... 07_references.md")
    print("  - paper.md (compiled)")
    print("  - paper_style.css (two-column academic stylesheet)")
    print("  - paper.pdf (professional PDF)")


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="📄 Research Paper Writer (With local source file support-v2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "The impact of transformer architectures on NLP tasks"
  python main.py "AI Prompt Engineering" --source-dir ./my_notes
        """
    )
    parser.add_argument("topic", nargs="?", help="Research topic/description")
    parser.add_argument("--topic", dest="topic_flag", help="Research topic (alternative to positional)")
    parser.add_argument("--out", default="./out", help="Output directory (default: ./out)")
    parser.add_argument("--source-dir", type=str, help="Optional directory containing research notes/files to base the paper on")
    args = parser.parse_args()

    # Resolve topic
    topic = args.topic_flag or args.topic

    if not topic:
        topic = """
        Write a research paper on "The Impact of Large Language Models on
        Scientific Research Productivity".

        Focus areas:
        - How LLMs are being used in literature review and hypothesis generation
        - Quantitative analysis of productivity changes in research workflows
        - Ethical considerations and potential biases
        - Comparison of LLM-assisted vs traditional research approaches

        Target: Academic journal, approximately 5000 words.
        """
        print("ℹ️  No topic provided, using demo research topic.")
        
    args.topic = topic.strip()
    await write_paper(args)


if __name__ == "__main__":
    asyncio.run(main())

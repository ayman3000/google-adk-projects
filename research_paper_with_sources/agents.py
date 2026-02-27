# agents.py - Agent definitions for the Single-Agent Research Paper Writer (v2)
#
# Key change from v1: SaverAgent and CompilerAgent have been REMOVED.
# Those were LlmAgents whose only job was to call tools (save_full_paper,
# compile_paper, compile_paper_pdf) — no LLM reasoning was needed.
# Now those tools are called directly from main.py after the pipeline finishes.

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.loop_agent import LoopAgent

# Import tools
try:
    from tools import exit_loop, read_source_files
except ModuleNotFoundError:
    from .tools import exit_loop, read_source_files


# --- Configuration ---
MODEL = "gemini-3-flash-preview"
CRITIQUE_MODEL = "gemini-2.5-flash-lite"

# --- State Keys ---
STATE_PAPER_PLAN = "paper_plan_json"
STATE_FULL_DRAFT = "full_paper_draft"


# =============================================================================
# STEP 1: Planner Agent
# =============================================================================

PlannerAgent = LlmAgent(
    model=MODEL,
    name="PlannerAgent",
    description="Defines the research paper structure, research question, and methodology. Reads available source material first.",
    instruction="""You are an Academic Research Planner. Based on the user's topic and any provided source material, create a comprehensive research paper plan.

If a --source-dir or source directory path was provided by the user, you MUST use the `read_source_files` tool to read the contents of that directory FIRST before generating your plan. The contents of those files contain the core ideas, notes, or data for the paper.

Produce ONLY this JSON structure:
{
    "title": "Paper Title",
    "research_question": "The central research question",
    "hypothesis": "Optional hypothesis if applicable",
    "methodology": "qualitative|quantitative|mixed-methods|literature-review|meta-analysis",
    "target_journal": "General academic audience",
    "citation_style": "APA",
    "sections": [
        {
            "name": "abstract",
            "description": "Brief summary of the entire paper (150-300 words)",
            "layout": "single"
        },
        {
            "name": "introduction",
            "description": "Background, motivation, research question, and paper structure",
            "layout": "single"
        },
        {
            "name": "literature_review",
            "description": "Survey of existing work and theoretical framework",
            "layout": "single"
        },
        {
            "name": "methodology",
            "description": "Research design, data collection, analysis approach",
            "layout": "single"
        },
        {
            "name": "results",
            "description": "Findings presented with tables and figures",
            "layout": "two-column"
        },
        {
            "name": "discussion",
            "description": "Interpretation of results, implications, limitations",
            "layout": "two-column"
        },
        {
            "name": "conclusion",
            "description": "Summary, contributions, and future work",
            "layout": "single"
        },
        {
            "name": "references",
            "description": "Full bibliography in the chosen citation style",
            "layout": "single"
        }
    ],
    "key_themes": ["theme1", "theme2", "theme3"],
    "estimated_word_count": 5000,
    "special_notes": "Any specific requirements"
}

Rules:
- The sections list MUST include all 8 standard sections above.
- Adjust descriptions based on the user's research topic.
- Set layout to "two-column" for results and discussion by default.
- Return ONLY the JSON, no explanations.
""",
    tools=[read_source_files],
    output_key=STATE_PAPER_PLAN,
)


# =============================================================================
# STEP 2: Single Writer Agent
# =============================================================================

SingleWriterAgent = LlmAgent(
    model=MODEL,
    name="SingleWriterAgent",
    description="Writes the complete research paper in one structured pass.",
    instruction="""You are an Academic Researcher writing a complete research paper.

If a source directory was provided, use the `read_source_files` tool to read the research material BEFORE writing. Base your paper heavily on the notes, ideas, and data discovered in those source files.

Paper Plan: {paper_plan_json}

Write the ENTIRE research paper as a single Markdown document. You MUST use the
following delimiter format to separate sections:

<!-- SECTION: abstract -->
Your abstract text here (150-300 words). Summarize the research question,
methodology, key findings, and conclusions.

<!-- SECTION: introduction -->
Your introduction here. Include:
- Background and context
- Research question/problem statement
- Significance of the study
- Paper structure overview

<!-- SECTION: literature_review -->
Your literature review here. Include:
- Theoretical framework
- Key prior studies with inline citations like (Author, Year)
- Research gaps this paper addresses
- How your work builds on existing literature

<!-- SECTION: methodology -->
Your methodology here. Include:
- Research design
- Data collection methods
- Analysis approach
- Limitations of the methodology

<!-- SECTION: results -->
Your results here. Present findings clearly:
- Write narrative paragraphs describing findings (these go in two columns)
- For tables, place EACH table in its own full-width block like this:

  <div class="full-width">

  | Col1 | Col2 | Col3 |
  |------|------|------|
  | data | data | data |

  *Table 1: Caption here*

  </div>

- Keep tables SIMPLE: max 4-5 columns, short cell text
- Reference figures (Figure 1, Table 1, etc.)
- Report statistical measures if applicable
- Present data objectively without interpretation

<!-- SECTION: discussion -->
Your discussion here. Include:
- Interpretation of results
- Comparison with prior work
- Practical implications
- Limitations of the study
- Unexpected findings

<!-- SECTION: conclusion -->
Your conclusion here. Include:
- Summary of contributions
- Answer to the research question
- Recommendations for practice
- Directions for future research

<!-- SECTION: references -->
Your references here. Format in APA style:
- Author, A. A. (Year). Title of work. *Journal Name*, Volume(Issue), pages.
- Include at least 10-15 references
- Ensure all in-text citations appear here

CRITICAL RULES:
1. Use the exact <!-- SECTION: name --> delimiters as shown above.
2. Write in formal academic tone throughout.
3. For results and discussion sections, keep paragraphs SHORT (3-5 sentences).
4. TABLES MUST be wrapped in <div class="full-width">...</div> so they span
   the full page width and do NOT overlap with two-column text.
5. Keep tables simple: maximum 4-5 columns with short cell values.
6. Use proper in-text citations: (Author, Year) format.
7. Every citation in the text MUST appear in the References section.
8. Aim for the estimated word count from the paper plan.
9. Output ONLY the paper content with delimiters, no JSON wrapper.
""",
    tools=[read_source_files],
    output_key=STATE_FULL_DRAFT,
)


# =============================================================================
# STEP 3: Critic + Refiner Loop
# =============================================================================

CriticAgent = LlmAgent(
    model=CRITIQUE_MODEL,
    name="CriticAgent",
    include_contents="none",
    description="Reviews the research paper for academic rigor and quality.",
    instruction="""You are a strict Academic Peer Reviewer evaluating a research paper.

Draft:
{full_paper_draft}

Evaluate the paper on these criteria:

1. **Research Question Clarity**: Is the RQ well-defined and focused?
2. **Literature Coverage**: Are key works cited? Are there obvious gaps?
3. **Methodology Rigor**: Is the methodology appropriate and well-described?
4. **Results Presentation**: Are findings clear, well-organized, and objective?
5. **Discussion Depth**: Are results interpreted meaningfully? Are limitations acknowledged?
6. **Citation Consistency**: Do all in-text citations appear in References and vice versa?
7. **Academic Tone**: Is the language formal and precise throughout?
8. **Logical Flow**: Does each section build on the previous one?

If improvements are needed:
- Provide concise, actionable feedback organized by section.
- Prioritize the most impactful issues.

If the paper is publication-ready:
- Output EXACTLY: "No major issues found."

Do NOT rewrite the paper. Only provide feedback.
""",
    output_key="critique_feedback",
)

RefinerAgent = LlmAgent(
    model=MODEL,
    name="RefinerAgent",
    include_contents="none",
    description="Refines the paper based on reviewer feedback.",
    instruction="""You are an Academic Researcher refining your paper based on peer review.

**Current Draft:**
{full_paper_draft}

**Reviewer Feedback:**
{critique_feedback}

IF feedback is EXACTLY "No major issues found.":
    Call the exit_loop function immediately. Do not output text.

ELSE:
    Apply the feedback to improve the paper.
    MAINTAIN the exact same <!-- SECTION: name --> delimiter format.
    Output ONLY the refined paper content.
""",
    tools=[exit_loop],
    output_key=STATE_FULL_DRAFT,  # Overwrites draft
)

EditLoop = LoopAgent(
    name="EditLoop",
    sub_agents=[CriticAgent, RefinerAgent],
    max_iterations=2,
)


# =============================================================================
# PIPELINE
# =============================================================================

def build_pipeline() -> SequentialAgent:
    """
    Build the LLM-only research paper pipeline.

    Returns:
        SequentialAgent: The LLM pipeline.
    """
    return SequentialAgent(
        name="ResearchPaperWithSourcesPipeline",
        sub_agents=[
            PlannerAgent,
            SingleWriterAgent,
            EditLoop,
        ],
        description="Research paper pipeline (with sources): Plan → Write → Edit",
    )

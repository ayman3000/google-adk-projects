# tools.py - File I/O tools for the Single-Agent Research Paper Writer
import os
import json
import re
from typing import Optional, List
from google.adk.tools.tool_context import ToolContext


def _ensure_dir(path: str) -> None:
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


def _abs(path: str) -> str:
    """Return absolute path."""
    return os.path.abspath(path)


# =============================================================================
# ACADEMIC CSS STYLESHEET (two-column support)
# =============================================================================

PAPER_CSS = """
/* Academic Research Paper Stylesheet */
@import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=Source+Sans+Pro:wght@400;600;700&display=swap');

@page {
    size: A4;
    margin: 2.5cm 2cm;
    @top-center {
        content: string(paper-title);
        font-size: 9pt;
        color: #666;
    }
    @bottom-center {
        content: counter(page);
        font-size: 9pt;
    }
}

body {
    font-family: 'Libre Baskerville', 'Times New Roman', serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
    max-width: 100%;
}

/* Title & Header */
h1 {
    font-family: 'Source Sans Pro', Arial, sans-serif;
    font-size: 20pt;
    font-weight: 700;
    text-align: center;
    margin-bottom: 0.3em;
    string-set: paper-title content();
}

h2 {
    font-family: 'Source Sans Pro', Arial, sans-serif;
    font-size: 13pt;
    font-weight: 700;
    border-bottom: 1px solid #ccc;
    padding-bottom: 0.2em;
    margin-top: 1.5em;
}

h3 {
    font-family: 'Source Sans Pro', Arial, sans-serif;
    font-size: 11pt;
    font-weight: 700;
    margin-top: 1.2em;
}

/* Abstract block */
.abstract {
    background: #f8f9fa;
    border-left: 3px solid #2c3e50;
    padding: 1em 1.5em;
    margin: 1.5em 2em;
    font-size: 10pt;
    line-height: 1.5;
}

.abstract strong:first-child {
    font-family: 'Source Sans Pro', Arial, sans-serif;
    font-size: 11pt;
}

/* Two-column layout */
.two-column {
    column-count: 2;
    column-gap: 2em;
    column-rule: 1px solid #e0e0e0;
    margin: 1em 0;
}

.two-column h3 {
    column-span: all;
}

/* Full-width blocks inside two-column: tables, figures */
.full-width {
    column-span: all;
    width: 100%;
    margin: 1em 0;
}

/* Prevent tables from breaking across columns */
table {
    break-inside: avoid;
}

/* Keywords */
.keywords {
    font-size: 10pt;
    color: #555;
    margin: 0.5em 2em 1.5em 2em;
}

.keywords strong {
    font-family: 'Source Sans Pro', Arial, sans-serif;
}

/* Tables */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 10pt;
    break-inside: avoid;
    column-span: all;
}

th, td {
    border: 1px solid #ccc;
    padding: 0.4em 0.8em;
    text-align: left;
}

th {
    background: #f0f0f0;
    font-family: 'Source Sans Pro', Arial, sans-serif;
    font-weight: 600;
}

/* Figure captions */
figcaption, .caption {
    font-size: 9pt;
    color: #555;
    text-align: center;
    font-style: italic;
    margin-top: 0.3em;
}

/* Blockquotes for citations */
blockquote {
    border-left: 3px solid #ddd;
    padding-left: 1em;
    color: #555;
    font-style: italic;
    margin: 1em 0;
}

/* References section */
.references {
    font-size: 10pt;
    line-height: 1.4;
}

.references p {
    padding-left: 2em;
    text-indent: -2em;
    margin: 0.3em 0;
}

/* Page breaks */
.page-break {
    page-break-after: always;
}

/* Author info */
.author-info {
    text-align: center;
    font-size: 11pt;
    margin-bottom: 1.5em;
    color: #444;
}

/* Code blocks (if any) */
pre, code {
    font-family: 'Courier New', Courier, monospace;
    font-size: 9.5pt;
    background: #f5f5f5;
    padding: 0.1em 0.3em;
    border-radius: 2px;
}

pre {
    padding: 0.8em;
    overflow-x: auto;
    border: 1px solid #ddd;
}
"""


# =============================================================================
# SECTION DEFINITIONS (canonical order)
# =============================================================================

SECTION_ORDER = [
    "abstract",
    "introduction",
    "literature_review",
    "methodology",
    "results",
    "discussion",
    "conclusion",
    "references",
]

SECTION_DISPLAY_NAMES = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "literature_review": "Literature Review",
    "methodology": "Methodology",
    "results": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
    "references": "References",
}

# Sections that use two-column layout in PDF
TWO_COLUMN_SECTIONS = {"results", "discussion"}


# =============================================================================
# TOOLS
# =============================================================================

def read_source_files(directory_path: str) -> dict:
    """
    Read all text-based source files (ideas, notes, raw data) from a directory.
    Agents can use this to ingest user-provided research material before writing.

    Args:
        directory_path: Path to the directory containing source files.

    Returns:
        dict: {"status": "success"|"error", "content": str, "files_read": int}
    """
    if not os.path.exists(directory_path):
        return {"status": "error", "detail": f"Directory not found: {directory_path}"}
    if not os.path.isdir(directory_path):
        return {"status": "error", "detail": f"Path is not a directory: {directory_path}"}

    allowed_exts = {".txt", ".md", ".json", ".csv", ".log", ".py"}
    combined_content = []
    files_read = 0

    try:
        combined_content.append(f"SOURCE MATERIAL FROM: {directory_path}\n{'='*50}\n")
        
        for root, _, files in os.walk(directory_path):
            for file in sorted(files):
                ext = os.path.splitext(file)[1].lower()
                if ext in allowed_exts:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read().strip()
                            rel_path = os.path.relpath(file_path, directory_path)
                            combined_content.append(f"--- FILE: {rel_path} ---\n{content}\n")
                            files_read += 1
                    except Exception as e:
                        combined_content.append(f"--- ERROR READING {file}: {e} ---\n")
        
        if files_read == 0:
            combined_content.append("No readable text files found in the directory.")
            
        return {
            "status": "success", 
            "content": "\n".join(combined_content),
            "files_read": files_read
        }
    except Exception as e:
        return {"status": "error", "detail": f"Failed to read source files: {e}"}


def save_section(
    section_name: str,
    content: str,
    out_dir: str = "./out"
) -> dict:
    """
    Save a single research paper section to disk.

    Args:
        section_name: Canonical section name (e.g., 'abstract', 'introduction',
                      'literature_review', 'methodology', 'results',
                      'discussion', 'conclusion', 'references').
        content: Section content in Markdown format.
        out_dir: Output directory path.

    Returns:
        dict: {"status": "success"|"error", "path"?: str, "detail"?: str}
    """
    sections_dir = os.path.join(out_dir, "sections")
    _ensure_dir(sections_dir)

    # Normalize section name
    section_key = section_name.lower().replace(" ", "_").strip()

    # Determine file order index for sorting
    if section_key in SECTION_ORDER:
        idx = SECTION_ORDER.index(section_key)
    else:
        idx = len(SECTION_ORDER)

    file_name = f"{idx:02d}_{section_key}.md"
    out_path = os.path.join(sections_dir, file_name)

    try:
        display_name = SECTION_DISPLAY_NAMES.get(section_key, section_name.title())

        # Add section header if not present
        if not content.strip().startswith("#"):
            content = f"## {display_name}\n\n{content}"

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "success", "path": _abs(out_path), "file_name": file_name}
    except Exception as e:
        return {"status": "error", "detail": f"Failed to save section '{section_name}': {e}"}


def save_full_paper(
    content: str,
    out_dir: str = "./out"
) -> dict:
    """
    Parse a full paper with <!-- SECTION: name --> delimiters and save each
    section as a separate file. Use this when the writer outputs the entire
    paper in one pass.

    Args:
        content: Full paper content with section delimiters.
        out_dir: Output directory path.

    Returns:
        dict: {"status": "success"|"error", "sections_saved": [...], "detail"?: str}
    """
    sections_dir = os.path.join(out_dir, "sections")
    _ensure_dir(sections_dir)

    # Parse sections using delimiters
    # Pattern: <!-- SECTION: section_name -->
    pattern = r'<!--\s*SECTION:\s*(\w+)\s*-->'
    parts = re.split(pattern, content, flags=re.IGNORECASE)

    saved = []
    errors = []

    # parts[0] is text before first delimiter (usually empty or title)
    # Then alternating: section_name, section_content, section_name, section_content...
    if len(parts) < 3:
        # No delimiters found — try to split by ## headers instead
        header_pattern = r'^##\s+(.+)$'
        sections = re.split(header_pattern, content, flags=re.MULTILINE)

        if len(sections) >= 3:
            for i in range(1, len(sections), 2):
                section_name = sections[i].strip()
                section_content = sections[i + 1].strip() if i + 1 < len(sections) else ""
                result = save_section(section_name, section_content, out_dir)
                if result["status"] == "success":
                    saved.append(section_name)
                else:
                    errors.append(result.get("detail", ""))
        else:
            return {
                "status": "error",
                "sections_saved": [],
                "detail": "Could not find section delimiters (<!-- SECTION: name -->) or ## headers."
            }
    else:
        for i in range(1, len(parts), 2):
            section_name = parts[i].strip()
            section_content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            result = save_section(section_name, section_content, out_dir)
            if result["status"] == "success":
                saved.append(section_name)
            else:
                errors.append(result.get("detail", ""))

    if errors:
        return {
            "status": "error",
            "sections_saved": saved,
            "detail": "; ".join(errors)
        }
    return {"status": "success", "sections_saved": saved}


def compile_paper(out_dir: str = "./out", paper_title: str = "Untitled Paper") -> dict:
    """
    Compile all saved sections into a single paper.md file with proper academic
    formatting and two-column layout markers.

    Args:
        out_dir: Directory containing sections/ folder.
        paper_title: Title for the paper.

    Returns:
        dict: {"status": "success"|"error", "path"?: str, "detail"?: str}
    """
    try:
        sections_dir = os.path.join(out_dir, "sections")
        if not os.path.exists(sections_dir):
            return {"status": "error", "detail": f"No sections directory found at {sections_dir}"}

        parts = []

        # Paper title
        parts.append(f"# {paper_title}\n")

        # Read sections in order
        section_files = sorted([
            f for f in os.listdir(sections_dir) if f.endswith(".md")
        ])

        for section_file in section_files:
            section_path = os.path.join(sections_dir, section_file)
            with open(section_path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            # Determine section key from filename (e.g., "02_methodology.md" → "methodology")
            section_key = re.sub(r'^\d+_', '', section_file.replace('.md', ''))

            # Wrap abstract in styled div
            if section_key == "abstract":
                # Remove the ## header if present (we'll use a styled div)
                content_body = re.sub(r'^##\s+.*?\n', '', content, count=1).strip()
                parts.append(
                    f'\n<div class="abstract">\n\n'
                    f'**Abstract**\n\n{content_body}\n\n'
                    f'</div>\n'
                )
            # Wrap two-column sections
            elif section_key in TWO_COLUMN_SECTIONS:
                parts.append(f'\n<div class="two-column">\n\n{content}\n\n</div>\n')
            # References section
            elif section_key == "references":
                parts.append(f'\n<div class="references">\n\n{content}\n\n</div>\n')
            else:
                parts.append(f"\n{content}\n")

        # Write compiled paper
        paper_path = os.path.join(out_dir, "paper.md")
        with open(paper_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))

        # Also write the CSS stylesheet
        css_path = os.path.join(out_dir, "paper_style.css")
        with open(css_path, "w", encoding="utf-8") as f:
            f.write(PAPER_CSS)

        return {"status": "success", "path": _abs(paper_path)}
    except Exception as e:
        return {"status": "error", "detail": f"Failed to compile paper: {e}"}


def compile_paper_pdf(out_dir: str = "./out", paper_title: str = "Untitled Paper") -> dict:
    """
    Convert paper.md into a professional academic PDF using pandoc + weasyprint
    with the two-column CSS stylesheet.

    Requires: pip install weasyprint; brew install pandoc

    Args:
        out_dir: Directory containing paper.md and paper_style.css.
        paper_title: Title for PDF metadata.

    Returns:
        dict: {"status": "success"|"error", "path"?: str, "detail"?: str}
    """
    import subprocess
    import shutil

    paper_md_path = os.path.join(out_dir, "paper.md")
    paper_pdf_path = os.path.join(out_dir, "paper.pdf")
    css_path = os.path.join(out_dir, "paper_style.css")

    if not os.path.exists(paper_md_path):
        return {"status": "error", "detail": f"paper.md not found at {paper_md_path}"}

    if not shutil.which("pandoc"):
        return {
            "status": "error",
            "detail": "pandoc not installed. Install with: brew install pandoc"
        }

    # Ensure CSS exists
    if not os.path.exists(css_path):
        with open(css_path, "w", encoding="utf-8") as f:
            f.write(PAPER_CSS)

    try:
        cmd = [
            "pandoc",
            paper_md_path,
            "-o", paper_pdf_path,
            "--pdf-engine=weasyprint",
            f"--css={css_path}",
            "--standalone",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            return {
                "status": "error",
                "detail": f"pandoc failed: {result.stderr}"
            }

        return {"status": "success", "path": _abs(paper_pdf_path)}

    except subprocess.TimeoutExpired:
        return {"status": "error", "detail": "PDF generation timed out"}
    except Exception as e:
        return {"status": "error", "detail": f"Failed to generate PDF: {e}"}


def exit_loop(tool_context: ToolContext) -> dict:
    """
    Signal that the editing loop should exit.
    Call this when the critique indicates no further changes are needed.

    Args:
        tool_context: ADK tool context for escalation.

    Returns:
        dict: Empty dict (escalation handled via context).
    """
    print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
    tool_context.actions.escalate = True
    return {}

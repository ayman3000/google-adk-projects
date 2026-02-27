# Research Paper With Sources (v2 - Optimized)

An optimized version of the research paper generator that supports reading local source material and uses direct tool calls for deterministic operations.

## Architecture

This version refactors the pipeline to remove unnecessary LLM agents (`SaverAgent` and `CompilerAgent`).

```mermaid
graph TD
    User([User topic + --source-dir]) --> Pipeline["LLM Pipeline (SequentialAgent)"]
    
    subgraph Pipeline
        direction TB
        PlannerAgent["PlannerAgent (LlmAgent)"] -- read_source_files --> Plan
        Plan --> SingleWriterAgent["SingleWriterAgent (LlmAgent)"]
        SingleWriterAgent -- read_source_files --> Draft
        Draft --> CriticAgent["CriticAgent"]
        
        subgraph EditLoop ["EditLoop (LoopAgent)"]
            direction TB
            CriticAgent -- Feedback --> RefinerAgent["RefinerAgent"]
            RefinerAgent -- "Refined Draft" --> CriticAgent
        end
    end
    
    RefinerAgent -- "Final State" --> SaveStep["save_full_paper (Direct Call)"]
    SaveStep -- Save Sections --> Disk[(File System)]
    SaveStep --> CompileStep["compile_paper (Direct Call)"]
    CompileStep --> Disk
    CompileStep --> PDFStep["compile_paper_pdf (Direct Call)"]
    PDFStep --> Disk
    
    style SaveStep fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    style CompileStep fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    style PDFStep fill:#e1f5fe,stroke:#01579b,stroke-width:2px

    %% Styles
    classDef agent fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,color:#000
    classDef tool fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#000
    class PlannerAgent,SingleWriterAgent,CriticAgent,RefinerAgent agent
    class SaveStep,CompileStep,PDFStep tool
```

## What's New in v2

This version refactors the architecture to be more efficient, cost-effective, and reliable by removing unnecessary LLM intermediaries.

- **Sources Support**: Uses `read_source_files` tool to ingest local context (notes, data).
- **Efficient Pipeline**: Reasoning steps are LLM-based, while file saving and compilation are direct Python calls in `main.py`.
- **Reduced Latency & Cost**: Saves 2 LLM API calls per execution.
- **Improved Reliability**: Eliminates the risk of the LLM hallucinating during basic tool execution commands.

## Setup

1. Configure your `.env` file with your Gemini API key.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   brew install pandoc
   pip install weasyprint
   ```

## Usage

```bash
python main.py "Your topic" --source-dir ./sample_research
```

The tool will:
1. Read all files in `./sample_research`.
2. Plan the paper using those sources.
3. Write and refine the paper.
4. Deterministically save and compile the final PDF.

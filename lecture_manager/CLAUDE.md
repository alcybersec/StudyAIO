# Lecture Manager — Claude Code Instructions

This repository automates sorting and summarizing university lecture files (Computer Science degree).

## Repository Structure

```
.
├── CLAUDE.md                 ← You are here (Claude Code instructions)
├── new_lectures/             ← Drop zone: user places raw lecture files here
├── raw_lectures/             ← Organized storage: <SUBJECT>/<SUBJECT>_Week<#>.<ext>
├── lectures_summary/         ← Generated markdown summaries: <SUBJECT>/<SUBJECT>_Week<#>.md
└── scripts/
    └── extract_text.py       ← Helper: extracts text from docx, pdf, pptx
```

## Slash Commands

### `/sort_lectures`

Scan `new_lectures/` and organize files into `raw_lectures/`.

**Workflow:**

1. List all files in `new_lectures/` (only `.docx`, `.pdf`, `.pptx`). If empty, inform the user.
2. For **each file**, determine the **subject code** and **week number**:
   a. **First, check the filename.** Look for patterns like `CSIT302`, `ISIT312`, `MATH201`, etc. (typically uppercase letters + digits) and week/lecture numbers (`Week 3`, `Lecture 5`, `W3`, `L5`, `wk3`, etc.).
   b. **If filename is ambiguous or missing info**, extract text from the file content (use `scripts/extract_text.py`) and look for:
      - Subject code: usually appears in the first few pages/slides (e.g., "CSIT302 — Data Structures")
      - Week/Lecture number: "Week 3", "Lecture 3", "Module 3" etc., typically near the beginning
   c. **If still unable to determine** subject or week after checking both filename and content, **ask the user for confirmation**. Show them the filename and any hints found.

3. **Create the subject folder** in `raw_lectures/` if it doesn't already exist (e.g., `raw_lectures/CSIT302/`).

4. **Check for conflicts** before moving:
   - Build the target filename: `<SUBJECT>_Week<#>.<ext>` (e.g., `CSIT302_Week3.pdf`)
   - If a file with that name already exists in the destination:
     - Extract text from **both** the existing file and the new file
     - Compare the content (a fuzzy comparison is fine — check if >90% similar)
     - **If contents are effectively the same**: skip the file, delete it from `new_lectures/`, and inform the user it was a duplicate
     - **If contents differ**: rename the new file with a `_v2` suffix (or `_v3`, etc., incrementing as needed). E.g., `CSIT302_Week3_v2.pdf`

5. **Move** the file from `new_lectures/` to the target location in `raw_lectures/`.

6. After processing all files, print a summary table:
   ```
   | File                  | Subject  | Week | Action          |
   |-----------------------|----------|------|-----------------|
   | lecture3.pdf          | CSIT302  | 3    | Moved           |
   | slides_week5.pptx     | ISIT312  | 5    | Moved           |
   | data_structures.docx  | CSIT302  | 3    | Skipped (dupe)  |
   | notes.pdf             | CSIT302  | 3    | Moved (_v2)     |
   ```

### `/summarize_lectures`

Scan `raw_lectures/` and generate summaries for any lectures not yet summarized.

**Workflow:**

1. **Scan `raw_lectures/`** — list all subject folders and their lecture files.

2. **Scan `lectures_summary/`** — list all existing summaries.

3. **Find unsummarized lectures**: A lecture is "unsummarized" if there is no corresponding `.md` file in `lectures_summary/<SUBJECT>/` for that week. For example, if `raw_lectures/CSIT302/CSIT302_Week3.pdf` exists but `lectures_summary/CSIT302/CSIT302_Week3.md` does not, it needs summarizing.

4. **For each unsummarized week** (there may be multiple files per week, e.g., a `.pdf` and a `.pptx`):
   a. Collect **all files** for that subject + week (including `_v2` variants).
   b. Extract text from every file using `scripts/extract_text.py`.
   c. Extract images from every file using `scripts/extract_text.py --extract-images /tmp/lecture_images/<subject>_week<#>/`.
   d. **Visually inspect the extracted images.** Many CS lectures have critical content in diagrams (UML, ER diagrams, flowcharts, architecture drawings, state machines, network topologies, algorithm visualizations) that text extraction CANNOT capture. Look at each image and identify what it represents.
   e. **Combine** all extracted content — do NOT compress or lose any content from individual files. Every file's content must be fully represented.
   f. Generate a comprehensive summary markdown file, including descriptions of visual content in the "Diagrams & Visual Descriptions" section.
   g. Clean up the temporary image directory.

5. **Save** the summary as `lectures_summary/<SUBJECT>/<SUBJECT>_Week<#>.md`, creating the subject folder if needed.

6. Print a summary of what was generated.

**Summary Format Requirements:**

Each `.md` summary must follow this structure:

```markdown
# <SUBJECT> — Week <#>: <Topic Title>

> **Source files:** file1.pdf, file2.pptx
> **Date summarized:** YYYY-MM-DD

## Overview
A 2-3 sentence high-level summary of what this lecture covers and why it matters
in the broader context of the course.

## Key Concepts

### <Concept 1 Name>
- Clear explanation of the concept
- How it works, why it matters
- Relationship to other concepts

### <Concept 2 Name>
...

## Definitions
| Term | Definition |
|------|------------|
| Term1 | Clear, concise definition |
| Term2 | ... |

## Diagrams & Visual Descriptions
Describe any diagrams, flowcharts, architecture drawings, or visual content
from the lecture slides. Recreate them in text/ASCII art where helpful.

## Code Examples
If the lecture includes code, include the examples with explanations.
```language
// code here
```
Explain what the code demonstrates and how it relates to the lecture concepts.

## Formulas & Algorithms
List any mathematical formulas, pseudocode, or algorithms covered.
Use LaTeX notation where appropriate: $O(n \log n)$

## Key Takeaways
- Bullet point summary of the most important points
- What a student should definitely remember from this lecture

## Connections
How this lecture connects to previous weeks or broader CS topics.
```

**Summary Quality Guidelines (Computer Science focus):**
- Explain concepts as if teaching a peer — clear but not oversimplified
- Include time/space complexity for algorithms
- Preserve all code examples from the source material
- Describe diagrams in detail (data flow, class hierarchies, network topologies, etc.)
- Note any exam hints or emphasized content from the lecturer
- Use proper CS terminology but define jargon
- If a concept builds on a previous week, note the connection

## Text Extraction

Use the helper script for extracting text from lecture files:

```bash
python scripts/extract_text.py <filepath>
```

This handles `.docx`, `.pdf`, and `.pptx` files. Text goes to stdout.

### Image Extraction

The same script can also extract images from lecture files:

```bash
python scripts/extract_text.py <filepath> --extract-images <output_dir>
```

This will:
- Extract **embedded images** from the file (photos, diagrams, figures from `word/media/` or `ppt/media/`)
- **Render full pages/slides as images** via LibreOffice + pdftoppm (captures vector diagrams, SmartArt, charts, drawn content that isn't a simple embedded raster)
- **Deduplicate** images by content hash and skip tiny images (<2KB, likely icons/bullets)
- Save images as `<basename>_img001.png`, `_img002.jpg`, etc.
- Print an image manifest to stderr

**Example:**
```bash
python scripts/extract_text.py raw_lectures/CSIT302/CSIT302_Week3.pptx --extract-images /tmp/csit302_w3_images/
```

### Using Images During Summarization

When summarizing lectures, **always extract images** and visually inspect them. Many CS lectures encode critical information in diagrams (class hierarchies, network topologies, flowcharts, state machines, ER diagrams, etc.) that is NOT captured by text extraction alone.

The extraction script automatically:
- **Normalizes** all images to standard PNG/JPG (fixes raw PDF streams, JPEG2000, CMYK, etc.)
- **Resizes** images larger than 2048px to prevent API "Could not process image" errors
- **Skips** corrupt or unreadable images gracefully

If an image still fails to load during visual inspection, **skip it and move on** — do not loop/retry. Note in the summary that some visual content could not be analyzed and suggest the student check the original file.

Workflow for `/summarize_lectures`:
1. Extract text: `python scripts/extract_text.py <file>`
2. Extract images: `python scripts/extract_text.py <file> --extract-images <temp_dir>`
3. **View each extracted image** to identify diagrams, charts, and visual content
4. Incorporate descriptions of visual content into the summary under the "Diagrams & Visual Descriptions" section
5. Clean up the temporary image directory after summarization

For PPTX files with visual content, you can also use:
```bash
python -m markitdown <filepath>
```

## Parallelization & Agent File Writing

When using background Task agents to parallelize summarization:

1. **Extract text and images from the main context first** — agents may not have Bash permissions for extraction scripts.
2. **Do NOT paste full extracted text into agent prompts for large lectures.** Instead, save extracted text to `/tmp/claude/lecture_texts/` and tell agents to read those files. This avoids bloating the agent's context and hitting output token limits.
3. **Agent file writing — preferred methods (in order):**
   - **Write tool (preferred):** Agents CAN use the Write tool — it works in agent subprocesses. This is the simplest and most reliable method.
   - **Bash with base64-encoded content (fallback):** If Write tool is denied, use base64 encoding to avoid shell escaping issues:
     ```bash
     python3 -c "
     import base64
     content = base64.b64decode('<BASE64_ENCODED_CONTENT>').decode('utf-8')
     with open('<path>', 'w') as f:
         f.write(content)
     print(f'Written {len(content)} bytes')
     "
     ```
   - **NEVER use `python3 -c` with triple-quoted raw markdown** — markdown contains backticks, quotes, and backslashes that WILL break shell escaping. This has failed repeatedly.
   - **NEVER use Bash heredocs** (`cat << 'EOF'`) — they fail in sandboxed environments (read-only /tmp for shell temp files).

4. **Critical: Agents MUST write files via tool calls, NOT as text output.**
   - Agents have a **32,000 output token limit** per response. A comprehensive lecture summary can easily exceed this.
   - Agents MUST NOT output the full summary as text. Instead, they should generate the content and **immediately write it** using the Write tool or Bash+base64.
   - If an agent keeps hitting `max_output_tokens`, the main context should stop it and write the summary directly.

5. **Agent prompt design for large content:**
   - Tell agents to read source files from `/tmp/claude/lecture_texts/` rather than receiving content inline.
   - Tell agents: "Do NOT output the summary as text. Write it directly to the file using the Write tool."
   - For weeks with 4+ source files, warn agents about the output token limit.
   - Include the target file path and format template in the prompt.

6. **After agents finish, verify file sizes from the main context.** If any are 0 bytes or missing:
   - Check the agent output log for `max_output_tokens` errors (agent tried to output content as text instead of writing to file).
   - Check for shell escaping errors in Bash tool results.
   - Re-generate the summary from the main context using the Write tool (which always has permissions in the main context).

7. **Monitor agents periodically** — check progress every few minutes. Common failure modes:
   - `max_output_tokens`: Agent is outputting content as text instead of writing to file. Stop and regenerate from main context.
   - Shell escaping errors in Bash: Agent should retry with Write tool or base64.
   - Agent only making Read calls after a long time: It may be stuck generating content. Check the tail of its output file for errors.

## Important Notes

- This is a Computer Science degree — lectures may cover programming, algorithms, data structures, networking, databases, security, operating systems, AI/ML, software engineering, etc.
- Subject codes typically follow the pattern: 2-4 uppercase letters + 3-4 digits (e.g., `CSIT302`, `MATH201`, `ISIT312`).
- Always preserve the original file format when moving files.
- When comparing files for duplicates, a rough text similarity check is sufficient — exact match is not required.
- When extracting week numbers, normalize variations: "Lecture 3", "Week 3", "Module 3", "W3", "L3" all map to `Week3`.
- If multiple files exist for one week, the summary must incorporate ALL of them — do not skip or compress any source file's content.

Scan the `new_lectures/` directory for all `.docx`, `.pdf`, and `.pptx` files and organize them into `raw_lectures/`.

Follow the `/sort_lectures` workflow defined in CLAUDE.md exactly:

1. List all supported files in `new_lectures/`. If empty, tell me.
2. For each file, determine the **subject code** and **week number**:
   - First check the filename for patterns (e.g., `CSIT302`, `Week3`, `L5`, `wk3`)
   - If ambiguous, extract text from the file using `python scripts/extract_text.py <file> --first-n-chars 2000` and look for subject/week info in the beginning
   - If still unclear, **ask me** — show the filename and any hints you found
3. Create subject folders in `raw_lectures/` as needed.
4. Before moving, check for filename conflicts:
   - If target file already exists, extract text from both and compare
   - If contents are ~90%+ similar → skip (delete from `new_lectures/`, report as duplicate)
   - If contents differ → rename with `_v2` (or `_v3`, etc.)
5. **Move** (not copy) each file from `new_lectures/` to its destination.
6. Print a summary table of all actions taken.

Target naming: `<SUBJECT>_Week<#>.<ext>` (e.g., `CSIT302_Week3.pdf`)

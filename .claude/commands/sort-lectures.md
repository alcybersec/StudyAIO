# Sort Lectures (v0 Compatibility)

Scan `new_lectures/` for new files and organize them into `raw_lectures/`.

## Process

1. List all files in `new_lectures/` (PDF, DOCX, PPTX only)
2. For each file:
   a. Read the first few pages/slides to extract text
   b. Identify the **subject code** (e.g., CSIT302) from filename and content
   c. Identify the **week number** from filename and content
   d. If subject or week is ambiguous, ask for clarification
   e. Move the file to `raw_lectures/<subject>/<subject>_Week<N>.<ext>`
   f. Create the subject folder if it doesn't exist
3. Report what was moved and where

## Rules
- Files are **moved**, not copied (new_lectures/ should be empty after)
- If a file already exists at the destination, ask before overwriting
- Clean filename format: `<SUBJECT>_Week<N>.<ext>` (e.g., `CSIT302_Week3.pdf`)
- Multiple files for the same week are fine (e.g., PDF and PPTX)
- If week number can't be determined, ask — don't guess

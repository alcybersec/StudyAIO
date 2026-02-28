# 📚 Lecture Manager

Automated lecture sorting and summarization powered by Claude Code.

## Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt --break-system-packages
   ```

2. Open this repo with Claude Code.

## Usage

### 1. Drop lecture files

Place your `.docx`, `.pdf`, or `.pptx` lecture files into the `new_lectures/` folder.

### 2. Sort lectures

Tell Claude Code:
```
/sort_lectures
```

Claude will scan each file, detect the subject code and week number, and organize them into `raw_lectures/<SUBJECT>/<SUBJECT>_Week<#>.<ext>`.

### 3. Summarize lectures

Tell Claude Code:
```
/summarize_lectures
```

Claude will find any lectures that haven't been summarized yet, parse their content, and generate comprehensive markdown summaries in `lectures_summary/<SUBJECT>/`.

## Folder Structure

```
new_lectures/          ← Drop zone (files are moved out after sorting)
raw_lectures/          ← Organized lectures by subject
  CSIT302/
    CSIT302_Week1.pdf
    CSIT302_Week1.pptx
    CSIT302_Week2.docx
lectures_summary/      ← Generated summaries
  CSIT302/
    CSIT302_Week1.md
    CSIT302_Week2.md
scripts/               ← Helper utilities
  extract_text.py      ← Text extraction from docx/pdf/pptx
```

## Notes

- Multiple files per lecture week are combined into a single summary without losing content.
- Duplicate files are detected and skipped automatically.
- If Claude can't determine the subject or week, it will ask you for confirmation.

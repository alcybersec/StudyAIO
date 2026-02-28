# Summarize Lectures (v0 Compatibility)

Compare `raw_lectures/` against `lectures_summary/` and generate missing summaries.

## Process

1. Scan `raw_lectures/` — list all courses and weeks that have lecture files
2. Scan `lectures_summary/` — list all existing summaries
3. Identify **missing summaries** (lectures without a corresponding `.md` file)
4. For each missing summary:
   a. Read all files for that course+week (combine if multiple)
   b. Extract text and note any images/diagrams
   c. Generate a comprehensive markdown summary following the format below
   d. Save to `lectures_summary/<subject>/<subject>_Week<N>.md`

## Summary Format

Every summary MUST include these sections in this order:

```markdown
# <Course Code> — Week <N>: <Topic Title>

## Key Concepts
<Explain each major concept clearly enough to understand without slides>

## Definitions
| Term | Definition |
|---|---|
| <term> | <definition in course context> |

## Code Examples
<Reproduce and explain key code from the lecture>

## Diagrams & Figures
<Describe key diagrams and their significance>

## Potential Exam Topics
- <topic>: <what to focus on>

## Summary
<2-3 paragraph high-level overview connecting concepts>
```

## Rules
- Only generate summaries for lectures that **don't already have one**
- If a summary already exists, skip it (use `/resummarize` to force regeneration)
- Summaries should be detailed enough to study from without the original slides
- CS-specific: include Big-O analysis, algorithm explanations, design patterns where relevant
- Combine multiple files for the same week into one summary

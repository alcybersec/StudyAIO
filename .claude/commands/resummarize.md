# Re-Summarize Lectures (v0 Compatibility)

Force regeneration of summaries, even if they already exist.

## Usage

Run this command and specify which summaries to regenerate:
- A specific course: "CSIT302"
- A specific week: "CSIT302 Week 3"
- All: "all"

## Process

1. Identify target lectures based on the scope specified
2. For each target:
   a. Read all lecture files for that course+week from `raw_lectures/`
   b. If an existing summary exists, read it as reference (preserve good content)
   c. Generate an updated summary following the standard format
   d. Overwrite the existing summary in `lectures_summary/`
3. Report what was regenerated

## Rules
- Same format requirements as `/summarize-lectures`
- When updating, improve on the existing summary — don't lose information
- Note at the bottom of the summary: `*Regenerated on <date>*`

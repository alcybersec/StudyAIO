Scan `raw_lectures/` and generate comprehensive markdown summaries for any lectures that don't yet have a corresponding summary in `lectures_summary/`.

Follow the `/summarize_lectures` workflow defined in CLAUDE.md exactly:

1. Scan `raw_lectures/` — list all subject folders and their files.
2. Scan `lectures_summary/` — list existing summaries.
3. Identify unsummarized lectures: a lecture needs summarizing if there's no `lectures_summary/<SUBJECT>/<SUBJECT>_Week<#>.md` for that week.
4. For each unsummarized week:
   - Collect ALL files for that subject + week (including `_v2` variants)
   - Extract full text from every file: `python scripts/extract_text.py <file>`
   - Extract images from every file: `python scripts/extract_text.py <file> --extract-images /tmp/claude/lecture_images/<subject>_week<#>/`
   - **Visually inspect extracted images** — look for diagrams, flowcharts, charts, architecture drawings, UML, ER diagrams, etc. Many CS lectures have critical content only in visuals. If any image fails to load (API error), **skip it and move on** — do not retry in a loop. Note in the summary that some visuals couldn't be analyzed.
   - Combine all text content — do NOT lose or compress anything from any file
   - Incorporate visual content descriptions into the "Diagrams & Visual Descriptions" section of the summary
   - Generate a summary following the format template in CLAUDE.md
   - Clean up temp image directory after summarization
5. Save as `lectures_summary/<SUBJECT>/<SUBJECT>_Week<#>.md`
6. Report what was generated.

**CRITICAL**: This is a Computer Science degree. Summaries must be:
- Comprehensive: cover every concept, definition, algorithm, code example, and diagram
- Well-structured: use the full template from CLAUDE.md (Overview, Key Concepts, Definitions, Diagrams, Code Examples, Formulas, Key Takeaways, Connections)
- CS-appropriate: include complexity analysis, proper terminology, preserve code snippets
- Student-friendly: explain as if teaching a peer, define jargon, note connections to previous weeks
- Complete: if multiple files exist for one week, ALL content must appear in the summary

---

## Parallelization Strategy (Background Agents)

When there are multiple unsummarized weeks, use background Task agents to generate summaries in parallel. Follow these rules strictly — they are based on real failure modes observed in production.

### Phase 1: Extraction (main context)
The **main context** must perform ALL text/image extraction before spawning agents:
1. Extract text from every unsummarized lecture file and save to temp files:
   ```bash
   python scripts/extract_text.py <file> > /tmp/claude/lecture_texts/<SUBJECT>_Week<#>.txt 2>/dev/null
   ```
   For weeks with multiple files (e.g., `_v2`, `_v3`), save each separately:
   ```bash
   python scripts/extract_text.py <file_v2> > /tmp/claude/lecture_texts/<SUBJECT>_Week<#>_v2.txt 2>/dev/null
   ```
2. Extract images to temp directories:
   ```bash
   python scripts/extract_text.py <file> --extract-images /tmp/claude/lecture_images/<subject>_week<#>/
   ```
3. Visually inspect extracted images from the main context and note descriptions.

### Phase 2: Agent Summarization (background agents)
Spawn one background Task agent per week. **Critical rules for agent prompts:**

1. **Tell agents to READ source files from `/tmp/claude/lecture_texts/`** — do NOT paste extracted text into the prompt. Pasting large content bloats the agent context and causes output token limit failures.

2. **Tell agents to use the Write tool to write the output file.** Include this exact instruction in every agent prompt:
   ```
   Write the summary directly to <output_path> using the Write tool.
   Do NOT output the full summary as text in your response — you have a 32,000 output token limit and the summary will exceed it.
   Generate the content and immediately write it to the file.
   If the Write tool is denied, use Bash with base64 encoding as a fallback:
   python3 -c "import base64; content = base64.b64decode('<B64>').decode(); open('<path>','w').write(content); print(f'Written {len(content)} bytes')"
   ```

3. **Include in each agent prompt:**
   - Paths to the extracted text file(s) in `/tmp/claude/lecture_texts/`
   - Path to an existing summary for format reference (e.g., `lectures_summary/<SUBJECT>/<SUBJECT>_Week1.md`)
   - Descriptions of any visual content from images
   - The target output file path
   - A detailed list of topics to cover (from the lecture content)

4. **NEVER use these methods (they fail):**
   - `python3 -c` with triple-quoted raw markdown — backticks, quotes, and backslashes in markdown WILL break shell escaping
   - Bash heredocs (`cat << 'EOF'`) — fail in sandboxed environments (read-only /tmp for shell temp files)
   - `python3 -c` with `sys.stdin` pipe + heredoc — same heredoc failure

### Phase 3: Verification & Recovery (main context)
After all agents complete:
1. Check file sizes: `ls -la lectures_summary/<SUBJECT>/`
2. **If any files are missing or 0 bytes**, check the agent output log for these failure modes:
   - **`max_output_tokens` error**: Agent tried to output summary as text instead of writing to file. Stop the agent and write the summary from the main context.
   - **Shell escaping error in Bash**: Agent's `python3 -c` command failed on special characters. The content may still be in the agent's context — but it's usually faster to regenerate from the main context.
   - **Write tool denial**: Recover content from the agent output log:
     ```python
     python3 -c "
     import json
     with open('/tmp/claude-1000/-home-alex-lecture-manager/tasks/<agent_id>.output') as f:
         for line in f:
             try:
                 obj = json.loads(line.strip())
                 if obj.get('type') == 'assistant' and 'message' in obj:
                     for block in obj['message'].get('content', []):
                         if isinstance(block, dict) and block.get('type') == 'tool_use':
                             if block.get('name') == 'Write':
                                 content = block['input'].get('content', '')
                                 if len(content) > 100:
                                     with open('<target_path>', 'w') as out:
                                         out.write(content)
                                     print(f'Recovered {len(content)} chars')
                                     exit()
             except: pass
     "
     ```
   - Or write the summary directly from the main context using the Write tool.
3. Clean up temp files: `rm -rf /tmp/claude/lecture_images/ /tmp/claude/lecture_texts/`
4. Print final summary table.

### Monitoring Agents
Check on agents periodically (every 2-3 minutes) to catch failures early:
- `grep -o '"name":"[^"]*"' /tmp/claude-1000/-home-alex-lecture-manager/tasks/<agent_id>.output` — list tool calls
- `tail -c 300 /tmp/claude-1000/-home-alex-lecture-manager/tasks/<agent_id>.output` — see latest state
- `grep 'max_output_tokens' /tmp/claude-1000/-home-alex-lecture-manager/tasks/<agent_id>.output` — check for token limit errors
- If an agent has hit `max_output_tokens` twice, stop it and handle from main context

ARGUMENTS: if launching agents, periodically check on them to make sure they are not stuck

---
name: lark-meeting-doc-sync
description: Analyze a completed meeting and sync its decisions, open questions, risks, action items, and scope changes back into a Lark document as comments instead of editing the document body. Use when Codex has a source meeting artifact such as a Lark meeting record, minutes, transcript, AI summary, or raw meeting notes plus a target doc/docx/wiki document and needs to map meeting findings into the right sections with local comments when possible and full-document comments when necessary. Prefer this skill for PRDs, design docs, SOPs, plans, proposals, and any workflow where an initial document should be updated after a meeting through comments.
---

# Lark Meeting Doc Sync

Use this skill to bridge a meeting and an existing document without directly rewriting the document body.

The core job is:

- read the meeting artifact
- read the target document
- decide which meeting findings matter to the document
- choose local comment or full-document comment conservatively
- write comments back with `lark-cli`

## Required Skill Chain

- Always read the installed `lark-shared` skill first for auth, identity, and scope handling.
- Use the installed `lark-doc` skill to fetch the target document.
- Use the installed `lark-drive` skill to write comments.
- Use the installed `lark-vc` skill when the source is a completed meeting record or note.
- Use the installed `lark-minutes` skill when the source is a Minutes object or a minute token.

## Workflow

### 1. Confirm write intent

- Adding comments is a write operation.
- If the user asks for analysis only, stop at a comment plan and do not write.
- If the user wants the comments written, proceed after making the write intent explicit.

### 2. Resolve the meeting source

- For completed meetings, prefer `lark-cli vc +search`, `lark-cli vc +notes`, and `lark-cli vc +recording`.
- For Minutes URLs or tokens, prefer `lark-cli vc +notes --minute-tokens <token>` or `lark-minutes`.
- If the user already provided raw notes or pasted transcript text, skip source discovery.
- Prefer the most structured source available in this order: meeting notes document, AI summary, transcript, raw notes.

### 3. Resolve the target document

- Read the target with `lark-cli docs +fetch --doc <url-or-token>`.
- If the target is a wiki URL, resolve it before assuming it supports comments.
- Prefer `docx` when you need local comments.
- If the resolved object is `doc`, use full-document comments only.

### 4. Build a comment plan first

- Use [`references/workflow.md`](references/workflow.md) for the end-to-end flow.
- Use [`references/comment-strategy.md`](references/comment-strategy.md) for comment quality rules.
- Prefer `scripts/sync_lark_comments.py` as the primary entry point when the user wants an executable workflow rather than ad hoc commands.
- Use `scripts/extract_doc_structure.py` on `docs +fetch` output to get a clean section map.
- Use `scripts/build_comment_plan.py` with the meeting notes and section map to create a draft plan.
- Treat the draft plan as a heuristic scaffold. Refine it with actual reasoning before writing comments.

Example:

```powershell
python .\skills\lark-meeting-doc-sync\scripts\sync_lark_comments.py --target-doc "<DOC_URL>" --meeting-doc "<MEETING_DOC_URL>" --output-dir .\artifacts\sync-preview
```

### 5. Choose comment mode conservatively

- Use a local comment only when one section is clearly the right target.
- Prefer `--selection-with-ellipsis` with a heading or nearby sentence that is likely to match uniquely.
- Fall back to a full-document comment when:
  - the point affects multiple sections
  - the target is ambiguous
  - the target is `doc` rather than `docx`
  - the meeting signal is broad and editorial rather than section-specific

### 6. Write comments with `lark-drive`

If the user wants the workflow executed end-to-end, prefer:

```powershell
python .\skills\lark-meeting-doc-sync\scripts\sync_lark_comments.py --target-doc "<DOC_URL>" --meeting-doc "<MEETING_DOC_URL>" --output-dir .\artifacts\sync-apply --apply --allow-full-comments --min-confidence high
```

Local comment:

```powershell
lark-cli drive +add-comment --doc "<DOC_OR_WIKI_URL>" --selection-with-ellipsis "风险与待确认" --content '[{"type":"text","text":"会议同步：财务要求补充 T+1 对账 SLA，建议在本节显式写明。"}]'
```

Full-document comment:

```powershell
lark-cli drive +add-comment --doc "<DOC_OR_WIKI_URL>" --full-comment --content '[{"type":"text","text":"会议同步：发布时间不应再写死为 6 月，建议按联调结果调整发布计划描述。"}]'
```

If you need help generating `reply_elements`, use `scripts/render_reply_elements.py`.

### 7. Report what happened

- List written comments, skipped findings, and ambiguous cases.
- Explain any permission or document-type limitation.
- If you only produced a plan, say so clearly.

## Comment Quality Rules

- Keep one meeting signal per comment.
- State the meeting fact before the suggestion.
- Make the ask explicit: confirm, revise, add detail, or update timing.
- Do not directly rewrite the document unless the user explicitly changes the task from comment sync to document editing.
- Do not force local comments when confidence is low.

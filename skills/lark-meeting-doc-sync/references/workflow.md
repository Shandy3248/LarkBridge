# Workflow

## 1. Resolve the meeting source

- If the user gives a completed Lark meeting, prefer `lark-vc +search`, `lark-vc +notes`, or `lark-vc +recording`.
- If the user gives a Minutes URL, use `lark-minutes` or `lark-vc +notes --minute-tokens`.
- If the user already pasted raw notes, use the pasted text directly and skip source discovery.

## 2. Resolve the target document

- Use `lark-doc docs +fetch --doc <url-or-token>` to read the target document.
- If the target is a wiki URL, resolve it before assuming it is commentable.
- Prefer `docx` for local comments.
- If the target is only `doc`, fall back to full-document comments.

## 3. Build a comment plan before writing

- Use `scripts/extract_doc_structure.py` to turn `docs +fetch` JSON into a section map.
- Use `scripts/build_comment_plan.py` to combine the section map with meeting notes and create draft comments.
- Review the draft plan before writing anything back to Lark.

## 4. Choose comment mode conservatively

- Use a local comment only when the target section is unambiguous.
- Prefer `--selection-with-ellipsis` when the heading or a nearby sentence can be matched reliably.
- Fall back to a full-document comment when the target is ambiguous, the document type is not `docx`, or multiple sections would be equally valid.

## 5. Write comments

- Use `lark-cli drive +add-comment` for both local and full comments.
- Keep each comment focused on one meeting signal.
- Make the ask explicit: confirm, revise, add detail, or update timing.

## 6. Report outcome

- List which comments were written.
- List which items were skipped because they were duplicates or too ambiguous.
- Call out any permission or document-type limits.

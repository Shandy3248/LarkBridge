# Comment Strategy

## Comment types

- `decision`
  The meeting confirmed a fact, scope choice, owner, date, or direction that the document does not yet reflect.
- `open_question`
  The meeting exposed an unresolved item that should stay visible in the document.
- `risk`
  The meeting raised a dependency, blocker, SLA gap, or rollout risk.
- `action_item`
  The meeting produced a follow-up action that should be captured near the relevant section.
- `scope_change`
  The meeting changed what is in or out of scope for the current version.

## Good comment shape

Each comment should contain three parts:

1. Meeting signal
   State what the meeting added, changed, or left unresolved.
2. Why this section is affected
   Explain why the current document section should reflect that signal.
3. Explicit ask
   Ask for one concrete action such as clarifying scope, updating wording, adding SLA, or confirming ownership.

## Local vs full-document comments

- Use a local comment when the meeting point clearly belongs to one section.
- Use a full-document comment when the point affects multiple sections or when the correct anchor is unclear.
- Never force a local comment just because local comments are available.

## Dedup rules

- Collapse repeated findings into one comment.
- Do not add a comment when the target section already says the same thing with similar specificity.
- If one finding affects several sections, choose the most action-driving section and mention the cross-section impact in the comment body.

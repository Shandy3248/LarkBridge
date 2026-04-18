import argparse
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from build_comment_plan import build_plan, load_meeting_findings
from extract_doc_structure import build_sections, load_input


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
MINUTE_URL_RE = re.compile(r"/minutes/([A-Za-z0-9]+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch meeting content and a target Lark doc, build a comment plan, and optionally write comments back."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--target-doc", help="Target Lark doc/docx/wiki URL or token.")
    target.add_argument("--target-doc-json", help="Local docs +fetch JSON file for offline testing.")

    meeting = parser.add_mutually_exclusive_group(required=True)
    meeting.add_argument("--meeting-file", help="Local markdown/text file with meeting notes.")
    meeting.add_argument("--meeting-doc", help="Lark doc/wiki URL or token for meeting notes.")
    meeting.add_argument("--minute-tokens", help="Minute token(s) for vc +notes.")
    meeting.add_argument("--minute-url", help="Lark Minutes URL.")
    meeting.add_argument("--meeting-ids", help="Meeting ID(s) for vc +notes.")
    meeting.add_argument("--calendar-event-ids", help="Calendar event ID(s) for vc +notes.")

    parser.add_argument("--meeting-artifact", choices=["auto", "summary", "notes", "verbatim"], default="auto")
    parser.add_argument("--output-dir", help="Directory for fetched artifacts and generated plans.")
    parser.add_argument("--max-comments", type=int, default=20)
    parser.add_argument("--min-confidence", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--apply", action="store_true", help="Actually write comments back to the target doc.")
    parser.add_argument("--allow-full-comments", action="store_true", help="Allow full-document fallback comments when local anchoring is weak.")
    parser.add_argument("--apply-limit", type=int, default=5, help="Maximum comments to write in one run.")
    parser.add_argument("--apply-delay-seconds", type=int, default=8, help="Delay between comment writes.")
    parser.add_argument("--keep-proxy", action="store_true", help="Do not override HTTP(S)_PROXY or set LARK_CLI_NO_PROXY.")
    return parser.parse_args()


def ensure_output_dir(path_arg: str | None) -> Path:
    if path_arg:
        path = Path(path_arg)
    else:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path("artifacts") / f"sync-run-{stamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def prepare_env(keep_proxy: bool) -> dict[str, str]:
    env = os.environ.copy()
    if not keep_proxy:
        env["LARK_CLI_NO_PROXY"] = "1"
        env.pop("HTTP_PROXY", None)
        env.pop("HTTPS_PROXY", None)
        env.pop("http_proxy", None)
        env.pop("https_proxy", None)
    return env


def unwrap_lark_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload and payload.get("code") == 0:
        return payload["data"]
    if isinstance(payload, dict) and "data" in payload and payload.get("ok") is True:
        return payload["data"]
    return payload


def find_doc_payload(payload: Any) -> dict[str, Any] | None:
    payload = unwrap_lark_data(payload)
    if isinstance(payload, dict):
        if "title" in payload and "markdown" in payload:
            return payload
        for value in payload.values():
            found = find_doc_payload(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = find_doc_payload(item)
            if found:
                return found
    return None


def run_cli_json(env: dict[str, str], *args: str) -> Any:
    cli = shutil.which("lark-cli") or shutil.which("lark-cli.cmd") or "lark-cli"
    command = [cli, *args]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or f"Command failed: {' '.join(command)}")
    return json.loads(completed.stdout)


def fetch_doc_payload(doc_ref: str, env: dict[str, str]) -> dict[str, Any]:
    payload = run_cli_json(env, "docs", "+fetch", "--doc", doc_ref)
    doc = find_doc_payload(payload)
    if not doc:
        raise RuntimeError("Unable to locate title/markdown in docs +fetch response.")
    return doc


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def extract_minute_token(value: str) -> str:
    match = MINUTE_URL_RE.search(value)
    if match:
        return match.group(1)
    return value


def pick_note_doc_token(note: dict[str, Any], preferred: str) -> str | None:
    meeting_notes = note.get("meeting_notes") or []
    if preferred == "notes" and meeting_notes:
        return meeting_notes[0]
    if preferred == "verbatim" and note.get("verbatim_doc_token"):
        return note["verbatim_doc_token"]
    if preferred == "summary" and note.get("note_doc_token"):
        return note["note_doc_token"]

    for candidate in [note.get("note_doc_token"), *(meeting_notes or []), note.get("verbatim_doc_token")]:
        if candidate:
            return candidate
    return None


def render_artifacts_markdown(note_payload: dict[str, Any], output_dir: Path) -> str:
    artifacts = note_payload.get("artifacts") or {}
    if not artifacts:
        notes = note_payload.get("notes") or []
        if notes and isinstance(notes[0], dict):
            artifacts = notes[0].get("artifacts") or {}
    lines = ["# Meeting Notes"]

    summary = artifacts.get("summary")
    if summary:
        lines.append("## AI Summary")
        if isinstance(summary, str):
            lines.append(summary)
        else:
            lines.append(json.dumps(summary, ensure_ascii=False, indent=2))

    todos = artifacts.get("todos")
    if todos:
        lines.append("## Todos")
        lines.append(json.dumps(todos, ensure_ascii=False, indent=2))

    chapters = artifacts.get("chapters")
    if chapters:
        lines.append("## Chapters")
        lines.append(json.dumps(chapters, ensure_ascii=False, indent=2))

    transcript_file = artifacts.get("transcript_file")
    if transcript_file:
        transcript_path = Path(transcript_file)
        if not transcript_path.is_absolute():
            transcript_path = Path.cwd() / transcript_path
        if transcript_path.exists():
            transcript_text = transcript_path.read_text(encoding="utf-8")
            lines.append("## Transcript")
            lines.append(transcript_text[:20000])
            write_text(output_dir / "meeting-transcript.txt", transcript_text)

    if len(lines) == 1:
        raise RuntimeError("vc +notes returned no note doc token and no inline artifacts to analyze.")
    return "\n\n".join(lines) + "\n"


def resolve_meeting_markdown(args: argparse.Namespace, env: dict[str, str], output_dir: Path) -> tuple[str, str, dict[str, Any]]:
    if args.meeting_file:
        text = Path(args.meeting_file).read_text(encoding="utf-8")
        return text, str(Path(args.meeting_file)), {"type": "meeting_file", "source": args.meeting_file}

    if args.meeting_doc:
        payload = fetch_doc_payload(args.meeting_doc, env)
        write_json(output_dir / "meeting-doc.json", payload)
        return payload["markdown"], args.meeting_doc, {"type": "meeting_doc", "source": args.meeting_doc, "title": payload.get("title")}

    note_args = ["vc", "+notes", "--format", "json"]
    if args.minute_tokens or args.minute_url:
        minute_tokens = extract_minute_token(args.minute_url) if args.minute_url else args.minute_tokens
        note_args.extend(["--minute-tokens", minute_tokens, "--output-dir", str(output_dir / "meeting-artifacts"), "--overwrite"])
        source_label = f"minute_tokens:{minute_tokens}"
    elif args.meeting_ids:
        note_args.extend(["--meeting-ids", args.meeting_ids])
        source_label = f"meeting_ids:{args.meeting_ids}"
    else:
        note_args.extend(["--calendar-event-ids", args.calendar_event_ids])
        source_label = f"calendar_event_ids:{args.calendar_event_ids}"

    raw_payload = run_cli_json(env, *note_args)
    payload = unwrap_lark_data(raw_payload)
    write_json(output_dir / "meeting-notes-response.json", raw_payload)

    notes = payload.get("notes") or []
    if notes:
        note = notes[0]
        doc_token = pick_note_doc_token(note, args.meeting_artifact)
        if doc_token:
            doc_payload = fetch_doc_payload(doc_token, env)
            write_json(output_dir / "meeting-doc.json", doc_payload)
            return doc_payload["markdown"], source_label, {"type": "vc_notes_doc", "source": source_label, "doc_token": doc_token, "title": doc_payload.get("title")}

    markdown = render_artifacts_markdown(payload, output_dir)
    write_text(output_dir / "meeting-artifacts.md", markdown)
    return markdown, source_label, {"type": "vc_artifacts", "source": source_label}


def resolve_target_doc(args: argparse.Namespace, env: dict[str, str], output_dir: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    if args.target_doc_json:
        title, markdown = load_input(Path(args.target_doc_json))
        payload = {"title": title, "markdown": markdown}
        write_json(output_dir / "target-doc.json", payload)
        return payload, args.target_doc_json, {"type": "local_json", "source": args.target_doc_json}

    payload = fetch_doc_payload(args.target_doc, env)
    write_json(output_dir / "target-doc.json", payload)
    return payload, args.target_doc, {"type": "lark_doc", "source": args.target_doc, "title": payload.get("title")}


def should_apply(item: dict[str, Any], min_confidence: str) -> bool:
    return CONFIDENCE_ORDER[item["confidence"]] >= CONFIDENCE_ORDER[min_confidence]


def build_windows_cmd(command: list[str]) -> str:
    escaped = []
    for arg in command:
        escaped.append('"' + arg.replace('"', '""') + '"')
    return " ".join(escaped)


def run_cli_write(env: dict[str, str], *args: str) -> dict[str, Any]:
    cli = shutil.which("lark-cli.cmd") or shutil.which("lark-cli") or "lark-cli"
    command = [cli, *args]
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", build_windows_cmd(command)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )
    else:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def apply_comments(args: argparse.Namespace, env: dict[str, str], target_ref: str, plan: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    if not args.target_doc:
        raise RuntimeError("Cannot write comments when using --target-doc-json. Use --target-doc instead.")

    results = {"applied": [], "skipped": []}
    applied_count = 0
    for item in plan["items"]:
        if not should_apply(item, args.min_confidence):
            results["skipped"].append({"id": item["id"], "reason": f"confidence<{args.min_confidence}"})
            continue
        if applied_count >= args.apply_limit:
            results["skipped"].append({"id": item["id"], "reason": f"apply_limit={args.apply_limit}"})
            continue

        content = json.dumps([{"type": "text", "text": item["draft_comment"]}], ensure_ascii=False)
        if item["mode"] == "local_candidate" and item.get("selection_hint"):
            result = run_cli_write(
                env,
                "drive",
                "+add-comment",
                "--doc",
                target_ref,
                "--selection-with-ellipsis",
                item["selection_hint"],
                "--content",
                content,
            )
            result["id"] = item["id"]
            result["mode"] = "local_comment"
            if result["returncode"] == 0:
                results["applied"].append(result)
                applied_count += 1
                time.sleep(args.apply_delay_seconds)
            else:
                results["skipped"].append({"id": item["id"], "reason": result["stderr"] or result["stdout"]})
            continue

        if args.allow_full_comments:
            result = run_cli_write(
                env,
                "drive",
                "+add-comment",
                "--doc",
                target_ref,
                "--full-comment",
                "--content",
                content,
            )
            result["id"] = item["id"]
            result["mode"] = "full_comment"
            if result["returncode"] == 0:
                results["applied"].append(result)
                applied_count += 1
                time.sleep(args.apply_delay_seconds)
            else:
                results["skipped"].append({"id": item["id"], "reason": result["stderr"] or result["stdout"]})
            continue

        results["skipped"].append({"id": item["id"], "reason": "no_local_anchor_and_full_comments_disabled"})

    write_json(output_dir / "apply-results.json", results)
    return results


def main() -> None:
    args = parse_args()
    output_dir = ensure_output_dir(args.output_dir)
    env = prepare_env(args.keep_proxy)

    target_payload, target_ref, target_meta = resolve_target_doc(args, env, output_dir)
    meeting_markdown, meeting_label, meeting_meta = resolve_meeting_markdown(args, env, output_dir)

    write_text(output_dir / "meeting-notes.md", meeting_markdown)

    doc_structure = build_sections(target_payload.get("title") or "Untitled", target_payload.get("markdown") or "")
    doc_structure["source_path"] = target_ref
    write_json(output_dir / "doc-structure.json", doc_structure)

    findings = load_meeting_findings(output_dir / "meeting-notes.md")
    plan = build_plan(doc_structure, findings, meeting_label, args.max_comments)
    write_json(output_dir / "comment-plan.json", plan)

    summary = {
        "target": target_meta,
        "meeting": meeting_meta,
        "output_dir": str(output_dir),
        "item_count": plan["item_count"],
        "apply_requested": args.apply,
        "allow_full_comments": args.allow_full_comments,
        "min_confidence": args.min_confidence,
    }

    if args.apply:
        summary["apply_results"] = apply_comments(args, env, target_ref, plan, output_dir)
    else:
        summary["apply_results"] = None

    write_json(output_dir / "run-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

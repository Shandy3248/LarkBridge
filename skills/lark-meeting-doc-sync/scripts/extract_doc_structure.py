import argparse
import json
import re
from pathlib import Path


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
TAG_RE = re.compile(r"<[^>]+>")


def load_input(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        title = data.get("title") or path.stem
        markdown = data.get("markdown") or ""
        return title, markdown
    return path.stem, raw


def clean_line(value: str) -> str:
    value = TAG_RE.sub(" ", value)
    value = re.sub(r"[`*_>#-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def build_sections(title: str, markdown: str) -> dict:
    lines = markdown.splitlines()
    headings: list[dict] = []
    for index, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if not match:
            continue
        headings.append(
            {
                "line": index,
                "level": len(match.group(1)),
                "heading": match.group(2).strip(),
            }
        )

    sections = []
    if not headings:
        preview = " ".join(clean_line(line) for line in lines if clean_line(line))
        sections.append(
            {
                "index": 1,
                "level": 0,
                "heading": title,
                "start_line": 1,
                "end_line": len(lines),
                "anchor_text": preview[:120] or title,
                "preview": preview[:240],
                "selection_hints": [value for value in [title, preview[:120]] if value],
            }
        )
        return {
            "title": title,
            "line_count": len(lines),
            "section_count": len(sections),
            "sections": sections,
        }

    first_heading_line = headings[0]["line"]
    if first_heading_line > 1:
        intro_lines = lines[: first_heading_line - 1]
        intro_preview = " ".join(clean_line(line) for line in intro_lines if clean_line(line))
        if intro_preview:
            sections.append(
                {
                    "index": 1,
                    "level": 0,
                    "heading": title,
                    "start_line": 1,
                    "end_line": first_heading_line - 1,
                    "anchor_text": intro_preview[:120],
                    "preview": intro_preview[:240],
                    "selection_hints": [value for value in [title, intro_preview[:120]] if value],
                }
            )

    for offset, heading in enumerate(headings):
        start = heading["line"]
        end = headings[offset + 1]["line"] - 1 if offset + 1 < len(headings) else len(lines)
        body_lines = lines[start - 1 : end]
        cleaned_lines = [clean_line(line) for line in body_lines]
        cleaned_lines = [line for line in cleaned_lines if line]
        preview = " ".join(cleaned_lines)[:240]
        anchor_text = cleaned_lines[1] if len(cleaned_lines) > 1 else heading["heading"]
        selection_hints = []
        for value in [heading["heading"], anchor_text]:
            if value and value not in selection_hints:
                selection_hints.append(value)
        sections.append(
            {
                "index": len(sections) + 1,
                "level": heading["level"],
                "heading": heading["heading"],
                "start_line": start,
                "end_line": end,
                "anchor_text": anchor_text[:120],
                "preview": preview,
                "selection_hints": selection_hints,
            }
        )

    return {
        "title": title,
        "line_count": len(lines),
        "section_count": len(sections),
        "sections": sections,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract a section map from docs +fetch output.")
    parser.add_argument("--input", required=True, help="Path to docs +fetch JSON or raw markdown.")
    parser.add_argument("--output", required=True, help="Path to write JSON output.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    title, markdown = load_input(input_path)
    result = build_sections(title, markdown)
    result["source_path"] = str(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

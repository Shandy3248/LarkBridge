import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


TOKEN_RE = re.compile(r"[a-zA-Z0-9_+-]{3,}|[\u4e00-\u9fff]{2,}")
FINDING_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}")
SPEAKER_RE = re.compile(r"^说话人\s+\d+")
KEYWORD_LINE_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9、,，/ -]{8,}$")
TRANSCRIPT_NOISE_MARKERS = ["诶，你好", "第二个问题", "我想调研一下", "我想了解一下", "OK，", "OK,"]

CATEGORY_RULES = [
    ("open_question", ["待确认", "未定", "是否", "需要确认", "pending", "question"]),
    ("risk", ["风险", "依赖", "阻塞", "sla", "失败", "重试", "blocked"]),
    ("scope_change", ["首版", "mvp", "范围", "不进入", "不支持", "下一阶段", "scope"]),
    ("action_item", ["本周", "跟进", "负责人", "action", "follow up"]),
    ("decision", ["确认", "确定", "已定", "agreed", "decision"]),
]

HEADING_HINT_RULES = [
    (["风险", "待确认"], ["风险", "sla", "失败", "重试", "待确认", "未定", "依赖"]),
    (["发布", "计划"], ["发布", "上线", "时间", "联调", "延期", "锁定"]),
    (["目标"], ["目标", "首版", "mvp", "支持", "范围"]),
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> set[str]:
    lowered = normalize(text).lower()
    tokens = set(TOKEN_RE.findall(lowered))
    grams: set[str] = set()
    cjk_only = re.sub(r"[^\u4e00-\u9fff]", "", lowered)
    for size in (2, 3):
        for index in range(0, max(0, len(cjk_only) - size + 1)):
            grams.add(cjk_only[index : index + size])
    return {token for token in tokens | grams if token}


def classify(text: str) -> str:
    lowered = text.lower()
    for category, keywords in CATEGORY_RULES:
        if any(keyword in lowered for keyword in keywords):
            return category
    return "note"


def load_meeting_findings(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    findings = []
    seen: set[str] = set()
    for line in lines:
        line = normalize(FINDING_RE.sub("", line))
        if len(line) < 8:
            continue
        if line.startswith("#"):
            continue
        if TIMESTAMP_RE.match(line):
            continue
        if SPEAKER_RE.match(line):
            continue
        if line.startswith("关键词"):
            continue
        if "内容如下" in line and len(line) < 40:
            continue
        if KEYWORD_LINE_RE.match(line) and ("、" in line or "，" in line or "," in line) and len(line) < 40:
            continue
        if len(line) > 60 and any(marker in line for marker in TRANSCRIPT_NOISE_MARKERS):
            continue
        if line in seen:
            continue
        seen.add(line)
        findings.append(line)
    return findings


def score_finding(section: dict, finding: str) -> int:
    finding_tokens = tokenize(finding)
    heading_score = 3 * len(tokenize(section["heading"]) & finding_tokens)
    anchor_score = 2 * len(tokenize(section.get("anchor_text", "")) & finding_tokens)
    preview_score = len(tokenize(section.get("preview", "")) & finding_tokens)
    normalized_finding = finding.lower()
    heading_boost = 0
    for heading_keywords, finding_keywords in HEADING_HINT_RULES:
        if any(keyword in section["heading"] for keyword in heading_keywords) and any(
            keyword in normalized_finding for keyword in finding_keywords
        ):
            heading_boost += 8
    return heading_score + anchor_score + preview_score + heading_boost


def build_comment(category: str, finding: str, heading: str | None) -> str:
    prefix = {
        "decision": "会议同步：本次会议已确认",
        "open_question": "会议同步：这里仍有待确认项",
        "risk": "会议同步：本次会议暴露出一个风险或依赖",
        "action_item": "会议同步：这里需要补充一个跟进动作",
        "scope_change": "会议同步：本次会议调整了当前范围",
        "note": "会议同步：本次会议补充了相关信息",
    }[category]
    if heading:
        return f"{prefix}“{finding}”。建议核对“{heading}”这一节是否需要补充、修订或显式标注。"
    return f"{prefix}“{finding}”。建议在文档中补充对应说明或确认项。"


def build_plan(doc_data: dict, findings: list[str], meeting_source: str, max_comments: int = 20) -> dict:
    sections = doc_data.get("sections", [])
    plan_items = []
    for index, finding in enumerate(findings[:max_comments], start=1):
        scored = sorted(
            (
                {
                    "section": section,
                    "score": score_finding(section, finding),
                }
                for section in sections
            ),
            key=lambda item: item["score"],
            reverse=True,
        )
        best = scored[0] if scored else None
        category = classify(finding)
        if best and best["score"] > 0:
            section = best["section"]
            mode = "local_candidate"
            heading = section["heading"]
            selection_hint = section["selection_hints"][0] if section.get("selection_hints") else section["heading"]
            score = best["score"]
        else:
            section = None
            mode = "full_comment"
            heading = None
            selection_hint = None
            score = 0

        plan_items.append(
            {
                "id": f"F{index:02d}",
                "category": category,
                "finding": finding,
                "mode": mode,
                "confidence": "high" if score >= 8 else "medium" if score >= 4 else "low",
                "score": score,
                "target_section_index": section["index"] if section else None,
                "target_heading": heading,
                "selection_hint": selection_hint,
                "draft_comment": build_comment(category, finding, heading),
            }
        )

    filtered_items = []
    seen_targets: set[tuple[str | None, str]] = set()
    for item in sorted(
        plan_items,
        key=lambda value: (
            CONFIDENCE_ORDER[value["confidence"]],
            value["score"],
            -len(value["finding"]),
        ),
        reverse=True,
    ):
        target_key = (item["target_heading"], item["category"])
        if target_key in seen_targets:
            continue
        seen_targets.add(target_key)
        filtered_items.append(item)

    filtered_items.sort(key=lambda value: value["id"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "doc_title": doc_data.get("title"),
        "doc_source": doc_data.get("source_path"),
        "meeting_source": meeting_source,
        "item_count": len(filtered_items),
        "items": filtered_items,
    }


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a draft comment plan from doc structure and meeting notes.")
    parser.add_argument("--doc-structure", required=True, help="Path to extract_doc_structure.py JSON output.")
    parser.add_argument("--meeting", required=True, help="Path to meeting notes in markdown or text.")
    parser.add_argument("--output", required=True, help="Path to write the draft plan JSON.")
    parser.add_argument("--max-comments", type=int, default=20, help="Maximum number of findings to emit.")
    args = parser.parse_args()

    doc_data = json.loads(Path(args.doc_structure).read_text(encoding="utf-8"))
    findings = load_meeting_findings(Path(args.meeting))
    result = build_plan(doc_data, findings, str(Path(args.meeting)), args.max_comments)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

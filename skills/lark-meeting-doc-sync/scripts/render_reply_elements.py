import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="Render plain text into Lark reply_elements JSON.")
    parser.add_argument("--text", required=True, help="Comment text.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    args = parser.parse_args()

    payload = [{"type": "text", "text": args.text}]
    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()

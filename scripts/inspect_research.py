
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = [
    ROOT / "knowledge_base" / "raw_documents.json",
    ROOT / "knowledge_base" / "raw_wikipedia.json",
]


def inspect_file(path):
    print(f"\n{'=' * 60}")
    print(f"FILE: {path.name}")
    print("=" * 60)

    if not path.exists():
        print("File not found!")
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as error:
        print("Could not read JSON:", error)
        return

    print("Top-level type:", type(data).__name__)

    if isinstance(data, list):
        print("Total records:", len(data))

        if not data:
            print("No records found.")
            return

        for index, record in enumerate(data[:3], start=1):
            print(f"\nRecord {index}:")

            if isinstance(record, dict):
                for key, value in record.items():
                    if isinstance(value, str):
                        preview = value[:180].replace("\n", " ")
                        print(f"  {key}: {preview!r}")
                    elif isinstance(value, list):
                        print(f"  {key}: list with {len(value)} items")
                    elif isinstance(value, dict):
                        print(f"  {key}: dict with keys {list(value)[:10]}")
                    else:
                        print(f"  {key}: {value!r}")
            else:
                print("  Record type:", type(record).__name__)

    elif isinstance(data, dict):
        print("Top-level keys:", list(data.keys()))

    else:
        print("Unexpected JSON structure.")


if __name__ == "__main__":
    for file_path in FILES:
        inspect_file(file_path)

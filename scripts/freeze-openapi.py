"""Freeze only the implemented v1 OpenAPI contract; no legacy compatibility claim."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Update after contract review")
    args = parser.parse_args()
    from radar.main import app

    target = ROOT / "contracts" / "openapi" / "v1.json"
    schema = json.dumps(app.openapi(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(schema, encoding="utf-8")
        print("Updated implemented v1 OpenAPI snapshot.")
        return 0
    if not target.exists() or json.loads(target.read_text(encoding="utf-8")) != json.loads(schema):
        print("OpenAPI differs from reviewed contracts/openapi/v1.json. Review before --write.")
        return 1
    print("Implemented v1 OpenAPI matches the reviewed snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

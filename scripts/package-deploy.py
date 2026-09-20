"""Package only the files needed to install the published Docker images."""

from pathlib import Path
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".release" / "ai-radar-deploy.zip"
FILES = (
    "scripts/release.py", "scripts/pull-release.py", "scripts/backup-database.py",
    "deploy/containers/Caddyfile.release",
    "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md",
)


def main() -> None:
    OUTPUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.glob("compose.release*.json"):
            config = json.loads(path.read_text(encoding="utf-8-sig"))
            for service in config.get("services", {}).values():
                service.pop("build", None)
            archive.writestr("ai-radar/" + path.name, json.dumps(config, indent=2) + "\n")
        for name in FILES:
            path = ROOT / name
            archive.write(path, "ai-radar/" + name)
    print(OUTPUT)


if __name__ == "__main__":
    main()

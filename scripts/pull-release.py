"""Pull release images from one Docker repository and give them local Compose tags."""

from __future__ import annotations

import argparse
import subprocess


DEFAULT_REPOSITORY = (
    "crpi-z2yvaep8ppb79obm.cn-hangzhou.personal.cr.aliyuncs.com"
    "/ai_radar_spec/ai_radar_docker"
)
ROLES = ("db", "backend", "gateway")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY,
                        help="Docker repository containing role-version tags")
    parser.add_argument("--version", default="v0.1.2", help="release tag suffix (default: v0.1.2)")
    parser.add_argument("--assistant", action="store_true", help="also pull the optional pi image")
    args = parser.parse_args()
    repository = args.repository.rstrip("/")
    if not repository or "://" in repository or "@" in repository or ":" in repository.rsplit("/", 1)[-1]:
        parser.error("--repository must be an untagged Docker repository name")
    if not args.version or any(character in args.version for character in ":/@ "):
        parser.error("--version must be a Docker tag suffix such as v0.1.2")

    roles = (*ROLES, *(("pi",) if args.assistant else ()))
    for role in roles:
        subprocess.run(["docker", "pull", f"{repository}:{role}-{args.version}"], check=True)
    for role in roles:
        source = f"{repository}:{role}-{args.version}"
        local = f"ai-radar-{role}:{args.version}"
        subprocess.run(["docker", "tag", source, local], check=True)
        print(f"{source} -> {local}")


if __name__ == "__main__":
    main()

"""Private-network container entry; host entry remains loopback/systemd based."""

from pathlib import Path

from .sandbox_controller import production_app
from .sandbox_credentials import read_service_token
from .sandbox_watchdog import container_watchdog


def main() -> None:
    import argparse
    import asyncio
    import os

    import httpx
    import uvicorn

    from .research_guard import ResearchRejected
    from .sandbox_client import SandboxClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    token = read_service_token(Path("/run/secrets/sandbox_token"))
    if args.check:

        async def check() -> None:
            async with httpx.AsyncClient(trust_env=False) as client:
                await SandboxClient(client, "http://127.0.0.1:8092", token).ready(
                    os.environ.get("RADAR_SANDBOX_IMAGE_ID")
                )

        try:
            asyncio.run(check())
        except (ResearchRejected, OSError, ValueError):
            raise SystemExit(1) from None
        return
    app = production_app(
        os.environ["RADAR_SANDBOX_IMAGE_ID"],
        token,
        Path("/run/radar-control/controller.lock"),
        watchdog=container_watchdog,
    )
    uvicorn.run(app, host="0.0.0.0", port=8092, workers=1, access_log=False)


if __name__ == "__main__":
    main()

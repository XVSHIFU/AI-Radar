"""Private-network container entry; host entry remains loopback/systemd based."""

from pathlib import Path

from .sandbox_controller import production_app
from .sandbox_credentials import read_service_token
from .sandbox_watchdog import container_watchdog


def main() -> None:
    import os

    import uvicorn

    token = read_service_token(Path("/run/secrets/sandbox_token"))
    app = production_app(
        os.environ["RADAR_SANDBOX_IMAGE_ID"],
        token,
        Path("/run/radar-control/controller.lock"),
        watchdog=container_watchdog,
    )
    uvicorn.run(app, host="0.0.0.0", port=8092, workers=1, access_log=False)


if __name__ == "__main__":
    main()

"""Operator-only credentials; never import through model tool dispatch."""

import os
import stat
from pathlib import Path

from .sandbox_http import service_token


def read_service_token(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_size > 130
        ):
            raise ValueError("service credential must be a private operator-owned file")
        raw = stream.read(131)
        if len(raw) > 130:
            raise ValueError("invalid service credential file")
    return service_token(raw.decode("ascii").strip())

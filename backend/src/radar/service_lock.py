"""Operator process locking, independent of the Docker control plane."""

import os
from pathlib import Path
from typing import BinaryIO


def acquire_lock(path: Path) -> BinaryIO:
    import fcntl

    # Never unlink: all deployments must keep locking the same inode.
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    stream = os.fdopen(descriptor, "r+b")
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        stream.close()
        raise
    return stream

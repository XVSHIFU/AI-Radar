import os
import subprocess
import sys
from pathlib import Path

import pytest

from radar.service_lock import acquire_lock

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux flock semantics")


def contender(path):
    code = """
import sys
from pathlib import Path
from radar.service_lock import acquire_lock
try:
    lock = acquire_lock(Path(sys.argv[1]))
except BlockingIOError:
    raise SystemExit(17)
lock.close()
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    return subprocess.run([sys.executable, "-c", code, str(path)], env=env, check=False).returncode


def test_another_process_cannot_hold_same_lock_and_can_recover_after_exit(tmp_path):
    path = tmp_path / "worker.lock"
    first = acquire_lock(path)
    try:
        inode = path.stat().st_ino
        assert contender(path) == 17
        assert path.stat().st_ino == inode
    finally:
        first.close()
    assert contender(path) == 0
    assert path.stat().st_ino == inode


def test_lock_path_symlink_is_rejected(tmp_path):
    target = tmp_path / "target"
    target.write_text("")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError):
        acquire_lock(link)

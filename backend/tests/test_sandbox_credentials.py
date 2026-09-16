"""Linux file boundary tests: these are skipped, not emulated, on Windows."""

import os
import sys

import pytest

from radar.sandbox_credentials import read_service_token

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux credential file semantics")
TOKEN = "a" * 43


def private_file(tmp_path, content=TOKEN):
    path = tmp_path / "token"
    path.write_text(content, encoding="ascii")
    path.chmod(0o600)
    return path


def test_private_file_and_optional_final_newline(tmp_path):
    path = private_file(tmp_path, TOKEN + "\n")
    assert read_service_token(path) == TOKEN
    path.chmod(0o400)
    assert read_service_token(path) == TOKEN


@pytest.mark.parametrize("mode", [0o640, 0o604, 0o660, 0o644])
def test_group_or_other_permissions_rejected(tmp_path, mode):
    path = private_file(tmp_path)
    path.chmod(mode)
    with pytest.raises(ValueError, match="private operator-owned"):
        read_service_token(path)


def test_symlink_is_rejected_even_when_target_is_private(tmp_path):
    path = private_file(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        read_service_token(link)


def test_fifo_is_rejected_without_waiting_for_a_writer(tmp_path):
    path = tmp_path / "pipe"
    os.mkfifo(path, 0o600)
    with pytest.raises(ValueError, match="private operator-owned"):
        read_service_token(path)


def test_wrong_owner_is_rejected(tmp_path, monkeypatch):
    path = private_file(tmp_path)
    uid = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: uid + 1)
    with pytest.raises(ValueError, match="private operator-owned"):
        read_service_token(path)


@pytest.mark.parametrize("content", ["", "short", "a" * 131, "a" * 129, "a" * 42 + "!"])
def test_invalid_or_oversized_token_is_rejected(tmp_path, content):
    with pytest.raises(ValueError):
        read_service_token(private_file(tmp_path, content))


def test_checked_descriptor_is_read_if_path_is_replaced(tmp_path, monkeypatch):
    path = private_file(tmp_path)
    original_fstat = os.fstat

    def replace_after_open(fd):
        info = original_fstat(fd)
        replacement = tmp_path / "replacement"
        replacement.write_text("b" * 43, encoding="ascii")
        replacement.chmod(0o644)
        replacement.replace(path)
        return info

    monkeypatch.setattr(os, "fstat", replace_after_open)
    assert read_service_token(path) == TOKEN

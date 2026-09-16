"""Operator-provisioned model artifact gate for the embedding Compose profile."""

import hashlib
import os
import stat
from pathlib import Path

MODEL_ROOT = Path("/opt/radar-embedding")
REVISION = "7698c0c30eafe2736771e96d733545270cdec56f"
# Existing Ubuntu artifacts recorded in retrieval-validation.md and verified
# tokenizer digest on 2026-09-16. No download or model installation at runtime.
ARTIFACTS = {
    "model.onnx": (569721516, "796e1f3985226cb8e5b3b52f9c70154c82ab3d65cfed13fdf6faea03aae67cd3"),
    "tokenizer.json": (
        17082821,
        "6710678b12670bc442b99edc952c4d996ae309a7020c1fa0096dd245c2faf790",
    ),
}


def verify_model(root: Path = MODEL_ROOT) -> None:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("embedding_model_unverified")
    for name, (size, digest) in ARTIFACTS.items():
        descriptor = os.open(root / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size != size:
                raise ValueError("embedding_model_unverified")
            # Bound the read even if a trusted host operator changes the file.
            value, remaining = hashlib.sha256(), size
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("embedding_model_unverified")
                value.update(chunk)
                remaining -= len(chunk)
            if stream.read(1) or value.hexdigest() != digest:
                raise ValueError("embedding_model_unverified")

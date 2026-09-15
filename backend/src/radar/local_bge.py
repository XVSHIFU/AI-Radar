from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .retrieval import EmbeddingProfile

BGE_M3_DIMENSION = 1024


class LocalBgeM3Provider:
    """Lazy CPU-only ONNX adapter; model artifacts are provisioned outside Git."""

    def __init__(self, model_dir: Path, revision: str, *, threads: int = 4) -> None:
        if not revision:
            raise ValueError("a pinned model revision is required")
        self.model_dir = model_dir
        self.threads = threads
        self.profile = EmbeddingProfile(
            provider="local-onnx-cpu",
            model_id="BAAI/bge-m3-int8",
            revision=revision,
            dimension=BGE_M3_DIMENSION,
            normalize=True,
            input_template_version="plain-query-v1",
        )
        self._runtime: tuple[Any, Any, Any] | None = None

    def _load(self) -> tuple[Any, Any, Any]:
        if self._runtime is not None:
            return self._runtime
        try:
            import numpy as np  # type: ignore[import-not-found]
            import onnxruntime as ort  # type: ignore[import-not-found]
            from tokenizers import Tokenizer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("install the embedding-local optional dependency") from exc
        model_path = self.model_dir / "model.onnx"
        tokenizer_path = self.model_dir / "tokenizer.json"
        if not model_path.is_file() or not tokenizer_path.is_file():
            raise RuntimeError("pinned BGE-M3 model artifacts are unavailable")
        options = ort.SessionOptions()
        options.intra_op_num_threads = self.threads
        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        tokenizer.enable_truncation(max_length=512)
        session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
        self._runtime = (np, tokenizer, session)
        return self._runtime

    def _embed(self, text: str) -> list[float]:
        np, tokenizer, session = self._load()
        encoded = tokenizer.encode(text)
        inputs = {
            "input_ids": np.asarray([encoded.ids], dtype=np.int64),
            "attention_mask": np.asarray([encoded.attention_mask], dtype=np.int64),
        }
        expected = {item.name for item in session.get_inputs()}
        if "token_type_ids" in expected:
            inputs["token_type_ids"] = np.zeros_like(inputs["input_ids"])
        hidden = session.run(
            None, {key: value for key, value in inputs.items() if key in expected}
        )[0]
        mask = inputs["attention_mask"][:, :, None]
        pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
        pooled /= np.linalg.norm(pooled, axis=1, keepdims=True)
        vector = [float(value) for value in pooled[0]]
        if len(vector) != BGE_M3_DIMENSION:
            raise RuntimeError(f"BGE-M3 returned {len(vector)} dimensions")
        return vector

    async def embed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._embed, text)
